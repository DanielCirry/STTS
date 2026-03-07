"""
STTS Python Backend - WebSocket Server
Main entry point for the Python sidecar process
"""

import asyncio
import json
import logging
import logging.handlers
import os
import signal
import sys
from pathlib import Path
from typing import Optional

import websockets
from websockets.server import WebSocketServerProtocol

from core.engine import STTSEngine
from core.events import EventType, create_event


def setup_logging():
    """Configure logging: file (INFO) + console (WARNING).

    File logs go to %APPDATA%/STTS/logs/stts.log with rotation (5 MB, 2 backups).
    Console (stderr) only shows WARNING and above to reduce noise.
    """
    appdata = os.environ.get('APPDATA') or str(Path.home())
    log_dir = Path(appdata) / 'STTS' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'stts.log'

    fmt = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')

    # Root logger captures everything
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # File handler — INFO level (captures info + warning + error)
    file_handler = logging.handlers.RotatingFileHandler(
        str(log_file), maxBytes=5 * 1024 * 1024, backupCount=2, encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Console handler — WARNING level only
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(fmt)
    root.addHandler(console_handler)

    # Suppress noisy third-party loggers
    for name in ('websockets', 'urllib3', 'httpx', 'httpcore', 'asyncio'):
        logging.getLogger(name).setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger('stts')

# Global engine instance
engine: Optional[STTSEngine] = None

# Connected clients
clients: set[WebSocketServerProtocol] = set()


async def broadcast(message: dict):
    """Broadcast a message to all connected clients."""
    if clients:
        message_str = json.dumps(message)
        await asyncio.gather(
            *[client.send(message_str) for client in clients],
            return_exceptions=True
        )


async def handle_message(websocket: WebSocketServerProtocol, message: str):
    """Handle incoming WebSocket messages."""
    global engine

    try:
        data = json.loads(message)
        msg_type = data.get('type')
        payload = data.get('payload', {})

        logger.debug(f"Received message: {msg_type}")

        if msg_type == 'ping':
            await websocket.send(json.dumps(create_event(EventType.PONG, {})))

        elif msg_type == 'get_status':
            status = engine.get_status() if engine else {'initialized': False}
            await websocket.send(json.dumps(create_event(EventType.STATUS, status)))

        elif msg_type == 'get_audio_devices':
            devices = engine.get_audio_devices() if engine else {'inputs': [], 'outputs': []}
            logger.debug(f"Audio devices: {len(devices.get('inputs', []))} inputs, {len(devices.get('outputs', []))} outputs")
            await websocket.send(json.dumps(create_event(EventType.AUDIO_DEVICES, devices)))

        elif msg_type == 'start_listening':
            if engine:
                await engine.start_listening()
                await websocket.send(json.dumps(create_event(EventType.LISTENING_STARTED, {})))

        elif msg_type == 'test_microphone':
            # Simple mic test - just capture audio levels without loading STT model
            if engine:
                device_id = payload.get('device_id')
                await engine.start_mic_test(device_id)
                await websocket.send(json.dumps(create_event(EventType.LISTENING_STARTED, {})))

        elif msg_type == 'stop_test_microphone':
            if engine:
                await engine.stop_mic_test()
                await websocket.send(json.dumps(create_event(EventType.LISTENING_STOPPED, {})))

        elif msg_type == 'stop_listening':
            if engine:
                await engine.stop_listening()
                await websocket.send(json.dumps(create_event(EventType.LISTENING_STOPPED, {})))

        elif msg_type == 'update_settings':
            if engine:
                logger.debug(f"Received update_settings: {payload}")
                engine.update_settings(payload)
                # Include actual TTS engine so frontend knows if a fallback occurred
                actual_engine = engine._tts.get_current_engine() if engine._tts else None
                await websocket.send(json.dumps(create_event(EventType.SETTINGS_UPDATED, {
                    'tts_engine': actual_engine,
                })))

        elif msg_type == 'load_model':
            if engine:
                model_type = payload.get('type')
                model_id = payload.get('id')
                success = await engine.load_model(model_type, model_id)
                await websocket.send(json.dumps(create_event(
                    EventType.MODEL_LOADED if success else EventType.MODEL_ERROR,
                    {'type': model_type, 'id': model_id}
                )))

        elif msg_type == 'speak':
            if engine:
                text = payload.get('text', '')
                await engine.speak(text)

        elif msg_type == 'ai_query':
            if engine:
                query = payload.get('query', '')
                # Response is broadcast via engine's callback - don't send here to avoid duplicates
                await engine.ai_query(query)

        elif msg_type == 'send_text' or msg_type == 'text_input':
            # Process text input the same way as voice transcripts
            # (translation, keyword check, VRChat send)
            if engine:
                text = payload.get('text', '')
                if text.strip():
                    await engine.process_text_input(text)

        elif msg_type == 'get_languages':
            if engine:
                languages = engine.get_supported_languages()
                await websocket.send(json.dumps({'type': 'languages', 'payload': {'languages': languages}}))

        elif msg_type == 'translate':
            if engine and engine._translator and engine._translator.is_loaded:
                text = payload.get('text', '')
                source = payload.get('source', 'eng_Latn')
                target = payload.get('target', 'jpn_Jpan')
                try:
                    translated = engine._translator.translate(text, source, target)
                    await websocket.send(json.dumps(create_event(EventType.TRANSLATION_COMPLETE, {
                        'original': text,
                        'translated': translated
                    })))
                except Exception as e:
                    await websocket.send(json.dumps(create_event(EventType.ERROR, {'message': str(e)})))

        elif msg_type == 'vrchat_send':
            # Send text directly to VRChat chatbox
            if engine:
                text = payload.get('text', '')
                use_queue = payload.get('use_queue', True)
                await engine.send_to_vrchat(text, use_queue)
                await websocket.send(json.dumps(create_event(EventType.VRCHAT_SENT, {'text': text})))

        elif msg_type == 'vrchat_clear':
            # Clear the VRChat chatbox
            if engine:
                engine.clear_vrchat_chatbox()
                await websocket.send(json.dumps(create_event(EventType.VRCHAT_SENT, {'text': '', 'cleared': True})))

        elif msg_type == 'get_tts_voices':
            # Get available TTS voices
            if engine:
                engine_id = payload.get('engine')
                voices = engine.get_tts_voices(engine_id)
                await websocket.send(json.dumps({'type': 'tts_voices', 'payload': {'voices': voices}}))

        elif msg_type == 'get_tts_output_devices':
            # Get available TTS output devices
            if engine:
                devices = engine.get_tts_output_devices()
                await websocket.send(json.dumps({'type': 'tts_output_devices', 'payload': {'devices': devices}}))

        elif msg_type == 'test_voicevox_connection':
            # Test connection to VOICEVOX engine
            if engine and engine._tts:
                voicevox = engine._tts._engines.get('voicevox')
                if voicevox:
                    url = payload.get('url', 'http://localhost:50021')
                    voicevox.engine_url = url
                    connected = await voicevox.test_connection()
                    result = {'connected': connected, 'url': url}
                    if connected:
                        # Fetch speakers with icons (uses cache)
                        voice_dicts = await voicevox.fetch_speakers_with_icons()
                        result['voices'] = voice_dicts
                    await websocket.send(json.dumps({'type': 'voicevox_connection_result', 'payload': result}))
                else:
                    await websocket.send(json.dumps({'type': 'voicevox_connection_result', 'payload': {'connected': False, 'error': 'VOICEVOX engine not registered'}}))

        elif msg_type == 'fetch_voicevox_voices':
            # Fetch VOICEVOX voices with icons (uses disk cache)
            if engine and engine._tts:
                voicevox = engine._tts._engines.get('voicevox')
                if voicevox:
                    try:
                        voice_dicts = await voicevox.fetch_speakers_with_icons()
                    except Exception as e:
                        logger.warning(f"Failed to fetch VOICEVOX voices: {e}")
                        voice_dicts = []
                    await websocket.send(json.dumps({'type': 'voicevox_voices', 'payload': {'voices': voice_dicts}}))
                else:
                    await websocket.send(json.dumps({'type': 'voicevox_voices', 'payload': {'voices': []}}))

        elif msg_type == 'voicevox_check_install':
            # Check if VOICEVOX Engine is installed locally
            if engine:
                status = await engine.voicevox_check_install()
                await websocket.send(json.dumps(create_event(EventType.VOICEVOX_SETUP_STATUS, status)))

        elif msg_type == 'voicevox_download_engine':
            # Download and install VOICEVOX Engine (fire-and-forget, progress via broadcast)
            if engine:
                build_type = payload.get('build_type', 'directml')
                asyncio.create_task(engine.voicevox_download_engine(build_type))

        elif msg_type == 'voicevox_cancel_download':
            # Cancel in-progress VOICEVOX download
            if engine:
                engine.voicevox_cancel_download()

        elif msg_type == 'voicevox_start_engine':
            # Start the local VOICEVOX Engine (non-blocking with immediate feedback)
            if engine:
                # Send immediate "starting" feedback so UI shows progress
                await websocket.send(json.dumps(create_event(EventType.VOICEVOX_SETUP_PROGRESS, {
                    'stage': 'starting', 'progress': 0, 'detail': 'Starting VOICEVOX Engine...',
                })))

                async def _do_start_engine():
                    success = await engine.voicevox_start_engine()
                    await engine.broadcast(create_event(EventType.VOICEVOX_SETUP_PROGRESS, {
                        'stage': 'complete' if success else 'error',
                        'progress': 100 if success else 0,
                        'detail': 'Engine started' if success else 'Failed to start engine',
                    }))
                    await engine.broadcast(create_event(EventType.VOICEVOX_ENGINE_STATUS, {
                        'running': success,
                        'port': 50021,
                        'pid': None,
                        'error': None if success else 'Failed to start VOICEVOX Engine',
                    }))

                asyncio.create_task(_do_start_engine())

        elif msg_type == 'voicevox_stop_engine':
            # Stop the local VOICEVOX Engine
            if engine:
                engine.voicevox_stop_engine()
                await websocket.send(json.dumps(create_event(EventType.VOICEVOX_ENGINE_STATUS, {
                    'running': False, 'port': 50021, 'pid': None, 'error': None,
                })))

        elif msg_type == 'voicevox_uninstall_engine':
            # Uninstall VOICEVOX Engine
            if engine:
                engine.voicevox_uninstall_engine()
                status = await engine.voicevox_check_install()
                await websocket.send(json.dumps(create_event(EventType.VOICEVOX_SETUP_STATUS, status)))

        elif msg_type == 'clear_cache':
            # Clear all cached data (VOICEVOX icons, etc.)
            try:
                from utils.cache import clear_all_cache
                result = clear_all_cache()
                await websocket.send(json.dumps({'type': 'cache_cleared', 'payload': result}))
            except Exception as e:
                await websocket.send(json.dumps({'type': 'cache_cleared', 'payload': {'error': str(e)}}))

        elif msg_type == 'get_cache_info':
            # Get cache statistics
            try:
                from utils.cache import get_cache_info
                info = get_cache_info()
                await websocket.send(json.dumps({'type': 'cache_info', 'payload': info}))
            except Exception as e:
                await websocket.send(json.dumps({'type': 'cache_info', 'payload': {'error': str(e)}}))

        elif msg_type == 'shutdown':
            # Graceful shutdown requested from frontend
            logger.info("Shutdown requested from frontend")
            if engine:
                await engine.cleanup()
            # Cancel the run-forever future to exit gracefully
            for task in asyncio.all_tasks():
                task.cancel()
            return

        elif msg_type == 'stop_speaking':
            # Stop current TTS playback
            if engine:
                engine.stop_speaking()
                await websocket.send(json.dumps(create_event(EventType.TTS_FINISHED, {})))

        elif msg_type == 'get_ai_providers':
            # Get available AI providers
            if engine:
                providers = engine.get_ai_providers()
                await websocket.send(json.dumps({'type': 'ai_providers', 'payload': {'providers': providers}}))

        elif msg_type == 'get_local_models':
            # Get available local LLM models
            if engine:
                models = engine.get_local_llm_models()
                await websocket.send(json.dumps({'type': 'local_models', 'payload': {'models': models}}))

        elif msg_type == 'set_models_directory':
            # Set custom models directory
            if engine:
                path = payload.get('path', '')
                success = engine.set_local_models_directory(path)
                # Return updated models list
                models = engine.get_local_llm_models() if success else []
                await websocket.send(json.dumps({'type': 'models_directory_set', 'payload': {
                    'success': success,
                    'path': path,
                    'models': models
                }}))

        elif msg_type == 'get_models_directory':
            # Get current models directory
            if engine:
                path = engine.get_local_models_directory()
                await websocket.send(json.dumps({'type': 'models_directory', 'payload': {'path': path}}))

        elif msg_type == 'set_ai_api_key':
            # Set API key for a provider
            if engine:
                provider = payload.get('provider', '')
                api_key = payload.get('api_key', '')
                success = engine.set_ai_api_key(provider, api_key)
                await websocket.send(json.dumps({'type': 'api_key_set', 'payload': {
                    'provider': provider,
                    'success': success
                }}))

        elif msg_type == 'check_ai_api_key':
            # Check if provider has API key
            if engine:
                provider = payload.get('provider', '')
                has_key = engine.has_ai_api_key(provider)
                await websocket.send(json.dumps({'type': 'api_key_status', 'payload': {
                    'provider': provider,
                    'has_key': has_key
                }}))

        elif msg_type == 'clear_ai_conversation':
            # Clear AI conversation history
            if engine:
                engine.clear_ai_conversation()
                await websocket.send(json.dumps({'type': 'ai_conversation_cleared', 'payload': {}}))

        elif msg_type == 'overlay_show_text':
            # Show text on VR overlay
            if engine:
                text = payload.get('text', '')
                message_type = payload.get('message_type', 'system')
                duration = payload.get('duration')
                engine.show_overlay_text(text, message_type, duration)
                await websocket.send(json.dumps({'type': 'overlay_text_shown', 'payload': {'text': text}}))

        elif msg_type == 'overlay_clear':
            # Clear the VR overlay
            if engine:
                engine.clear_overlay()
                await websocket.send(json.dumps({'type': 'overlay_cleared', 'payload': {}}))

        elif msg_type == 'get_overlay_status':
            # Get detailed VR overlay status
            if engine:
                status = engine.get_vr_overlay_status()
                await websocket.send(json.dumps({'type': 'overlay_status', 'payload': status}))

        elif msg_type == 'start_speaker_capture':
            # Start capturing speaker/system audio
            if engine:
                await engine.start_speaker_capture()

        elif msg_type == 'stop_speaker_capture':
            # Stop capturing speaker/system audio
            if engine:
                await engine.stop_speaker_capture()

        elif msg_type == 'get_gpu_info':
            # Get GPU information
            if engine:
                gpu_info = engine._get_gpu_info()
                await websocket.send(json.dumps({
                    'type': 'gpu_info',
                    'payload': gpu_info
                }))

        elif msg_type == 'get_loopback_devices':
            # Get available loopback devices
            if engine:
                devices = engine.get_loopback_devices()
                await websocket.send(json.dumps({
                    'type': 'loopback_devices',
                    'payload': {'devices': devices}
                }))

        # RVC Voice Conversion
        elif msg_type == 'rvc_scan_models':
            if engine:
                directory = payload.get('directory')
                await engine.rvc_scan_models(directory)

        elif msg_type == 'rvc_load_model':
            if engine:
                model_path = payload.get('model_path', '')
                index_path = payload.get('index_path')
                await engine.rvc_load_model(model_path, index_path)

        elif msg_type == 'rvc_download_base_models':
            if engine:
                await engine.rvc_download_base_models()

        elif msg_type == 'rvc_enable':
            if engine:
                enabled = payload.get('enabled', False)
                await engine.rvc_enable(enabled)

        elif msg_type == 'rvc_set_params':
            if engine:
                await engine.rvc_set_params(**payload)

        elif msg_type == 'rvc_unload':
            if engine:
                await engine.rvc_unload()

        elif msg_type == 'rvc_get_status':
            if engine:
                await engine.rvc_get_status()

        elif msg_type == 'rvc_browse_model':
            if engine:
                logger.debug("Opening RVC model file dialog...")
                def _open_file_dialog():
                    try:
                        import ctypes
                        import ctypes.wintypes

                        # Use Win32 GetOpenFileNameW directly via ctypes
                        # This works reliably from background processes unlike
                        # PowerShell/tkinter dialogs which need STA threads.
                        _PWCHAR = ctypes.POINTER(ctypes.c_wchar)

                        class OPENFILENAME(ctypes.Structure):
                            _fields_ = [
                                ("lStructSize", ctypes.wintypes.DWORD),
                                ("hwndOwner", ctypes.wintypes.HWND),
                                ("hInstance", ctypes.wintypes.HINSTANCE),
                                ("lpstrFilter", ctypes.wintypes.LPCWSTR),
                                ("lpstrCustomFilter", _PWCHAR),
                                ("nMaxCustFilter", ctypes.wintypes.DWORD),
                                ("nFilterIndex", ctypes.wintypes.DWORD),
                                ("lpstrFile", _PWCHAR),
                                ("nMaxFile", ctypes.wintypes.DWORD),
                                ("lpstrFileTitle", _PWCHAR),
                                ("nMaxFileTitle", ctypes.wintypes.DWORD),
                                ("lpstrInitialDir", ctypes.wintypes.LPCWSTR),
                                ("lpstrTitle", ctypes.wintypes.LPCWSTR),
                                ("Flags", ctypes.wintypes.DWORD),
                                ("nFileOffset", ctypes.wintypes.WORD),
                                ("nFileExtension", ctypes.wintypes.WORD),
                                ("lpstrDefExt", ctypes.wintypes.LPCWSTR),
                                ("lCustData", ctypes.wintypes.LPARAM),
                                ("lpfnHook", ctypes.c_void_p),
                                ("lpTemplateName", ctypes.wintypes.LPCWSTR),
                            ]

                        OFN_FILEMUSTEXIST = 0x00001000
                        OFN_PATHMUSTEXIST = 0x00000800
                        OFN_NOCHANGEDIR = 0x00000008

                        file_buf = ctypes.create_unicode_buffer(1024)
                        ofn = OPENFILENAME()
                        ofn.lStructSize = ctypes.sizeof(OPENFILENAME)
                        ofn.hwndOwner = None
                        ofn.lpstrFilter = "RVC Models (*.pth)\0*.pth\0All Files (*.*)\0*.*\0\0"
                        ofn.lpstrFile = file_buf
                        ofn.nMaxFile = 1024
                        ofn.lpstrTitle = "Select RVC Voice Model"
                        ofn.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR

                        # Bring dialog to front
                        ctypes.windll.user32.SetForegroundWindow(
                            ctypes.windll.kernel32.GetConsoleWindow() or 0
                        )
                        if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
                            return file_buf.value or None
                        return None
                    except Exception as e:
                        logger.error(f"File dialog failed: {e}")
                        return None

                path = await asyncio.get_event_loop().run_in_executor(None, _open_file_dialog)
                logger.debug(f"File dialog result: {path}")
                if path:
                    index_path = None
                    base = os.path.splitext(path)[0]
                    for ext in ['.index', '.0.index']:
                        candidate = base + ext
                        if os.path.exists(candidate):
                            index_path = candidate
                            break
                    await websocket.send(json.dumps({
                        'type': 'rvc_model_browsed',
                        'payload': {'path': path, 'index_path': index_path}
                    }))
                    await engine.rvc_load_model(path, index_path)
                else:
                    logger.debug("File dialog cancelled or no file selected")

        elif msg_type == 'rvc_test_voice':
            if engine:
                await engine.rvc_test_voice()

        elif msg_type == 'rvc_mic_start':
            if engine:
                output_device = payload.get('output_device_id')
                await engine.mic_rvc_start(output_device)

        elif msg_type == 'rvc_mic_stop':
            if engine:
                await engine.mic_rvc_stop()

        elif msg_type == 'rvc_mic_set_output_device':
            if engine:
                device_id = payload.get('device_id')
                await engine.mic_rvc_set_output_device(device_id)

        elif msg_type == 'rvc_set_device':
            if engine:
                device = payload.get('device', 'cpu')
                await engine.rvc_set_device(device)

        elif msg_type == 'get_features_status':
            try:
                from utils.package_manager import check_all_features
                feat_status = check_all_features()
                logger.debug(f"Features status: {list(feat_status.get('features', {}).keys())}")
                await websocket.send(json.dumps({'type': 'features_status', 'payload': feat_status}))
            except Exception as e:
                logger.error(f"Failed to get features status: {e}", exc_info=True)
                await websocket.send(json.dumps({'type': 'features_status', 'payload': {
                    'features': {},
                    'python_available': False,
                    'is_frozen': getattr(sys, 'frozen', False),
                    'error': str(e),
                }}))

        elif msg_type == 'install_feature':
            from utils.package_manager import install_feature

            feature_id = payload.get('feature_id', '')

            async def _progress(info):
                await broadcast({'type': 'feature_install_progress', 'payload': info})

            result = await install_feature(feature_id, progress_callback=_progress)
            await websocket.send(json.dumps({'type': 'feature_install_result', 'payload': result}))

        elif msg_type == 'uninstall_feature':
            from utils.package_manager import uninstall_feature

            feature_id = payload.get('feature_id', '')

            async def _unprogress(info):
                await broadcast({'type': 'feature_uninstall_progress', 'payload': info})

            result = await uninstall_feature(feature_id, progress_callback=_unprogress)
            await websocket.send(json.dumps({'type': 'feature_uninstall_result', 'payload': result}))

        elif msg_type == 'rvc_get_available_devices':
            from ai.rvc.config import get_available_devices
            devices = get_available_devices()
            await websocket.send(json.dumps({
                'type': 'rvc_available_devices',
                'payload': {'devices': devices}
            }))

        else:
            logger.warning(f"Unknown message type: {msg_type}")

    except json.JSONDecodeError:
        logger.error(f"Invalid JSON message: {message}")
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await websocket.send(json.dumps(create_event(EventType.ERROR, {'message': str(e)})))


async def handler(websocket: WebSocketServerProtocol):
    """Handle WebSocket connections."""
    clients.add(websocket)
    logger.debug(f"Client connected. Total clients: {len(clients)}")

    try:
        # Send initial status
        status = engine.get_status() if engine else {'initialized': False}
        await websocket.send(json.dumps(create_event(EventType.STATUS, status)))

        # Handle messages
        async for message in websocket:
            await handle_message(websocket, message)

    except websockets.exceptions.ConnectionClosed:
        logger.debug("Client disconnected")
    finally:
        clients.remove(websocket)
        logger.debug(f"Client removed. Total clients: {len(clients)}")


async def main():
    """Main entry point."""
    global engine

    # Parse command line arguments
    host = '0.0.0.0'  # Listen on all interfaces
    port = 9876

    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    logger.info(f"Starting STTS backend on {host}:{port}")

    # Initialize engine
    engine = STTSEngine(broadcast_callback=broadcast)
    await engine.initialize()

    # Set up signal handlers
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Shutting down...")
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    # Start WebSocket server (retry if port is still held by previous instance)
    for attempt in range(10):
        try:
            async with websockets.serve(handler, host, port):
                logger.info(f"WebSocket server started on ws://{host}:{port}")
                await asyncio.Future()  # Run forever
            break
        except OSError as e:
            if attempt < 9 and 'address' in str(e).lower():
                logger.warning(f"Port {port} in use, retrying in 1s... (attempt {attempt + 1}/10)")
                await asyncio.sleep(1)
            else:
                raise


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
