"""
Audio Manager - Handles microphone input and speaker capture
Uses sounddevice for mic input and soundcard for WASAPI loopback
"""

import asyncio
import logging
import queue
import threading
from typing import Callable, Dict, List, Optional

import numpy as np

logger = logging.getLogger('stts.audio')

# Audio settings
SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1
CHUNK_DURATION = 0.1  # 100ms chunks
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)


class AudioManager:
    """Manages audio input from microphone and speaker loopback."""

    def __init__(self):
        self.mic_stream = None
        self.loopback_stream = None
        self.is_recording = False
        self.audio_queue: queue.Queue = queue.Queue()

        # VAD settings
        self.vad_enabled = True
        self.vad_sensitivity = 0.5
        self._vad = None

        # Callbacks
        self.on_audio_data: Optional[Callable[[np.ndarray], None]] = None
        self.on_audio_level: Optional[Callable[[float], None]] = None
        self.on_mic_rvc_data: Optional[Callable[[np.ndarray], None]] = None

        # Device info
        self._input_devices: List[Dict] = []
        self._output_devices: List[Dict] = []
        self._refresh_devices()

    def _get_windows_friendly_names(self) -> dict:
        """Get friendly device names from Windows MMDevice API."""
        friendly_names = {}
        try:
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IMMDeviceEnumerator, EDataFlow, DEVICE_STATE
            from pycaw.constants import CLSID_MMDeviceEnumerator
            import comtypes

            # Get device enumerator
            deviceEnumerator = comtypes.CoCreateInstance(
                CLSID_MMDeviceEnumerator,
                IMMDeviceEnumerator,
                comtypes.CLSCTX_INPROC_SERVER
            )

            # Get all render (output) devices
            try:
                render_collection = deviceEnumerator.EnumAudioEndpoints(
                    EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value
                )
                render_count = render_collection.GetCount()
                for i in range(render_count):
                    device = render_collection.Item(i)
                    props = device.OpenPropertyStore(0)  # STGM_READ
                    try:
                        # PKEY_Device_FriendlyName
                        friendly_name = props.GetValue(
                            "{a45c254e-df1c-4efd-8020-67d146a850e0}, 14"
                        )
                        # PKEY_DeviceInterface_FriendlyName (shorter name)
                        interface_name = props.GetValue(
                            "{b3f8fa53-0004-438e-9003-51a46e139bfc}, 6"
                        )
                        if interface_name:
                            friendly_names[str(friendly_name).lower()] = str(interface_name)
                    except:
                        pass
            except Exception as e:
                logger.debug(f"Error getting render devices: {e}")

            # Get all capture (input) devices
            try:
                capture_collection = deviceEnumerator.EnumAudioEndpoints(
                    EDataFlow.eCapture.value, DEVICE_STATE.ACTIVE.value
                )
                capture_count = capture_collection.GetCount()
                for i in range(capture_count):
                    device = capture_collection.Item(i)
                    props = device.OpenPropertyStore(0)
                    try:
                        friendly_name = props.GetValue(
                            "{a45c254e-df1c-4efd-8020-67d146a850e0}, 14"
                        )
                        interface_name = props.GetValue(
                            "{b3f8fa53-0004-438e-9003-51a46e139bfc}, 6"
                        )
                        if interface_name:
                            friendly_names[str(friendly_name).lower()] = str(interface_name)
                    except:
                        pass
            except Exception as e:
                logger.debug(f"Error getting capture devices: {e}")

        except ImportError:
            logger.debug("pycaw not available for friendly names")
        except Exception as e:
            logger.debug(f"Error getting friendly names: {e}")

        logger.debug(f"Found {len(friendly_names)} friendly names from Windows API")
        return friendly_names

    def _refresh_devices(self):
        """Refresh the list of available audio devices."""
        try:
            import sounddevice as sd

            self._input_devices = []
            self._output_devices = []

            # Try to get Windows friendly names
            friendly_names = self._get_windows_friendly_names()

            # Get host APIs info
            host_apis = sd.query_hostapis()
            host_api_names = {i: api['name'] for i, api in enumerate(host_apis)}

            # Find WASAPI index for identifying hardware devices
            wasapi_index = None
            for i, api in enumerate(host_apis):
                if 'WASAPI' in api['name']:
                    wasapi_index = i
                    break

            devices = sd.query_devices()
            default_input = sd.query_devices(kind='input')
            default_output = sd.query_devices(kind='output')
            default_input_name = default_input['name'] if default_input else None
            default_output_name = default_output['name'] if default_output else None

            # Track seen device names to avoid exact duplicates
            seen_input_names = set()
            seen_output_names = set()

            # Log friendly names for debugging
            if friendly_names:
                logger.debug(f"Friendly names mapping: {friendly_names}")

            for i, device in enumerate(devices):
                device_name = device['name']
                host_api = host_api_names.get(device['hostapi'], 'Unknown')
                is_wasapi = device['hostapi'] == wasapi_index

                # Clean up ugly WDM-KS style names
                display_name = device_name
                if '@System32' in device_name or '%' in device_name:
                    # Extract meaningful part from ugly WDM-KS names like:
                    # "Headset 1 (@System32\drivers\bthhfenum.sys,#2;%1 Hands-Free%..."
                    # Try to get just the device type part
                    if '(' in device_name:
                        display_name = device_name.split('(')[0].strip()
                    if not display_name or display_name == device_name:
                        display_name = "Virtual Device"

                # Try to get a friendly name from Windows API
                friendly_name = friendly_names.get(device_name.lower(), None)

                # If not found, try partial matching (sounddevice names might be truncated)
                if not friendly_name:
                    for full_name, short_name in friendly_names.items():
                        if full_name in device_name.lower() or device_name.lower() in full_name:
                            friendly_name = short_name
                            break

                # Use friendly name if available, otherwise use cleaned display_name
                if friendly_name:
                    display_name = friendly_name

                # Check if device is active
                is_active = (device['default_samplerate'] > 0 and
                            (device['max_input_channels'] > 0 or device['max_output_channels'] > 0))

                # Create a unique key to track duplicates (name + host api)
                input_key = f"{device_name}_{host_api}_input"
                output_key = f"{device_name}_{host_api}_output"

                if device['max_input_channels'] > 0 and input_key not in seen_input_names:
                    seen_input_names.add(input_key)

                    # Build final display name with API suffix for non-WASAPI
                    final_name = display_name
                    if not is_wasapi:
                        final_name = f"{display_name} [{host_api}]"

                    device_info = {
                        'id': i,
                        'name': final_name,
                        'raw_name': device_name,
                        'sample_rate': int(device['default_samplerate']),
                        'channels': device['max_input_channels'],
                        'is_default': device_name == default_input_name,
                        'is_active': is_active,
                        'is_hardware': is_wasapi,
                        'host_api': host_api,
                    }
                    self._input_devices.append(device_info)

                if device['max_output_channels'] > 0 and output_key not in seen_output_names:
                    seen_output_names.add(output_key)

                    # Build final display name with API suffix for non-WASAPI
                    final_name = display_name
                    if not is_wasapi:
                        final_name = f"{display_name} [{host_api}]"

                    device_info = {
                        'id': i,
                        'name': final_name,
                        'raw_name': device_name,
                        'sample_rate': int(device['default_samplerate']),
                        'channels': device['max_output_channels'],
                        'is_default': device_name == default_output_name,
                        'is_active': is_active,
                        'is_hardware': is_wasapi,
                        'host_api': host_api,
                    }
                    self._output_devices.append(device_info)

            # Sort devices: default first, then hardware (WASAPI), then by name
            self._input_devices.sort(key=lambda d: (not d['is_default'], not d['is_hardware'], d['name']))
            self._output_devices.sort(key=lambda d: (not d['is_default'], not d['is_hardware'], d['name']))

            logger.debug(f"Found {len(self._input_devices)} input, {len(self._output_devices)} output devices")

        except Exception as e:
            logger.error(f"Error refreshing devices: {e}")

    def refresh_devices(self):
        """Public method to refresh device list (called when devices change)."""
        self._refresh_devices()
        return {
            'inputs': self._input_devices.copy(),
            'outputs': self._output_devices.copy()
        }

    def get_input_devices(self) -> List[Dict]:
        """Get list of available input devices."""
        return self._input_devices.copy()

    def get_output_devices(self) -> List[Dict]:
        """Get list of available output devices."""
        return self._output_devices.copy()

    def _init_vad(self):
        """Initialize Voice Activity Detection."""
        if self._vad is not None:
            return

        try:
            import webrtcvad
            self._vad = webrtcvad.Vad()
            # Aggressiveness mode: 0 (least aggressive) to 3 (most aggressive)
            mode = int(self.vad_sensitivity * 3)
            self._vad.set_mode(mode)
            logger.debug(f"VAD initialized with mode {mode}")
        except ImportError:
            logger.warning("webrtcvad not available, VAD disabled")
            self.vad_enabled = False
        except Exception as e:
            logger.error(f"Error initializing VAD: {e}")
            self.vad_enabled = False

    def _is_speech(self, audio_data: np.ndarray) -> bool:
        """Check if audio contains speech using VAD."""
        if not self.vad_enabled or self._vad is None:
            return True

        try:
            # Convert to 16-bit PCM for webrtcvad
            audio_int16 = (audio_data * 32767).astype(np.int16)

            # webrtcvad requires specific frame sizes (10, 20, or 30 ms)
            frame_duration = 30  # ms
            frame_size = int(SAMPLE_RATE * frame_duration / 1000)

            # Check multiple frames
            speech_frames = 0
            total_frames = 0

            for i in range(0, len(audio_int16) - frame_size, frame_size):
                frame = audio_int16[i:i + frame_size].tobytes()
                if self._vad.is_speech(frame, SAMPLE_RATE):
                    speech_frames += 1
                total_frames += 1

            # Return True if more than 30% of frames contain speech
            if total_frames > 0:
                return speech_frames / total_frames > 0.3
            return False

        except Exception as e:
            logger.error(f"VAD error: {e}")
            return True

    def _calculate_level(self, audio_data: np.ndarray) -> float:
        """Calculate audio level in dB."""
        rms = np.sqrt(np.mean(audio_data ** 2))
        if rms > 0:
            db = 20 * np.log10(rms)
            # Normalize to 0-1 range (assuming -60dB to 0dB range)
            # Convert to Python float for JSON serialization
            return float(max(0, min(1, (db + 60) / 60)))
        return 0.0

    def start_microphone(self, device_id: Optional[int] = None):
        """Start capturing audio from the microphone."""
        if self.is_recording:
            logger.warning("Already recording")
            return

        try:
            import sounddevice as sd

            if self.vad_enabled:
                self._init_vad()

            def audio_callback(indata, frames, time, status):
                if status:
                    logger.warning(f"Audio callback status: {status}")

                # Convert to mono float32
                audio_data = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
                audio_data = audio_data.astype(np.float32)

                # Calculate and report audio level
                level = self._calculate_level(audio_data)
                if level > 0.01:  # Only log if there's some sound
                    logger.debug(f"Audio level: {level:.3f}")
                if self.on_audio_level:
                    self.on_audio_level(level)

                # Feed all audio to mic RVC (not gated by VAD)
                if self.on_mic_rvc_data:
                    self.on_mic_rvc_data(audio_data)

                # Check for speech
                if self._is_speech(audio_data):
                    self.audio_queue.put(audio_data)
                    if self.on_audio_data:
                        self.on_audio_data(audio_data)

            self.mic_stream = sd.InputStream(
                device=device_id,
                channels=CHANNELS,
                samplerate=SAMPLE_RATE,
                blocksize=CHUNK_SIZE,
                dtype=np.float32,
                callback=audio_callback
            )
            self.mic_stream.start()
            self.is_recording = True
            logger.debug(f"Started microphone capture (device: {device_id or 'default'})")

        except Exception as e:
            logger.error(f"Error starting microphone: {e}")
            raise

    def stop_microphone(self):
        """Stop capturing audio from the microphone."""
        if self.mic_stream:
            self.mic_stream.stop()
            self.mic_stream.close()
            self.mic_stream = None
            self.is_recording = False
            logger.debug("Stopped microphone capture")

    def start_loopback(self, device_id: Optional[int] = None):
        """Start capturing audio from speaker loopback (WASAPI)."""
        try:
            import soundcard as sc

            if device_id is not None:
                # Find device by ID
                speakers = sc.all_speakers()
                if device_id < len(speakers):
                    speaker = speakers[device_id]
                else:
                    speaker = sc.default_speaker()
            else:
                speaker = sc.default_speaker()

            loopback = speaker.get_loopback()

            def loopback_thread():
                with loopback.recorder(samplerate=SAMPLE_RATE, channels=CHANNELS) as mic:
                    while self.loopback_stream is not None:
                        data = mic.record(numframes=CHUNK_SIZE)
                        audio_data = data[:, 0] if data.ndim > 1 else data
                        audio_data = audio_data.astype(np.float32)

                        if self._is_speech(audio_data):
                            self.audio_queue.put(('loopback', audio_data))

            self.loopback_stream = threading.Thread(target=loopback_thread, daemon=True)
            self.loopback_stream.start()
            logger.debug("Started speaker loopback capture")

        except ImportError:
            logger.error("soundcard not available for loopback capture")
        except Exception as e:
            logger.error(f"Error starting loopback: {e}")

    def stop_loopback(self):
        """Stop capturing audio from speaker loopback."""
        if self.loopback_stream:
            stream = self.loopback_stream
            self.loopback_stream = None
            stream.join(timeout=1)
            logger.debug("Stopped speaker loopback capture")

    def get_audio_chunk(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """Get the next audio chunk from the queue."""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear_queue(self):
        """Clear the audio queue."""
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

    def cleanup(self):
        """Clean up resources."""
        self.stop_microphone()
        self.stop_loopback()
        self.clear_queue()
