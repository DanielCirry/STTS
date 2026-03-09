"""
Core RVC voice conversion pipeline.

Ported from RVC infer/modules/vc/pipeline.py

Implements the full voice conversion chain:
1. HuBERT feature extraction
2. RMVPE pitch extraction with semitone shift
3. Optional FAISS index retrieval
4. VITS synthesizer forward pass
5. RMS loudness matching

All operations use torch.no_grad() -- this is inference only.
"""

import logging
import os
import numpy as np
import torch
from torch.nn import functional as F
# scipy is optional -- use numpy fallback for median filter if not available
try:
    from scipy import signal as scipy_signal
    HAS_SCIPY = True
    # 48Hz high-pass Butterworth filter matching original RVC preprocessing
    # Removes DC offset and low-frequency rumble that affect HuBERT/RMVPE
    _bh, _ah = scipy_signal.butter(N=5, Wn=48, btype="high", fs=16000)
except ImportError:
    HAS_SCIPY = False
    _bh, _ah = None, None

from ai.rvc.audio import load_audio_from_numpy, match_rms
from ai.rvc.config import get_device, get_is_half
from ai.rvc.models.synthesizer import SynthesizerTrnMs256NSFsid, SynthesizerTrnMs768NSFsid

logger = logging.getLogger('stts.rvc.pipeline')

# FAISS is optional -- graceful degradation if not installed
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning(
        "FAISS not available. RVC index retrieval disabled (index_rate forced to 0). "
        "Install faiss-cpu for improved voice quality: pip install faiss-cpu"
    )


