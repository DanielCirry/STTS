# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for STTS Backend
Creates a standalone executable with core dependencies.
ML dependencies (torch, whisper, etc.) should be pip installed separately.
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['C:\\repos\\STTS\\python'],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Core websocket/async
        'websockets',
        'websockets.server',
        'websockets.legacy',
        'websockets.legacy.server',
        'websockets.exceptions',
        'asyncio',
        # Audio
        'sounddevice',
        '_sounddevice_data',
        'numpy',
        'numpy.core',
        'numpy.core._multiarray_umath',
        'webrtcvad',
        # Config
        'yaml',
        # OSC
        'pythonosc',
        'pythonosc.osc_server',
        'pythonosc.dispatcher',
        'pythonosc.osc_message_builder',
        'pythonosc.udp_client',
        # Standard lib
        'logging',
        'json',
        'threading',
        'queue',
        'signal',
        'time',
        'io',
        'wave',
        # Edge TTS (online, no heavy deps)
        'edge_tts',
        'aiohttp',
        # Windows TTS
        'pyttsx3',
        'pyttsx3.drivers',
        'pyttsx3.drivers.sapi5',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy ML - users install separately
        'torch',
        'torchvision',
        'torchaudio',
        'transformers',
        'faster_whisper',
        'ctranslate2',
        'llama_cpp',
        'llama_cpp_python',
        'openvr',
        'piper_tts',
        'onnxruntime',
        'openai',
        'anthropic',
        'groq',
        'google',
        'google.generativeai',
        'huggingface_hub',
        'sentencepiece',
        'soundcard',
        'PIL',
        'pillow',
        # Unused
        'tkinter',
        'matplotlib',
        'pandas',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='stts-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
