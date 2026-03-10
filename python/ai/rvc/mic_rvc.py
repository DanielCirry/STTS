"""
Real-time microphone voice conversion via RVC.

Architecture:
- Uses separate sd.InputStream + sd.OutputStream for decoupled I/O
- A processing thread reads from input queue, runs RVC, writes to output queue
- The output stream callback pulls from the output queue (non-blocking)
- This avoids blocking the audio callback with heavy inference, which
  caused streams to abort after one block on Windows
"""

import logging
import queue
import sys
import threading
import time
from math import gcd
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger('stts.rvc.mic_rvc')

# SOLA settings matching working RVC defaults
SOLA_BUFFER_MS = 40
SOLA_SEARCH_MS = 10


class MicRVCProcessor:
    """Real-time mic voice conversion with decoupled I/O streams.

    Uses separate input/output streams and a processing thread to avoid
    blocking the audio callback with heavy RVC inference.
    """

    def __init__(self, rvc_postprocessor):
        self._rvc = rvc_postprocessor
        self._input_stream = None
        self._output_stream = None
        self._running = False

        # Device config
        self._input_device_id: Optional[int] = None
        self._output_device_id: Optional[int] = None
        self._device_sr: int = 48000

        # Timing
        self._block_time: float = 0.5
        self._context_time: float = 1.0

        # Frame sizes (computed in start)
        self._zc: int = 0
        self._block_frame: int = 0
        self._block_frame_16k: int = 0

        # Buffers
        self._input_wav: Optional[np.ndarray] = None  # rolling at device_sr

        # Resampling
        self._resample_up: int = 1
        self._resample_down: int = 3

        # SOLA state
        self._sola_buffer: Optional[np.ndarray] = None
        self._sola_buffer_frame: int = 0
        self._sola_search_frame: int = 0
        self._fade_in: Optional[np.ndarray] = None
        self._fade_out: Optional[np.ndarray] = None

        # Pipeline params
        self._skip_head: int = 0
        self._return_length: int = 0
        self._sola_extra_frames: int = 0

        # Pitch cache
        self._pitch_cache: Optional[np.ndarray] = None
        self._pitchf_cache: Optional[np.ndarray] = None

        # Silence
        self._silence_threshold: float = 0.003

        # Channels (stereo on Windows, mono on macOS)
        self._channels: int = 1

        # Queues for decoupled processing
        self._input_queue: queue.Queue = queue.Queue(maxsize=10)
        self._output_queue: queue.Queue = queue.Queue(maxsize=10)
        self._process_thread: Optional[threading.Thread] = None

        # Latency tracking
        self._latency_warned: bool = False
        self._consecutive_slow: int = 0

        # Callbacks
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_status: Optional[Callable[[str, dict], None]] = None

    @property
    def is_running(self) -> bool:
        return self._running

    def feed_audio(self, chunk: np.ndarray):
        """Backward compat — unused when sd streams are active."""
        pass

    def start(self, output_device_id: Optional[int] = None,
              input_device_id: Optional[int] = None):
        """Start real-time mic voice conversion with decoupled streams."""
        if self._running:
            logger.warning("Mic RVC already running")
            return

        import sounddevice as sd

        self._output_device_id = output_device_id
        self._input_device_id = input_device_id

        # Always use 48kHz for audio devices — standard rate supported by all hardware.
        # RVC output gets resampled from model's tgt_sr to 48kHz in _process_loop.
        self._device_sr = 48000

        # Frame alignment unit (10ms at device SR)
        self._zc = self._device_sr // 100

        # Block frame aligned to zc
        self._block_frame = int(np.round(
            self._block_time * self._device_sr / self._zc
        )) * self._zc
        self._block_frame_16k = 160 * self._block_frame // self._zc

        # SOLA parameters at device SR
        crossfade_frame = int(np.round(
            SOLA_BUFFER_MS / 1000 * self._device_sr / self._zc
        )) * self._zc
        self._sola_buffer_frame = min(crossfade_frame, 4 * self._zc)
        self._sola_search_frame = self._zc

        # Context
        extra_frame = int(np.round(
            self._context_time * self._device_sr / self._zc
        )) * self._zc

        # Total input buffer at device SR
        total_frame = (extra_frame + crossfade_frame +
                       self._sola_search_frame + self._block_frame)

        # skip_head / return_length in feature frames (100fps after 2x interp)
        self._return_length = (
            (self._block_frame + crossfade_frame + self._sola_search_frame)
            // self._zc
        )
        self._skip_head = total_frame // self._zc - self._return_length
        self._sola_extra_frames = (
            (crossfade_frame + self._sola_search_frame) // self._zc
        )

        # Resampling ratios (device_sr -> 16kHz)
        g = gcd(self._device_sr, 16000)
        self._resample_up = 16000 // g
        self._resample_down = self._device_sr // g

        # Initialize buffers
        self._input_wav = np.zeros(total_frame, dtype=np.float32)

        # Fade windows
        self._fade_in = np.sin(
            0.5 * np.pi * np.linspace(
                0, 1, self._sola_buffer_frame, dtype=np.float32
            )
        ) ** 2
        self._fade_out = 1.0 - self._fade_in
        self._sola_buffer = np.zeros(self._sola_buffer_frame, dtype=np.float32)

        # Pitch cache
        self._pitch_cache = None
        self._pitchf_cache = None

        # Determine channels based on device capability
        import sounddevice as sd
        try:
            dev_info = sd.query_devices(self._input_device_id if self._input_device_id is not None else sd.default.device[0])
            max_input_ch = dev_info.get('max_input_channels', 1)
            # Use stereo on Windows if device supports it, else mono
            if sys.platform == "darwin":
                self._channels = 1
            else:
                self._channels = min(2, max_input_ch)
            logger.info(f"[mic_rvc] Input device '{dev_info.get('name', '?')}' max_input_channels={max_input_ch}, using channels={self._channels}")
        except Exception as e:
            self._channels = 1  # Safe fallback to mono
            logger.warning(f"[mic_rvc] Could not query input device channels ({e}), falling back to mono")

        # Clear queues
        while not self._input_queue.empty():
            try:
                self._input_queue.get_nowait()
            except queue.Empty:
                break
        while not self._output_queue.empty():
            try:
                self._output_queue.get_nowait()
            except queue.Empty:
                break

        self._running = True

        # Start processing thread
        self._process_thread = threading.Thread(
            target=self._process_loop, daemon=True, name='mic-rvc-process'
        )
        self._process_thread.start()

        # Open separate input and output streams
        try:
            self._input_stream = sd.InputStream(
                device=self._input_device_id,
                samplerate=self._device_sr,
                blocksize=self._block_frame,
                channels=self._channels,
                dtype='float32',
                callback=self._input_callback,
                finished_callback=lambda: logger.warning("Mic RVC INPUT stream stopped unexpectedly") if self._running else None,
            )
            self._output_stream = sd.OutputStream(
                device=self._output_device_id,
                samplerate=self._device_sr,
                blocksize=self._block_frame,
                channels=self._channels,
                dtype='float32',
                callback=self._output_callback,
                finished_callback=lambda: logger.warning("Mic RVC OUTPUT stream stopped unexpectedly") if self._running else None,
            )
            self._input_stream.start()
            self._output_stream.start()
            logger.debug(
                f"Mic RVC started "
                f"(sr={self._device_sr}, block={self._block_frame} "
                f"({self._block_time}s), channels={self._channels}, "
                f"sola_buf={self._sola_buffer_frame}, "
                f"skip={self._skip_head}, ret={self._return_length})"
            )
        except Exception as e:
            self._running = False
            logger.error(f"Failed to open audio streams: {e}")
            if self.on_error:
                self.on_error(f"Failed to open audio streams: {e}")

    def stop(self):
        """Stop real-time mic voice conversion."""
        logger.info("[mic_rvc] stop() called, _running=%s", self._running)
        self._running = False

        # Drain input queue so process thread can unblock quickly
        while not self._input_queue.empty():
            try:
                self._input_queue.get_nowait()
            except queue.Empty:
                break

        if self._input_stream:
            try:
                logger.debug("[mic_rvc] Stopping input stream")
                self._input_stream.stop()
                self._input_stream.close()
            except Exception as e:
                logger.debug("[mic_rvc] Input stream stop error: %s", e)
            self._input_stream = None
        if self._output_stream:
            try:
                logger.debug("[mic_rvc] Stopping output stream")
                self._output_stream.stop()
                self._output_stream.close()
            except Exception as e:
                logger.debug("[mic_rvc] Output stream stop error: %s", e)
            self._output_stream = None
        if self._process_thread:
            logger.debug("[mic_rvc] Joining process thread (timeout=5s)")
            self._process_thread.join(timeout=5.0)
            if self._process_thread.is_alive():
                logger.warning("[mic_rvc] Process thread did not stop within 5s — abandoning")
            else:
                logger.debug("[mic_rvc] Process thread joined successfully")
            self._process_thread = None
        self._input_wav = None
        self._pitch_cache = None
        self._pitchf_cache = None
        self._sola_buffer = None
        self._latency_warned = False
        self._consecutive_slow = 0
        logger.info("[mic_rvc] Mic RVC stopped")

    def set_output_device(self, device_id: Optional[int]):
        """Change output device (requires restart)."""
        self._output_device_id = device_id
        if self._running:
            inp = self._input_device_id
            self.stop()
            self.start(device_id, inp)

    def set_buffer_duration(self, seconds: float):
        """Adjust block duration (requires restart)."""
        self._block_time = max(0.2, min(2.0, seconds))
        if self._running:
            out = self._output_device_id
            inp = self._input_device_id
            self.stop()
            self.start(out, inp)
        logger.debug(f"Mic RVC block duration set to {self._block_time}s")

    def set_context_time(self, seconds: float):
        """Adjust extra inference context (requires restart). More = better quality, more latency."""
        self._context_time = max(0.2, min(3.0, seconds))
        if self._running:
            out = self._output_device_id
            inp = self._input_device_id
            self.stop()
            self.start(out, inp)
        logger.debug(f"Mic RVC context time set to {self._context_time}s")

    def set_silence_threshold(self, threshold: float):
        """Adjust silence/response threshold. Below this RMS, audio is passed through as silence."""
        self._silence_threshold = max(0.0, min(0.05, threshold))
        logger.debug(f"Mic RVC silence threshold set to {self._silence_threshold}")

    def set_crossfade_ms(self, ms: float):
        """Adjust SOLA crossfade length in milliseconds (requires restart)."""
        global SOLA_BUFFER_MS
        SOLA_BUFFER_MS = max(10, min(200, ms))
        if self._running:
            out = self._output_device_id
            inp = self._input_device_id
            self.stop()
            self.start(out, inp)
        logger.debug(f"Mic RVC crossfade set to {SOLA_BUFFER_MS}ms")

    def get_performance_params(self) -> dict:
        """Return current performance parameters."""
        return {
            'block_time': self._block_time,
            'context_time': self._context_time,
            'silence_threshold': self._silence_threshold,
            'crossfade_ms': SOLA_BUFFER_MS,
        }

    def _input_callback(self, indata: np.ndarray, frames: int,
                        time_info, status):
        """Input stream callback — just enqueues mic data."""
        if status:
            logger.warning(f"Mic RVC input status: {status}")
        if not self._running:
            return
        try:
            # Make a copy since indata buffer is reused
            self._input_queue.put_nowait(indata.copy())
        except queue.Full:
            # Drop oldest block if queue is full (processing too slow)
            try:
                self._input_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._input_queue.put_nowait(indata.copy())
            except queue.Full:
                pass

    def _output_callback(self, outdata: np.ndarray, frames: int,
                         time_info, status):
        """Output stream callback — pulls converted audio from queue."""
        if status:
            logger.debug(f"Mic RVC output status: {status}")
        try:
            block = self._output_queue.get_nowait()
            n = min(len(block), frames)
            if self._channels > 1:
                for ch in range(self._channels):
                    outdata[:n, ch] = block[:n]
                if n < frames:
                    outdata[n:, :] = 0.0
            else:
                outdata[:n, 0] = block[:n]
                if n < frames:
                    outdata[n:, :] = 0.0
        except queue.Empty:
            outdata[:] = 0.0

    def _process_loop(self):
        """Processing thread — reads input, runs RVC, writes output."""
        from scipy.signal import resample_poly

        logger.debug("Mic RVC processing thread started")
        callback_count = 0

        while self._running:
            try:
                # Wait for input block (with timeout so we can check _running)
                try:
                    indata = self._input_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                t0 = time.perf_counter()
                callback_count += 1

                # Queue cap: if >3 blocks queued, drop oldest to prevent unbounded latency growth
                queued = self._input_queue.qsize()
                if queued > 3:
                    dropped = 0
                    while queued > 1:
                        try:
                            self._input_queue.get_nowait()
                            dropped += 1
                            queued -= 1
                        except queue.Empty:
                            break
                    # Use the latest block instead
                    try:
                        indata = self._input_queue.get_nowait()
                        dropped += 1
                    except queue.Empty:
                        pass  # use the block we already have
                    logger.warning(f"Mic RVC: dropped {dropped} queued blocks to prevent latency spiral (queue was {queued + dropped})")
                    if not self._latency_warned:
                        self._latency_warned = True
                        logger.warning(
                            "Mic RVC: processing is slower than real-time on CPU. "
                            "Install CUDA PyTorch for real-time voice conversion. "
                            "This warning will not repeat."
                        )
                        if self.on_status:
                            self.on_status('rvc_latency_warning', {
                                'message': 'RVC is too slow for real-time on CPU. Install CUDA PyTorch for better performance.'
                            })

                # Check running before processing (stop may have been called)
                if not self._running:
                    logger.debug("[mic_rvc] _running is False after dequeue, exiting loop")
                    break

                # Bail out if buffers were cleared by stop()
                if self._input_wav is None:
                    logger.debug("[mic_rvc] _input_wav is None, exiting loop")
                    break

                # Convert to mono
                if indata.ndim == 1:
                    mono = indata.astype(np.float32)
                elif indata.shape[1] > 1:
                    mono = np.mean(indata, axis=1).astype(np.float32)
                else:
                    mono = indata[:, 0].astype(np.float32)

                # Shift rolling buffer and append new block
                self._input_wav[:-self._block_frame] = (
                    self._input_wav[self._block_frame:]
                )
                self._input_wav[-self._block_frame:] = mono[:self._block_frame]

                # Check silence
                rms = np.sqrt(np.mean(mono ** 2))
                if rms < self._silence_threshold:
                    # Output silence
                    silence = np.zeros(self._block_frame, dtype=np.float32)
                    try:
                        self._output_queue.put_nowait(silence)
                    except queue.Full:
                        try:
                            self._output_queue.get_nowait()
                        except queue.Empty:
                            pass
                        self._output_queue.put_nowait(silence)
                    continue

                # Check running before heavy RVC inference
                if not self._running:
                    logger.debug("[mic_rvc] _running is False before RVC inference, exiting loop")
                    break

                # Resample full rolling buffer to 16kHz
                buffer_16k = resample_poly(
                    self._input_wav, self._resample_up, self._resample_down
                ).astype(np.float32)

                block_samples_16k = self._block_frame_16k

                # Run streaming RVC conversion
                converted, self._pitch_cache, self._pitchf_cache, out_sr = \
                    self._rvc.convert_streaming(
                        buffer_16k,
                        block_samples_16k,
                        self._pitch_cache,
                        self._pitchf_cache,
                        self._sola_extra_frames,
                    )

                if converted is None:
                    silence = np.zeros(self._block_frame, dtype=np.float32)
                    try:
                        self._output_queue.put_nowait(silence)
                    except queue.Full:
                        pass
                    continue

                infer_wav = converted

                # Resample RVC output to device SR if needed
                if out_sr != self._device_sr:
                    g = gcd(out_sr, self._device_sr)
                    infer_wav = resample_poly(
                        infer_wav, self._device_sr // g, out_sr // g
                    ).astype(np.float32)

                # --- SOLA crossfading ---
                bf = self._block_frame
                sbf = self._sola_buffer_frame
                ssf = self._sola_search_frame

                if len(infer_wav) < bf + sbf:
                    # Not enough output — pad
                    out = np.zeros(bf, dtype=np.float32)
                    n = min(len(infer_wav), bf)
                    out[:n] = np.clip(infer_wav[:n], -1.0, 1.0)
                    try:
                        self._output_queue.put_nowait(out)
                    except queue.Full:
                        pass
                    continue

                # Find best SOLA offset via cross-correlation
                best_offset = 0
                best_score = -1.0
                for offset in range(ssf):
                    end = offset + sbf
                    if end > len(infer_wav):
                        break
                    segment = infer_wav[offset:end]
                    energy = np.sqrt(np.sum(segment ** 2) + 1e-8)
                    score = np.sum(segment * self._sola_buffer) / energy
                    if score > best_score:
                        best_score = score
                        best_offset = offset

                # Trim to aligned position
                infer_wav = infer_wav[best_offset:]

                # Apply crossfade
                if len(infer_wav) >= sbf:
                    infer_wav = infer_wav.copy()
                    infer_wav[:sbf] = (
                        infer_wav[:sbf] * self._fade_in +
                        self._sola_buffer * self._fade_out
                    )

                # Save SOLA buffer at block boundary
                if len(infer_wav) >= bf + sbf:
                    self._sola_buffer[:] = infer_wav[bf:bf + sbf]
                else:
                    self._sola_buffer[:] = 0.0

                # Output exactly block_frame samples
                out = np.clip(infer_wav[:bf], -1.0, 1.0)

                try:
                    self._output_queue.put_nowait(out)
                except queue.Full:
                    # Drop oldest to keep latency bounded
                    try:
                        self._output_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self._output_queue.put_nowait(out)

                elapsed = time.perf_counter() - t0
                if elapsed > self._block_time:
                    self._consecutive_slow += 1
                    # Log warning but not every single block — first 3, then every 10th
                    if self._consecutive_slow <= 3 or self._consecutive_slow % 10 == 0:
                        logger.warning(
                            f"Mic RVC process #{callback_count}: {elapsed:.2f}s "
                            f"(>{self._block_time:.2f}s block) — latency increasing "
                            f"(consecutive slow: {self._consecutive_slow})"
                        )
                    # One-time CUDA suggestion after 5 consecutive slow blocks
                    if self._consecutive_slow == 5 and not self._latency_warned:
                        self._latency_warned = True
                        logger.warning(
                            "Mic RVC: consistently slower than real-time. "
                            "Install CUDA PyTorch for real-time voice conversion."
                        )
                        if self.on_status:
                            self.on_status('rvc_latency_warning', {
                                'message': 'RVC is too slow for real-time on CPU. Install CUDA PyTorch for better performance.'
                            })
                else:
                    self._consecutive_slow = 0
                if callback_count <= 3 or callback_count % 20 == 0:
                    logger.debug(
                        f"Mic RVC process #{callback_count}: {elapsed:.3f}s "
                        f"(block={self._block_time:.2f}s)"
                    )

            except Exception as e:
                import traceback
                logger.error(
                    f"Mic RVC process error: {e}\n{traceback.format_exc()}"
                )

        logger.debug("Mic RVC processing thread stopped")