class Pipeline:
    """RVC voice conversion pipeline.

    Coordinates HuBERT feature extraction, RMVPE pitch estimation,
    optional FAISS retrieval, and VITS synthesis.
    """

    def __init__(self, tgt_sr: int, device: torch.device, is_half: bool = False):
        """Initialize pipeline.

        Args:
            tgt_sr: Target sample rate of the synthesizer model.
            device: Torch compute device.
            is_half: Whether to use half precision.
        """
        self.tgt_sr = tgt_sr
        self.device = device
        self.is_half = is_half

        # Window size for the synthesizer (matches model training)
        self.window = 160  # 10ms at 16kHz
        # Padding in seconds — matches original RVC (x_pad=1 for CPU inference).
        # Provides enough context for accurate pitch detection and feature
        # extraction at chunk boundaries. Original uses 1-3s depending on VRAM.
        self.x_pad = 1  # seconds of padding on each side
        self.t_pad = 16000 * self.x_pad  # 16000 samples = 1s at 16kHz
        self.t_pad_tgt = self.tgt_sr * self.x_pad  # equivalent in output SR

        # F0 computation constants
        self.f0_min = 50
        self.f0_max = 1100
        self.f0_mel_min = 1127 * np.log(1 + self.f0_min / 700)
        self.f0_mel_max = 1127 * np.log(1 + self.f0_max / 700)

    @torch.no_grad()
    def vc_single(
        self,
        hubert_model,
        net_g,
        sid,
        audio: np.ndarray,
        input_sr: int,
        f0_up_key: int,
        rmvpe_model,
        index=None,
        index_rate: float = 0.75,
        filter_radius: int = 3,
        rms_mix_rate: float = 0.25,
        protect: float = 0.33,
        resample_sr: int = 0,
    ) -> np.ndarray:
        """Run voice conversion on a single audio clip.

        Args:
            hubert_model: Loaded HuBERT model for feature extraction.
            net_g: Loaded VITS synthesizer model (v1 or v2).
            sid: Speaker ID tensor (usually 0).
            audio: Float32 numpy audio at any sample rate.
            input_sr: Sample rate of the input audio.
            f0_up_key: Semitone shift (-12 to +12).
            rmvpe_model: Loaded RMVPE model for pitch extraction.
            index: FAISS index (optional, can be None).
            index_rate: FAISS retrieval influence (0.0 = none, 1.0 = full).
            filter_radius: Median filter radius for pitch smoothing (1-7).
            rms_mix_rate: RMS loudness matching mix (0.0-1.0).
            protect: Consonant protection (0.0-0.5).
            resample_sr: Output resample rate (0 = use model's native rate).

        Returns:
            Float32 numpy array of converted audio at tgt_sr (or resample_sr).
        """
        # Ensure float32 mono at 16kHz for processing
        audio_16k = load_audio_from_numpy(audio, input_sr, target_sr=16000)
        logger.debug(
            f"vc_single: input {len(audio)} samples @ {input_sr}Hz "
            f"-> {len(audio_16k)} @ 16kHz ({len(audio_16k)/16000:.2f}s)"
        )

        # Apply 48Hz high-pass filter to remove DC offset and low-frequency rumble
        # This is critical for clean HuBERT features and pitch detection
        if HAS_SCIPY and _bh is not None:
            audio_16k = scipy_signal.filtfilt(_bh, _ah, audio_16k).astype(np.float32)

        # Normalize amplitude to ~[-0.95, 0.95] range — matches original RVC.
        # HuBERT was trained on normalized audio; feeding it unnormalized
        # audio degrades feature extraction and produces robotic artifacts.
        audio_max = np.abs(audio_16k).max() / 0.95
        if audio_max > 1:
            audio_16k = audio_16k / audio_max

        # Compute input RMS for loudness matching later
        input_rms = np.sqrt(np.mean(audio_16k ** 2))

        # Add padding to avoid edge artifacts
        audio_pad = np.pad(audio_16k, (self.t_pad, self.t_pad), mode="reflect")
        logger.debug(f"vc_single: padded {len(audio_pad)} samples (pad={self.t_pad})")
        audio_pad_tensor = torch.from_numpy(audio_pad).float().to(self.device)
        if self.is_half:
            audio_pad_tensor = audio_pad_tensor.half()

        # --- Step 1: Extract F0 (pitch) ---
        f0 = self._extract_f0(audio_pad, f0_up_key, rmvpe_model, filter_radius)

        # --- Step 2: Extract HuBERT features ---
        feats = self._extract_hubert_features(hubert_model, audio_pad_tensor)

        # --- Step 3: Save original features for consonant protection (before FAISS) ---
        feats0 = feats.clone() if protect < 0.5 else None

        # --- Step 4: Optional FAISS index retrieval ---
        # Must happen BEFORE interpolation to match original RVC
        if index is not None and index_rate > 0 and FAISS_AVAILABLE:
            feats = self._apply_faiss_retrieval(feats, index, index_rate)
        elif index_rate > 0 and not FAISS_AVAILABLE:
            logger.debug("Skipping FAISS retrieval (faiss-cpu not installed)")

        # --- Step 5: Interpolate features 2x ---
        # HuBERT outputs at 50fps (hop=320) but the synthesizer expects 100fps
        # (hop=160 at 16kHz). Default mode (linear) for smooth interpolation.
        feats = F.interpolate(
            feats.permute(0, 2, 1),  # [B, dim, T] for interpolate
            scale_factor=2,
        ).permute(0, 2, 1)  # back to [B, T, dim]

        # Also interpolate the saved original features for consonant protection
        if feats0 is not None:
            feats0 = F.interpolate(
                feats0.permute(0, 2, 1),
                scale_factor=2,
            ).permute(0, 2, 1)

        # Align feature and F0 lengths
        p_len = min(feats.shape[1], f0.shape[0])
        feats = feats[:, :p_len, :]
        f0 = f0[:p_len]
        if feats0 is not None:
            feats0 = feats0[:, :p_len, :]

        logger.debug(
            f"vc_single: feats={feats.shape}, f0={f0.shape}, p_len={p_len}, "
            f"voiced_frames={int((f0 > 0).sum())}/{len(f0)}"
        )

        # --- Step 6: Prepare tensors for synthesizer ---
        pitch, pitchf = self._encode_pitch(f0, p_len)
        phone_lengths = torch.LongTensor([p_len]).to(self.device)

        # --- Step 7: Apply consonant protection ---
        # For unvoiced frames (f0=0), blend modified features with original
        # to preserve consonant clarity. Voiced frames use full conversion.
        if feats0 is not None:
            pitchff = pitchf.clone()
            pitchff[pitchf > 0] = 1       # voiced: use converted features
            pitchff[pitchf < 1] = protect  # unvoiced: mostly keep original
            pitchff = pitchff.unsqueeze(-1)  # [1, T] -> [1, T, 1] for broadcast
            feats = feats * pitchff + feats0 * (1 - pitchff)
            feats = feats.to(feats0.dtype)

        # --- Step 8: Run VITS synthesizer ---
        audio_output = self._run_synthesizer(
            net_g, sid, feats, pitch, pitchf, phone_lengths, p_len
        )
        logger.debug(
            f"vc_single: synth output {len(audio_output)} samples "
            f"({len(audio_output)/self.tgt_sr:.2f}s @ {self.tgt_sr}Hz)"
        )

        # Remove padding from output
        pad_samples = self.t_pad_tgt
        if 2 * pad_samples < len(audio_output):
            audio_output = audio_output[pad_samples:-pad_samples]
        elif pad_samples < len(audio_output):
            # Output is shorter than expected — take the middle portion
            mid = len(audio_output) // 2
            half = (len(audio_output) - 2 * pad_samples) // 2
            if half > 0:
                audio_output = audio_output[mid - half:mid + half]
            else:
                logger.warning(
                    f"Output ({len(audio_output)}) too short to remove padding "
                    f"({pad_samples} per side), returning unpadded"
                )

        # --- Step 6: RMS loudness matching ---
        if rms_mix_rate > 0:
            audio_output = match_rms(audio_output, input_rms, rms_mix_rate)

        # --- Step 7: Optional output resampling ---
        output_sr = self.tgt_sr
        if resample_sr > 0 and resample_sr != self.tgt_sr:
            try:
                import librosa
                audio_output = librosa.resample(
                    audio_output, orig_sr=self.tgt_sr, target_sr=resample_sr
                )
                output_sr = resample_sr
            except ImportError:
                logger.warning("Cannot resample output: librosa not available")

        # Clip to prevent clipping
        audio_output = np.clip(audio_output, -1.0, 1.0)

        return audio_output

    def _extract_f0(
        self,
        audio_pad: np.ndarray,
        f0_up_key: int,
        rmvpe_model,
        filter_radius: int,
    ) -> np.ndarray:
        """Extract and process F0 contour.

        Args:
            audio_pad: Padded 16kHz audio.
            f0_up_key: Semitone shift.
            rmvpe_model: RMVPE model instance.
            filter_radius: Median filter radius.

        Returns:
            F0 array in Hz.
        """
        # Extract F0 using RMVPE
        f0 = rmvpe_model.infer_from_audio(audio_pad, thred=0.03)

        # Apply semitone shift: f0 * 2^(semitones/12)
        if f0_up_key != 0:
            f0 *= 2 ** (f0_up_key / 12)

        # Apply median filter for pitch smoothing
        if filter_radius > 1 and HAS_SCIPY:
            f0_filtered = scipy_signal.medfilt(f0, kernel_size=filter_radius * 2 + 1)
            # Only apply filter to voiced regions (preserve unvoiced)
            voiced = f0 > 0
            f0[voiced] = f0_filtered[voiced]

        return f0

    def _extract_hubert_features(
        self, hubert_model, audio_tensor: torch.Tensor
    ) -> torch.Tensor:
        """Extract HuBERT content features from audio.

        Args:
            hubert_model: Loaded HuBERT model.
            audio_tensor: Audio tensor on device.

        Returns:
            Feature tensor [1, T, dim] where dim is 256 (v1) or 768 (v2).
        """
        # HuBERT expects [B, T] input at 16kHz
        if audio_tensor.dim() == 1:
            audio_tensor = audio_tensor.unsqueeze(0)

        # Pad to minimum length
        if audio_tensor.shape[1] < 400:
            audio_tensor = F.pad(audio_tensor, (0, 400 - audio_tensor.shape[1]))

        # Extract features
        with torch.no_grad():
            feats = hubert_model(audio_tensor)
            if hasattr(feats, 'last_hidden_state'):
                feats = feats.last_hidden_state
            elif isinstance(feats, tuple):
                feats = feats[0]

        # Ensure 3D: [B, T, dim]
        if feats.dim() == 2:
            feats = feats.unsqueeze(0)

        return feats.float()

    def _apply_faiss_retrieval(
        self,
        feats: torch.Tensor,
        index,
        index_rate: float,
    ) -> torch.Tensor:
        """Apply FAISS index retrieval to blend speaker features.

        Args:
            feats: HuBERT features [1, T, dim].
            index: FAISS index.
            index_rate: Blend rate (0.0-1.0).

        Returns:
            Blended features tensor.
        """
        try:
            npy = feats[0].cpu().numpy()
            if npy.dtype != np.float32:
                npy = npy.astype(np.float32)

            # Query FAISS index
            score, ix = index.search(npy, k=8)

            # Weighted average of retrieved features
            weight = np.square(1.0 / score)
            weight /= weight.sum(axis=1, keepdims=True)

            # Reconstruct features from index
            npy_result = np.zeros_like(npy)
            for i in range(npy.shape[0]):
                for j in range(8):
                    idx = ix[i, j]
                    if idx >= 0:
                        npy_result[i] += weight[i, j] * index.reconstruct(int(idx))

            # Blend original and retrieved features
            npy = (1 - index_rate) * npy + index_rate * npy_result
            feats = torch.from_numpy(npy).unsqueeze(0).to(self.device)
            if self.is_half:
                feats = feats.half()
            else:
                feats = feats.float()

        except Exception as e:
            logger.warning(f"FAISS retrieval failed (continuing without): {e}")

        return feats

    def _encode_pitch(self, f0: np.ndarray, p_len: int):
        """Encode F0 into pitch tensors for the synthesizer.

        Args:
            f0: F0 array in Hz.
            p_len: Target length.

        Returns:
            Tuple of (pitch_coarse [1, T], pitchf [1, T]).
        """
        # Convert F0 to mel scale for coarse pitch encoding
        f0_mel = 1127 * np.log(1 + f0 / 700)
        f0_mel[f0_mel > 0] = (f0_mel[f0_mel > 0] - self.f0_mel_min) * 254 / (
            self.f0_mel_max - self.f0_mel_min
        ) + 1
        f0_mel[f0_mel <= 1] = 1
        f0_mel[f0_mel > 255] = 255
        f0_coarse = np.rint(f0_mel).astype(int)

        pitch = torch.LongTensor(f0_coarse[:p_len]).unsqueeze(0).to(self.device)
        pitchf = torch.FloatTensor(f0[:p_len]).unsqueeze(0).to(self.device)

        return pitch, pitchf

    def _run_synthesizer(
        self,
        net_g,
        sid: torch.Tensor,
        feats: torch.Tensor,
        pitch: torch.Tensor,
        pitchf: torch.Tensor,
        phone_lengths: torch.Tensor,
        p_len: int,
        skip_head: int = None,
        return_length: int = None,
    ) -> np.ndarray:
        """Run VITS synthesizer forward pass.

        Args:
            net_g: Synthesizer model.
            sid: Speaker ID tensor.
            feats: HuBERT features [1, T, dim].
            pitch: Coarse pitch [1, T].
            pitchf: Continuous F0 [1, T].
            phone_lengths: Feature lengths [1].
            p_len: Sequence length.
            skip_head: Optional frames to skip (streaming mode).
            return_length: Optional frames to generate (streaming mode).

        Returns:
            Generated audio as float32 numpy array.
        """
        # Forward pass — noise is generated internally by the synthesizer
        # with 0.66666 scaling factor matching original RVC
        audio_output = net_g.infer(
            feats, phone_lengths, pitch, pitchf, sid,
            skip_head=skip_head, return_length=return_length,
        )

        # Handle both old return format (tuple) and direct tensor
        if isinstance(audio_output, tuple):
            audio_output = audio_output[0]

        # Convert to numpy
        audio_np = audio_output[0, 0].float().cpu().numpy()

        return audio_np

    @torch.no_grad()
    def vc_streaming(
        self,
        hubert_model,
        net_g,
        sid,
        audio_16k: np.ndarray,
        block_samples: int,
        f0_up_key: int,
        rmvpe_model,
        pitch_cache: np.ndarray = None,
        pitchf_cache: np.ndarray = None,
        sola_extra_frames: int = 4,
        index=None,
        index_rate: float = 0.75,
        filter_radius: int = 3,
        protect: float = 0.33,
    ):
        """Streaming voice conversion for real-time mic processing.

        Unlike vc_single which pads and processes the whole clip, this method:
        - Accepts a rolling buffer (context + new block) at 16kHz
        - Runs HuBERT on the full context for good features
        - Runs RMVPE only on the new block + small overlap (much faster)
        - Uses skip_head/return_length to only synthesize the block portion
        - Maintains a pitch cache across calls

        Args:
            hubert_model: Loaded HuBERT model.
            net_g: Loaded VITS synthesizer.
            sid: Speaker ID tensor.
            audio_16k: Full rolling buffer at 16kHz (context + block).
            block_samples: Number of NEW samples at the end of the buffer.
            f0_up_key: Semitone shift.
            rmvpe_model: Loaded RMVPE model.
            pitch_cache: Previous pitch values (numpy int array) or None.
            pitchf_cache: Previous F0 values (numpy float array) or None.
            sola_extra_frames: Extra frames for SOLA crossfading.
            index: FAISS index (optional).
            index_rate: FAISS blend rate.
            filter_radius: Median filter radius for pitch.
            protect: Consonant protection.

        Returns:
            Tuple of (converted_audio_np, pitch_cache, pitchf_cache, output_sr)
            where converted_audio is at tgt_sr and includes SOLA overlap region.
        """
        import time as _time

        total_samples = len(audio_16k)

        # Feature frame dimensions (after 2x interpolation: 100fps = 160 samples/frame)
        total_frames = total_samples // 160
        block_frames = block_samples // 160
        return_frames = block_frames + sola_extra_frames
        # skip_head = everything before (block + sola_extra) in the buffer
        skip_frames = total_frames - return_frames
        if skip_frames < 0:
            skip_frames = 0
            return_frames = total_frames

        logger.debug(
            f"vc_streaming: total={total_samples} total_fr={total_frames} "
            f"block={block_samples} block_fr={block_frames} "
            f"skip={skip_frames} ret={return_frames}"
        )

        # --- Preprocess audio ---
        audio = audio_16k.copy().astype(np.float32)

        # High-pass filter
        if HAS_SCIPY and _bh is not None:
            audio = scipy_signal.filtfilt(_bh, _ah, audio).astype(np.float32)

        # Normalize amplitude
        audio_max = np.abs(audio).max() / 0.95
        if audio_max > 1:
            audio = audio / audio_max

        audio_tensor = torch.from_numpy(audio).float().to(self.device)
        if self.is_half:
            audio_tensor = audio_tensor.half()

        # --- Step 1: HuBERT features on full context ---
        t0 = _time.monotonic()
        feats = self._extract_hubert_features(hubert_model, audio_tensor)
        t_hubert = _time.monotonic() - t0

        # --- Step 2: FAISS on new portion only (skip // 2 onwards) ---
        t0 = _time.monotonic()
        skip_hubert = skip_frames // 2  # HuBERT frames (before 2x interp)
        if index is not None and index_rate > 0 and FAISS_AVAILABLE:
            # Only apply FAISS to the new portion for speed
            npy = feats[0][skip_hubert:].cpu().numpy()
            if npy.dtype != np.float32:
                npy = npy.astype(np.float32)
            try:
                score, ix = index.search(npy, k=8)
                weight = np.square(1.0 / score)
                weight /= weight.sum(axis=1, keepdims=True)
                npy_result = np.zeros_like(npy)
                for i in range(npy.shape[0]):
                    for j in range(8):
                        idx = ix[i, j]
                        if idx >= 0:
                            npy_result[i] += weight[i, j] * index.reconstruct(int(idx))
                npy = (1 - index_rate) * npy + index_rate * npy_result
                feats[0][skip_hubert:] = torch.from_numpy(npy).to(feats.device).to(feats.dtype)
            except Exception as e:
                logger.warning(f"FAISS streaming retrieval failed: {e}")
        t_faiss = _time.monotonic() - t0

        # --- Step 3: F0 on recent portion only ---
        t0 = _time.monotonic()
        # RMVPE only needs the new block + ~800 samples context (50ms)
        f0_input_samples = block_samples + 800
        # Pad to nearest RMVPE-friendly boundary (5120-sample aligned)
        f0_input_aligned = 5120 * ((f0_input_samples - 1) // 5120 + 1) - 160
        f0_input_aligned = min(f0_input_aligned, total_samples)
        f0_audio = audio[-f0_input_aligned:]

        f0_new = rmvpe_model.infer_from_audio(f0_audio, thred=0.03)
        if f0_up_key != 0:
            f0_new *= 2 ** (f0_up_key / 12)

        # Trim edges (RMVPE has edge artifacts)
        if len(f0_new) > 4:
            f0_usable = f0_new[3:-1]
        else:
            f0_usable = f0_new

        # Update pitch cache
        if pitch_cache is None or pitchf_cache is None:
            # First call: initialize cache for full context (zeros = unvoiced)
            pitch_cache = np.zeros(total_frames, dtype=np.float64)
            pitchf_cache = np.zeros(total_frames, dtype=np.float64)
            # Fill the end with extracted pitch
            n_fill = min(len(f0_usable), total_frames)
            pitch_cache[-n_fill:] = f0_usable[-n_fill:]
            pitchf_cache[-n_fill:] = f0_usable[-n_fill:]
        else:
            # Shift cache left by block_frames, append new pitch
            shift = block_frames
            if shift < len(pitch_cache):
                pitch_cache[:-shift] = pitch_cache[shift:]
                pitchf_cache[:-shift] = pitchf_cache[shift:]
            n_fill = min(len(f0_usable), shift)
            pitch_cache[-n_fill:] = f0_usable[-n_fill:]
            pitchf_cache[-n_fill:] = f0_usable[-n_fill:]

        t_f0 = _time.monotonic() - t0

        # --- Step 4: Prepare features for synthesis ---
        t0 = _time.monotonic()

        # Save original features for consonant protection
        feats0 = feats.clone() if protect < 0.5 else None

        # Interpolate features 2x (50fps → 100fps)
        feats = F.interpolate(
            feats.permute(0, 2, 1), scale_factor=2
        ).permute(0, 2, 1)

        if feats0 is not None:
            feats0 = F.interpolate(
                feats0.permute(0, 2, 1), scale_factor=2
            ).permute(0, 2, 1)

        # Align lengths
        p_len = min(feats.shape[1], total_frames)
        feats = feats[:, :p_len, :]
        if feats0 is not None:
            feats0 = feats0[:, :p_len, :]

        # Encode pitch from cache
        pitch, pitchf_tensor = self._encode_pitch(pitchf_cache[:p_len], p_len)

        # Consonant protection
        if feats0 is not None:
            pitchff = pitchf_tensor.clone()
            pitchff[pitchf_tensor > 0] = 1
            pitchff[pitchf_tensor < 1] = protect
            pitchff = pitchff.unsqueeze(-1)
            feats = feats * pitchff + feats0 * (1 - pitchff)
            feats = feats.to(feats0.dtype)

        phone_lengths = torch.LongTensor([p_len]).to(self.device)

        # Clamp return_length to available frames
        actual_return = min(return_frames, p_len - skip_frames)
        if actual_return <= 0:
            actual_return = block_frames

        # --- Step 5: Synthesize with skip_head/return_length ---
        skip_head_t = torch.LongTensor([skip_frames])
        return_length_t = torch.LongTensor([actual_return])

        audio_output = self._run_synthesizer(
            net_g, sid, feats, pitch, pitchf_tensor, phone_lengths, p_len,
            skip_head=skip_head_t, return_length=return_length_t,
        )
        t_synth = _time.monotonic() - t0

        logger.debug(
            f"vc_streaming: hubert={t_hubert:.3f}s faiss={t_faiss:.3f}s "
            f"f0={t_f0:.3f}s synth={t_synth:.3f}s "
            f"total={t_hubert+t_faiss+t_f0+t_synth:.3f}s "
            f"output={len(audio_output)} samples"
        )

        return audio_output, pitch_cache, pitchf_cache, self.tgt_sr


def _import_hubert_model():
    """Import HubertModel, bypassing transformers lazy loading if needed.

    transformers caches torch availability at import time. In the exe,
    torch is loaded later from the external venv, so transformers replaces
    HubertModel with a DummyObject. Patching the flag doesn't help because
    the class is already bound. We bypass this by importing directly from
    the modeling submodule.
    """
    try:
        from transformers import HubertModel
        # Check if it's a real class or a DummyObject
        if hasattr(HubertModel, '_backends'):
            raise ImportError("HubertModel is a DummyObject")
        return HubertModel
    except (ImportError, RuntimeError):
        pass

    # Direct import bypasses lazy loading / DummyObject
    logger.debug("Bypassing transformers lazy loading for HubertModel")
    from transformers.models.hubert.modeling_hubert import HubertModel
    return HubertModel


def load_hubert(model_path: str, device: torch.device):
    """Load ContentVec model for feature extraction.

    ContentVec is a HuBERT model fine-tuned for voice conversion.
    It produces speaker-disentangled features that are used by the
    VITS synthesizer to generate speech in the target voice.

    IMPORTANT: RVC models are trained with ContentVec features, NOT
    vanilla facebook/hubert-base-ls960. Using the wrong model produces
    gibberish output.

    Args:
        model_path: Path to ContentVec model directory.
        device: Torch compute device.

    Returns:
        Loaded ContentVec model.
    """
    HubertModel = _import_hubert_model()

    logger.debug(f"Loading ContentVec model from {model_path}")

    # Load from transformers model directory (config.json + pytorch_model.bin)
    # We load manually to bypass transformers' torch version check (CVE-2025-32434)
    # which blocks torch.load even with weights_only=False on torch < 2.6.
    try:
        config_path = os.path.join(model_path, 'config.json')
        weights_path = os.path.join(model_path, 'pytorch_model.bin')
        safetensors_path = os.path.join(model_path, 'model.safetensors')

        # Prefer safetensors if available
        if os.path.exists(safetensors_path):
            logger.debug("Loading ContentVec via safetensors")
            model = HubertModel.from_pretrained(model_path, local_files_only=True)
        elif os.path.exists(weights_path):
            # Manual load: create model from config, load state dict directly
            logger.debug("Loading ContentVec manually (bypass torch version check)")
            from transformers import HubertConfig
            config = HubertConfig.from_pretrained(model_path, local_files_only=True)
            model = HubertModel(config)
            state_dict = torch.load(weights_path, map_location='cpu', weights_only=False)
            model.load_state_dict(state_dict, strict=False)
        else:
            raise FileNotFoundError(f"No model weights found in {model_path}")

        model = model.eval().to(device)
        logger.debug("ContentVec loaded successfully")
        return model
    except Exception as e:
        logger.error(f"Failed to load ContentVec from {model_path}: {e}")
        raise RuntimeError(
            f"Could not load ContentVec model from {model_path}. "
            "Try re-downloading the base models."
        ) from e


def load_synthesizer(
    model_path: str, device: torch.device
) -> tuple:
    """Load RVC voice synthesizer model from .pth file.

    Detects v1 vs v2 from the checkpoint's config key.

    Args:
        model_path: Path to the .pth voice model file.
        device: Torch compute device.

    Returns:
        Tuple of (model, target_sr, version) where:
        - model: Loaded synthesizer model.
        - target_sr: Output sample rate.
        - version: 'v1' or 'v2'.
    """
    logger.debug(f"Loading RVC voice model from {model_path}")

    cpt = torch.load(model_path, map_location="cpu", weights_only=False)

    # Extract config from checkpoint
    tgt_sr = cpt.get("config", [0] * 18)[-1]
    if tgt_sr not in (32000, 40000, 48000):
        # Fallback: try common sample rates from config list
        config = cpt.get("config", [])
        if len(config) >= 18:
            tgt_sr = config[-1]
        else:
            tgt_sr = 40000  # Default v1 rate
            logger.warning(f"Could not determine target SR, defaulting to {tgt_sr}")

    # Detect v1 vs v2 from config
    config = cpt.get("config", [])

    # v2 models have 768 as the hidden size, v1 has 256
    # The config is typically a list of hyperparameters
    # Check for f0 flag in the checkpoint
    f0 = cpt.get("f0", 1)

    # Determine version by examining weight keys or config
    weight = cpt.get("weight", {})
    version = "v1"

    # v2 models have enc_p.emb_phone with input dim 768
    for key in weight:
        if "emb_phone" in key and "weight" in key:
            shape = weight[key].shape
            if shape[-1] == 768 or (len(shape) > 0 and shape[0] == 768):
                version = "v2"
            break

    logger.debug(f"Detected RVC {version} model, target_sr={tgt_sr}, f0={f0}")

    # Build model with config parameters
    if len(config) >= 18:
        # Full config available
        model_config = {
            "spec_channels": config[0] if len(config) > 0 else 1025,
            "segment_size": config[1] if len(config) > 1 else 32,
            "inter_channels": config[2] if len(config) > 2 else 192,
            "hidden_channels": config[3] if len(config) > 3 else 192,
            "filter_channels": config[4] if len(config) > 4 else 768,
            "n_heads": config[5] if len(config) > 5 else 2,
            "n_layers": config[6] if len(config) > 6 else 6,
            "kernel_size": config[7] if len(config) > 7 else 3,
            "p_dropout": config[8] if len(config) > 8 else 0,
            "resblock": config[9] if len(config) > 9 else "1",
            "resblock_kernel_sizes": config[10] if len(config) > 10 else [3, 7, 11],
            "resblock_dilation_sizes": config[11] if len(config) > 11 else [[1, 3, 5], [1, 3, 5], [1, 3, 5]],
            "upsample_rates": config[12] if len(config) > 12 else [10, 10, 2, 2],
            "upsample_initial_channel": config[13] if len(config) > 13 else 512,
            "upsample_kernel_sizes": config[14] if len(config) > 14 else [16, 16, 4, 4],
            "spk_embed_dim": config[15] if len(config) > 15 else 109,
            "gin_channels": config[16] if len(config) > 16 else 256,
            "sr": config[17] if len(config) > 17 else tgt_sr,
        }
    else:
        # Use defaults
        model_config = {
            "spec_channels": 1025,
            "segment_size": 32,
            "inter_channels": 192,
            "hidden_channels": 192,
            "filter_channels": 768,
            "n_heads": 2,
            "n_layers": 6,
            "kernel_size": 3,
            "p_dropout": 0,
            "resblock": "1",
            "resblock_kernel_sizes": [3, 7, 11],
            "resblock_dilation_sizes": [[1, 3, 5], [1, 3, 5], [1, 3, 5]],
            "upsample_rates": [10, 10, 2, 2],
            "upsample_initial_channel": 512,
            "upsample_kernel_sizes": [16, 16, 4, 4],
            "spk_embed_dim": 109,
            "gin_channels": 256,
            "sr": tgt_sr,
        }

    # Instantiate model
    if version == "v2":
        net_g = SynthesizerTrnMs768NSFsid(**model_config)
    else:
        net_g = SynthesizerTrnMs256NSFsid(**model_config)

    # Load weights
    net_g.load_state_dict(weight, strict=False)
    net_g = net_g.eval().to(device)

    # Remove weight_norm for inference. This is critical for DirectML where
    # _weight_norm_interface falls back to CPU causing ~17x slowdown.
    # Use safe removal that handles missing hooks gracefully.
    _safe_remove_weight_norm(net_g)
    logger.debug("Synthesizer weight_norm removed for inference")

    return net_g, tgt_sr, version


def _safe_remove_weight_norm(model):
    """Remove weight_norm from all submodules, ignoring layers where it's missing.

    Handles both old-style (torch.nn.utils.weight_norm) and new-style
    (torch.nn.utils.parametrizations.weight_norm) hooks.
    """
    import torch
    from torch.nn.utils import remove_weight_norm as _remove_wn

    removed = 0
    for module in model.modules():
        # Try old-style removal
        try:
            _remove_wn(module)
            removed += 1
            continue
        except (ValueError, AttributeError):
            pass

        # Try new-style parametrization removal
        try:
            if hasattr(torch.nn.utils, 'parametrize') and \
               torch.nn.utils.parametrize.is_parametrized(module, 'weight'):
                torch.nn.utils.parametrize.remove_parametrizations(module, 'weight')
                removed += 1
        except (ValueError, AttributeError, RuntimeError):
            pass

    logger.debug(f"Removed weight_norm from {removed} modules")
