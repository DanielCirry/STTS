"""
RVC audio loading and resampling utilities.
"""

import logging
import numpy as np

logger = logging.getLogger('stts.rvc.audio')


def load_audio_from_numpy(audio: np.ndarray, sr: int, target_sr: int = 16000) -> np.ndarray:
    """Load and resample audio from a numpy array.

    Args:
        audio: Float32 numpy array of audio samples.
        sr: Source sample rate.
        target_sr: Target sample rate (default 16000 for HuBERT).

    Returns:
        Resampled float32 numpy array at target_sr.
    """
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)

    # Ensure mono
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    # Resample if needed
    if sr != target_sr:
        try:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
        except ImportError:
            # Fallback to scipy if librosa is not available
            from scipy.signal import resample_poly
            from math import gcd
            g = gcd(sr, target_sr)
            audio = resample_poly(audio, target_sr // g, sr // g)
            logger.warning("librosa not available, using scipy for resampling")

    return audio


def compute_rms(audio: np.ndarray, frame_length: int = 2048, hop_length: int = 512) -> np.ndarray:
    """Compute RMS energy of audio signal.

    Args:
        audio: Float32 audio array.
        frame_length: Analysis frame length.
        hop_length: Hop length between frames.

    Returns:
        RMS energy array.
    """
    # Pad audio
    pad_length = frame_length // 2
    audio_padded = np.pad(audio, (pad_length, pad_length), mode='reflect')

    n_frames = 1 + (len(audio_padded) - frame_length) // hop_length
    rms = np.zeros(n_frames)

    for i in range(n_frames):
        start = i * hop_length
        frame = audio_padded[start:start + frame_length]
        rms[i] = np.sqrt(np.mean(frame ** 2))

    return rms


def match_rms(source_audio: np.ndarray, target_rms: float,
              mix_rate: float = 0.25) -> np.ndarray:
    """Match the RMS loudness of source audio to a target level.

    Args:
        source_audio: Audio to adjust.
        target_rms: Target RMS level.
        mix_rate: Blend between original (0.0) and matched (1.0) loudness.

    Returns:
        Loudness-matched audio.
    """
    source_rms = np.sqrt(np.mean(source_audio ** 2))
    if source_rms < 1e-6:
        return source_audio

    ratio = target_rms / source_rms
    matched = source_audio * ratio

    # Blend between original and matched
    return source_audio * (1.0 - mix_rate) + matched * mix_rate
