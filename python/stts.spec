# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for STTS Python backend
Builds the WebSocket server as a standalone executable
"""

import sys
from pathlib import Path

# Get the base path
base_path = Path(SPECPATH)

# Collect all Python files
block_cipher = None

# Hidden imports for dynamic imports
hidden_imports = [
    # Core
    'asyncio',
    'websockets',
    'numpy',

    # Audio
    'sounddevice',
    'soundfile',
    'webrtcvad',

    # ML/AI
    'faster_whisper',
    'ctranslate2',
    'tokenizers',
    'transformers',
    'sentencepiece',
    'torch',
    'torchaudio',

    # TTS
    'edge_tts',
    'pyttsx3',

    # LLM
    'llama_cpp',
    'openai',
    'anthropic',
    'groq',
    'google.generativeai',

    # VR
    'openvr',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',

    # OSC
    'pythonosc',

    # Utils
    'keyring',
    'keyring.backends',
    'keyring.backends.Windows',

    # Audio capture
    'soundcard',
]

# Data files to include
datas = []

# Binary files (DLLs, etc.)
binaries = []

a = Analysis(
    ['main.py'],
    pathex=[str(base_path)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # GUI frameworks (not used)
        'tkinter',
        'PyQt5',
        'pyqt5_sip',
        'qt5_applications',
        'pythonwin',

        # Data science (not used)
        'matplotlib',
        'scipy',
        'pandas',
        'pytest',

        # Unused ML/compute
        'bitsandbytes',
        'torchvision',
        'numba',
        'llvmlite',
        'tensorboard',
        'tensorboardX',
        'sympy',
        'networkx',

        # Unused media
        'av',

        # Unused cloud/network
        'googleapiclient',
        'google_api_core',
        'grpc',
        'grpcio',
        'grpc_status',

        # Misc unused
        'pygments',
        'cryptography',
        'pip',
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
    console=True,  # Keep console for debugging, set to False for release
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if desired
)
