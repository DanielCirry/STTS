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

    # File handler — DEBUG level (captures everything for troubleshooting)
    file_handler = logging.handlers.RotatingFileHandler(
        str(log_file), maxBytes=10 * 1024 * 1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
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

        logger.info(f"[ws] Received: {msg_type} payload_keys={list(payload.keys()) if payload else 'none'}")

        if msg_type == 'ping':
            logger.debug("[ws] ping")
            await websocket.send(json.dumps(create_event(EventType.PONG, {})))

        elif msg_type == 'get_status':
            logger.debug("[ws] get_status")
            status = engine.get_status() if engine else {'initialized': False}
            await websocket.send(json.dumps(create_event(EventType.STATUS, status)))

        elif msg_type == 'get_audio_devices':
            logger.debug("[ws] get_audio_devices")
            devices = engine.get_audio_devices() if engine else {'inputs': [], 'outputs': []}
            logger.debug(f"Audio devices: {len(devices.get('inputs', []))} inputs, {len(devices.get('outputs', []))} outputs")
            await websocket.send(json.dumps(create_event(EventType.AUDIO_DEVICES, devices)))

        elif msg_type == 'start_listening':
            logger.debug("[ws] start_listening")
            if engine:
                logger.info("[ws] start_listening: loading STT model and starting mic capture")
                try:
                    await engine.start_listening()
                    if engine.listening:
                        logger.info("[ws] start_listening: done, sending LISTENING_STARTED")
                        await websocket.send(json.dumps(create_event(EventType.LISTENING_STARTED, {})))
                    else:
                        logger.error("[ws] start_listening: engine.listening is False after start_listening — STT likely failed")
                        await websocket.send(json.dumps(create_event(EventType.LISTENING_STOPPED, {})))
                except Exception as e:
                    logger.error(f"[ws] start_listening failed: {e}")
                    await websocket.send(json.dumps(create_event(EventType.LISTENING_STOPPED, {})))

        elif msg_type == 'test_microphone':
            logger.debug(f"[ws] test_microphone: device_id={payload.get('device_id')}")
            if engine:
                device_id = payload.get('device_id')
                await engine.start_mic_test(device_id)
                await websocket.send(json.dumps(create_event(EventType.LISTENING_STARTED, {})))

        elif msg_type == 'stop_test_microphone':
            logger.debug("[ws] stop_test_microphone")
            if engine:
                await engine.stop_mic_test()
                await websocket.send(json.dumps(create_event(EventType.LISTENING_STOPPED, {})))

        elif msg_type == 'test_speaker':
            logger.debug(f"[ws] test_speaker: device_id={payload.get('device_id')}")
            if engine:
                device_id = payload.get('device_id')
                await engine.test_speaker(device_id)
                await websocket.send(json.dumps(create_event(EventType.SPEAKER_TEST_DONE, {})))

        elif msg_type == 'test_loopback':
            logger.debug(f"[ws] test_loopback: device_id={payload.get('device_id')}")
            if engine:
                device_id = payload.get('device_id')
                await engine.test_loopback(device_id)
                await websocket.send(json.dumps(create_event(EventType.SPEAKER_TEST_DONE, {})))

        elif msg_type == 'stop_listening':
            logger.debug("[ws] stop_listening")
            if engine:
                await engine.stop_listening()
                await websocket.send(json.dumps(create_event(EventType.LISTENING_STOPPED, {})))

        elif msg_type == 'update_settings':
            logger.debug(f"[ws] update_settings: keys={list(payload.keys()) if payload else 'none'}")
            if engine:
                logger.debug(f"Received update_settings: {payload}")
                engine.update_settings(payload)
                # Include actual TTS engine so frontend knows if a fallback occurred
                actual_engine = engine._tts.get_current_engine() if engine._tts else None
                await websocket.send(json.dumps(create_event(EventType.SETTINGS_UPDATED, {
                    'tts_engine': actual_engine,
                })))

        elif msg_type == 'load_model':
            logger.debug(f"[ws] load_model: type={payload.get('type')} id={payload.get('id')}")
            if engine:
                model_type = payload.get('type')
                model_id = payload.get('id')
                success = await engine.load_model(model_type, model_id)
                await websocket.send(json.dumps(create_event(
                    EventType.MODEL_LOADED if success else EventType.MODEL_ERROR,
                    {'type': model_type, 'id': model_id}
                )))

        elif msg_type == 'speak':
            logger.debug(f"[ws] speak: text_len={len(payload.get('text', ''))}")
            if engine:
                text = payload.get('text', '')
                await engine.speak(text)

        elif msg_type == 'ai_query':
            logger.debug(f"[ws] ai_query: query_len={len(payload.get('query', ''))}")
            if engine:
                query = payload.get('query', '')
                # Response is broadcast via engine's callback - don't send here to avoid duplicates
                await engine.ai_query(query)

        elif msg_type == 'send_text' or msg_type == 'text_input':
            logger.debug(f"[ws] {msg_type}: text_len={len(payload.get('text', ''))}")
            if engine:
                text = payload.get('text', '')
                if text.strip():
                    await engine.process_text_input(text)

        elif msg_type == 'get_languages':
            logger.debug("[ws] get_languages")
            if engine:
                languages = engine.get_supported_languages()
                await websocket.send(json.dumps({'type': 'languages', 'payload': {'languages': languages}}))

        elif msg_type == 'translate':
            logger.debug(f"[ws] translate: source={payload.get('source')} target={payload.get('target')} text_len={len(payload.get('text', ''))}")
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
            logger.debug(f"[ws] vrchat_send: text_len={len(payload.get('text', ''))} use_queue={payload.get('use_queue')}")
            if engine:
                text = payload.get('text', '')
                use_queue = payload.get('use_queue', True)
                await engine.send_to_vrchat(text, use_queue)
                await websocket.send(json.dumps(create_event(EventType.VRCHAT_SENT, {'text': text})))

        elif msg_type == 'vrchat_clear':
            logger.debug("[ws] vrchat_clear")
            if engine:
                engine.clear_vrchat_chatbox()
                await websocket.send(json.dumps(create_event(EventType.VRCHAT_SENT, {'text': '', 'cleared': True})))

        elif msg_type == 'test_osc':
            ip = payload.get('ip', '127.0.0.1')
            port = int(payload.get('port', 9000))
            logger.info(f"[ws] test_osc: ip={ip} port={port}")
            try:
                from pythonosc import udp_client as _udp_client
                from pythonosc.osc_message_builder import OscMessageBuilder
                client = _udp_client.SimpleUDPClient(ip, port)
                builder = OscMessageBuilder(address="/chatbox/input")
                builder.add_arg("STTS Test Message")
                builder.add_arg(True)
                builder.add_arg(True)
                client.send(builder.build())
                logger.info(f"[ws] test_osc: sent test message to {ip}:{port}")
                await websocket.send(json.dumps({'type': 'test_osc_result', 'payload': {'success': True, 'ip': ip, 'port': port}}))
            except Exception as e:
                logger.error(f"[ws] test_osc FAILED: {e}")
                await websocket.send(json.dumps({'type': 'test_osc_result', 'payload': {'success': False, 'error': str(e)}}))

        elif msg_type == 'get_tts_voices':
            logger.debug(f"[ws] get_tts_voices: engine={payload.get('engine')}")
            if engine:
                engine_id = payload.get('engine')
                voices = engine.get_tts_voices(engine_id)
                await websocket.send(json.dumps({'type': 'tts_voices', 'payload': {'voices': voices}}))

        elif msg_type == 'get_tts_output_devices':
            logger.debug("[ws] get_tts_output_devices")
            if engine:
                devices = engine.get_tts_output_devices()
                await websocket.send(json.dumps({'type': 'tts_output_devices', 'payload': {'devices': devices}}))

        elif msg_type == 'test_voicevox_connection':
            logger.debug(f"[ws] test_voicevox_connection: url={payload.get('url')}")
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
            logger.debug("[ws] fetch_voicevox_voices")
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
            logger.debug("[ws] voicevox_check_install")
            if engine:
                status = await engine.voicevox_check_install()
                await websocket.send(json.dumps(create_event(EventType.VOICEVOX_SETUP_STATUS, status)))

        elif msg_type == 'voicevox_download_engine':
            logger.debug(f"[ws] voicevox_download_engine: build_type={payload.get('build_type')}")
            if engine:
                build_type = payload.get('build_type', 'directml')
                asyncio.create_task(engine.voicevox_download_engine(build_type))

        elif msg_type == 'voicevox_cancel_download':
            logger.debug("[ws] voicevox_cancel_download")
            if engine:
                engine.voicevox_cancel_download()

        elif msg_type == 'voicevox_start_engine':
            logger.debug("[ws] voicevox_start_engine")
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
            logger.debug("[ws] voicevox_stop_engine")
            if engine:
                engine.voicevox_stop_engine()
                await websocket.send(json.dumps(create_event(EventType.VOICEVOX_ENGINE_STATUS, {
                    'running': False, 'port': 50021, 'pid': None, 'error': None,
                })))

        elif msg_type == 'voicevox_uninstall_engine':
            logger.debug("[ws] voicevox_uninstall_engine")
            if engine:
                engine.voicevox_uninstall_engine()
                status = await engine.voicevox_check_install()
                await websocket.send(json.dumps(create_event(EventType.VOICEVOX_SETUP_STATUS, status)))

        elif msg_type == 'clear_cache':
            logger.debug("[ws] clear_cache")
            try:
                from utils.cache import clear_all_cache
                result = clear_all_cache()
                await websocket.send(json.dumps({'type': 'cache_cleared', 'payload': result}))
            except Exception as e:
                await websocket.send(json.dumps({'type': 'cache_cleared', 'payload': {'error': str(e)}}))

        elif msg_type == 'get_cache_info':
            logger.debug("[ws] get_cache_info")
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
            logger.debug("[ws] stop_speaking")
            if engine:
                engine.stop_speaking()
                await websocket.send(json.dumps(create_event(EventType.TTS_FINISHED, {})))

        elif msg_type == 'get_ai_providers':
            logger.debug("[ws] get_ai_providers")
            if engine:
                providers = engine.get_ai_providers()
                await websocket.send(json.dumps({'type': 'ai_providers', 'payload': {'providers': providers}}))

        elif msg_type == 'get_local_models':
            logger.debug("[ws] get_local_models")
            if engine:
                models = engine.get_local_llm_models()
                await websocket.send(json.dumps({'type': 'local_models', 'payload': {'models': models}}))

        elif msg_type == 'set_models_directory':
            logger.debug(f"[ws] set_models_directory: path={payload.get('path')}")
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
            logger.debug("[ws] get_models_directory")
            if engine:
                path = engine.get_local_models_directory()
                await websocket.send(json.dumps({'type': 'models_directory', 'payload': {'path': path}}))

        elif msg_type == 'get_llm_status':
            logger.debug("[ws] get_llm_status")
            if engine:
                status = engine.get_llm_status()
                await websocket.send(json.dumps({'type': 'llm_status', 'payload': status}))

        elif msg_type == 'unload_llm':
            logger.debug("[ws] unload_llm")
            if engine:
                success = engine.unload_llm()
                await websocket.send(json.dumps({'type': 'llm_unloaded', 'payload': {'success': success}}))

        elif msg_type == 'browse_llm_folder':
            logger.debug("[ws] browse_llm_folder")
            if engine:
                def _open_folder_dialog():
                    try:
                        import ctypes
                        import ctypes.wintypes
                        from ctypes import windll

                        # Use SHBrowseForFolderW via ctypes for folder picker
                        BIF_RETURNONLYFSDIRS = 0x00000001
                        BIF_NEWDIALOGSTYLE = 0x00000040

                        class BROWSEINFO(ctypes.Structure):
                            _fields_ = [
                                ("hwndOwner", ctypes.wintypes.HWND),
                                ("pidlRoot", ctypes.c_void_p),
                                ("pszDisplayName", ctypes.c_wchar_p),
                                ("lpszTitle", ctypes.c_wchar_p),
                                ("ulFlags", ctypes.c_uint),
                                ("lpfn", ctypes.c_void_p),
                                ("lParam", ctypes.wintypes.LPARAM),
                                ("iImage", ctypes.c_int),
                            ]

                        # Try modern IFileDialog first (better UX)
                        try:
                            import subprocess
                            result = subprocess.run(
                                ['powershell', '-NoProfile', '-Command',
                                 'Add-Type -AssemblyName System.Windows.Forms; '
                                 '$f = New-Object System.Windows.Forms.FolderBrowserDialog; '
                                 '$f.Description = "Select folder containing .gguf model files"; '
                                 '$f.ShowNewFolderButton = $true; '
                                 'if ($f.ShowDialog() -eq "OK") { $f.SelectedPath } else { "" }'],
                                capture_output=True, text=True, timeout=120
                            )
                            path = result.stdout.strip()
                            return path if path else None
                        except Exception as e:
                            logger.warning(f"PowerShell folder dialog failed: {e}")
                            return None
                    except Exception as e:
                        logger.error(f"Folder dialog failed: {e}")
                        return None

                path = await asyncio.get_event_loop().run_in_executor(None, _open_folder_dialog)
                logger.debug(f"Folder dialog result: {path}")
                if path:
                    success = engine.set_local_models_directory(path)
                    models = engine.get_local_llm_models() if success else []
                    await websocket.send(json.dumps({'type': 'models_directory_set', 'payload': {
                        'success': success,
                        'path': path,
                        'models': models
                    }}))

        elif msg_type == 'browse_llm_model':
            logger.debug("[ws] browse_llm_model")
            if engine:
                def _open_gguf_dialog():
                    try:
                        import ctypes
                        import ctypes.wintypes
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
                        ofn.lpstrFilter = "GGUF Models (*.gguf)\0*.gguf\0All Files (*.*)\0*.*\0\0"
                        ofn.lpstrFile = file_buf
                        ofn.nMaxFile = 1024
                        ofn.lpstrTitle = "Select GGUF Model File"
                        ofn.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR

                        # Set initial dir to current models directory
                        models_dir = engine.get_local_models_directory()
                        if models_dir and os.path.isdir(models_dir):
                            ofn.lpstrInitialDir = models_dir

                        ctypes.windll.user32.SetForegroundWindow(
                            ctypes.windll.kernel32.GetConsoleWindow() or 0
                        )
                        if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
                            return file_buf.value or None
                        return None
                    except Exception as e:
                        logger.error(f"File dialog failed: {e}")
                        return None

                path = await asyncio.get_event_loop().run_in_executor(None, _open_gguf_dialog)
                logger.debug(f"GGUF file dialog result: {path}")
                if path:
                    # Set models directory to parent of selected file
                    parent_dir = os.path.dirname(path)
                    engine.set_local_models_directory(parent_dir)
                    models = engine.get_local_llm_models()
                    await websocket.send(json.dumps({'type': 'llm_model_browsed', 'payload': {
                        'path': path,
                        'directory': parent_dir,
                        'models': models
                    }}))

        elif msg_type == 'set_ai_api_key':
            logger.debug(f"[ws] set_ai_api_key: provider={payload.get('provider')}")
            if engine:
                provider = payload.get('provider', '')
                api_key = payload.get('api_key', '')
                success = engine.set_ai_api_key(provider, api_key)
                await websocket.send(json.dumps({'type': 'api_key_set', 'payload': {
                    'provider': provider,
                    'success': success
                }}))

        elif msg_type == 'check_ai_api_key':
            logger.debug(f"[ws] check_ai_api_key: provider={payload.get('provider')}")
            if engine:
                provider = payload.get('provider', '')
                has_key = engine.has_ai_api_key(provider)
                await websocket.send(json.dumps({'type': 'api_key_status', 'payload': {
                    'provider': provider,
                    'has_key': has_key
                }}))

        elif msg_type == 'clear_ai_conversation':
            logger.debug("[ws] clear_ai_conversation")
            if engine:
                engine.clear_ai_conversation()
                await websocket.send(json.dumps({'type': 'ai_conversation_cleared', 'payload': {}}))

        elif msg_type == 'overlay_show_text':
            logger.debug(f"[ws] overlay_show_text: message_type={payload.get('message_type')} duration={payload.get('duration')}")
            if engine:
                text = payload.get('text', '')
                message_type = payload.get('message_type', 'system')
                duration = payload.get('duration')
                engine.show_overlay_text(text, message_type, duration)
                await websocket.send(json.dumps({'type': 'overlay_text_shown', 'payload': {'text': text}}))

        elif msg_type == 'overlay_clear':
            logger.debug("[ws] overlay_clear")
            if engine:
                engine.clear_overlay()
                await websocket.send(json.dumps({'type': 'overlay_cleared', 'payload': {}}))

        elif msg_type == 'get_overlay_status':
            logger.debug("[ws] get_overlay_status")
            if engine:
                status = engine.get_vr_overlay_status()
                await websocket.send(json.dumps({'type': 'overlay_status', 'payload': status}))

        elif msg_type == 'start_speaker_capture':
            logger.debug("[ws] start_speaker_capture")
            if engine:
                await engine.start_speaker_capture()

        elif msg_type == 'stop_speaker_capture':
            logger.debug("[ws] stop_speaker_capture")
            if engine:
                await engine.stop_speaker_capture()

        elif msg_type == 'get_gpu_info':
            logger.debug("[ws] get_gpu_info")
            if engine:
                gpu_info = engine._get_gpu_info()
                await websocket.send(json.dumps({
                    'type': 'gpu_info',
                    'payload': gpu_info
                }))

        elif msg_type == 'get_loopback_devices':
            logger.debug("[ws] get_loopback_devices")
            if engine:
                devices = engine.get_loopback_devices()
                await websocket.send(json.dumps({
                    'type': 'loopback_devices',
                    'payload': {'devices': devices}
                }))

        # RVC Voice Conversion
        elif msg_type == 'rvc_scan_models':
            logger.debug(f"[ws] rvc_scan_models: directory={payload.get('directory')}")
            if engine:
                directory = payload.get('directory')
                await engine.rvc_scan_models(directory)

        elif msg_type == 'rvc_load_model':
            logger.debug(f"[ws] rvc_load_model: model_path={payload.get('model_path')} index_path={payload.get('index_path')}")
            if engine:
                model_path = payload.get('model_path', '')
                index_path = payload.get('index_path')
                await engine.rvc_load_model(model_path, index_path)

        elif msg_type == 'rvc_download_base_models':
            logger.debug("[ws] rvc_download_base_models")
            if engine:
                await engine.rvc_download_base_models()

        elif msg_type == 'rvc_enable':
            logger.debug(f"[ws] rvc_enable: enabled={payload.get('enabled')}")
            if engine:
                enabled = payload.get('enabled', False)
                await engine.rvc_enable(enabled)

        elif msg_type == 'rvc_set_params':
            logger.debug(f"[ws] rvc_set_params: {payload}")
            if engine:
                await engine.rvc_set_params(**payload)

        elif msg_type == 'rvc_unload':
            logger.debug("[ws] rvc_unload")
            if engine:
                await engine.rvc_unload()

        elif msg_type == 'rvc_get_status':
            logger.debug("[ws] rvc_get_status")
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
            logger.debug("[ws] rvc_test_voice")
            if engine:
                await engine.rvc_test_voice()

        elif msg_type == 'rvc_mic_start':
            logger.debug(f"[ws] rvc_mic_start: output_device_id={payload.get('output_device_id')}")
            if engine:
                output_device = payload.get('output_device_id')
                await engine.mic_rvc_start(output_device)

        elif msg_type == 'rvc_mic_stop':
            logger.debug("[ws] rvc_mic_stop")
            if engine:
                await engine.mic_rvc_stop()

        elif msg_type == 'rvc_mic_set_output_device':
            logger.debug(f"[ws] rvc_mic_set_output_device: device_id={payload.get('device_id')}")
            if engine:
                device_id = payload.get('device_id')
                await engine.mic_rvc_set_output_device(device_id)

        elif msg_type == 'rvc_set_device':
            logger.debug(f"[ws] rvc_set_device: device={payload.get('device')}")
            if engine:
                device = payload.get('device', 'cpu')
                await engine.rvc_set_device(device)

        elif msg_type == 'get_features_status':
            logger.debug("[ws] get_features_status")
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
            logger.debug(f"[ws] install_feature: feature_id={payload.get('feature_id')}")
            from utils.package_manager import install_feature

            feature_id = payload.get('feature_id', '')

            async def _progress(info):
                await broadcast({'type': 'feature_install_progress', 'payload': info})

            result = await install_feature(feature_id, progress_callback=_progress)

            # After RVC pip packages install, also download base models (HuBERT + RMVPE)
            if feature_id == 'rvc' and result.get('success'):
                try:
                    await _progress({'feature': 'rvc', 'stage': 'installing', 'detail': 'Downloading RVC base models (HuBERT + RMVPE)...'})
                    from ai.tts.rvc_postprocess import RVCPostProcessor
                    rvc_proc = RVCPostProcessor()
                    rvc_proc.on_progress = lambda stage, pct: asyncio.ensure_future(
                        broadcast({'type': 'feature_install_progress', 'payload': {
                            'feature': 'rvc', 'stage': 'installing',
                            'detail': f'Downloading {stage}... {int(pct*100)}%',
                        }})
                    )
                    rvc_proc.on_status = lambda event, data: None
                    success = await rvc_proc.download_base_models()
                    if not success:
                        await _progress({'feature': 'rvc', 'stage': 'installing', 'detail': 'Warning: base models download failed (can retry from RVC settings)'})
                except Exception as e:
                    import traceback
                    logger.error(f"RVC base models download failed: {e}\n{traceback.format_exc()}")
                    await _progress({'feature': 'rvc', 'stage': 'installing', 'detail': f'Warning: base models download failed: {e}'})

            # Flag restart needed after torch install (CUDA DLLs need fresh process)
            if 'torch' in feature_id and result.get('success') and getattr(sys, 'frozen', False):
                logger.info("[ws] Torch installed — restart will be needed for CUDA support")
                result['restart_needed'] = True

            await websocket.send(json.dumps({'type': 'feature_install_result', 'payload': result}))

        elif msg_type == 'uninstall_feature':
            logger.debug(f"[ws] uninstall_feature: feature_id={payload.get('feature_id')}")
            from utils.package_manager import uninstall_feature

            feature_id = payload.get('feature_id', '')
            logger.info(f"[ws] uninstall_feature: feature_id={feature_id}")

            async def _unprogress(info):
                logger.info(f"[ws] uninstall progress: {info}")
                await broadcast({'type': 'feature_uninstall_progress', 'payload': info})

            try:
                result = await uninstall_feature(feature_id, progress_callback=_unprogress)
                logger.info(f"[ws] uninstall_feature result: {result}")
                await websocket.send(json.dumps({'type': 'feature_uninstall_result', 'payload': result}))
            except Exception as e:
                import traceback
                logger.error(f"[ws] uninstall_feature EXCEPTION: {e}\n{traceback.format_exc()}")
                await websocket.send(json.dumps({'type': 'feature_uninstall_result', 'payload': {'success': False, 'feature': feature_id, 'error': str(e)}}))

        elif msg_type == 'restart_app':
            logger.info("[ws] restart_app requested by frontend")
            await broadcast({'type': 'app_restarting', 'payload': {'reason': 'Restarting for GPU support'}})
            await asyncio.sleep(1)
            # Launch new process, then kill ourselves
            import subprocess
            args = [sys.executable] + sys.argv[1:] + ['--no-browser']
            # Deduplicate --no-browser
            if args.count('--no-browser') > 1:
                args = [a for a in args if a != '--no-browser'] + ['--no-browser']
            subprocess.Popen(args,
                             creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0)
            logger.info("[ws] New process spawned, exiting current process")
            os._exit(0)

        elif msg_type == 'rvc_get_available_devices':
            logger.debug("[ws] rvc_get_available_devices")
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

    for arg in sys.argv[1:]:
        try:
            port = int(arg)
            break
        except ValueError:
            continue

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
