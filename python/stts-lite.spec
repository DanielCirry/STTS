# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for STTS Lite (minimal dependencies)
Builds a --onedir bundle: dist/STTS-Lite/STTS.exe
No torch, whisper, translation, local LLM, or RVC bundled.
User installs heavy deps separately if needed.
"""

import os
from pathlib import Path

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).parent
PYTHON_DIR = Path(SPECPATH)
DIST_DIR = PROJECT_ROOT / 'dist'

# Collect frontend files
frontend_datas = []
if DIST_DIR.exists() and (DIST_DIR / 'index.html').exists():
    frontend_datas.append((str(DIST_DIR), 'dist'))

hidden_imports = [
    # --- Core async/networking ---
    'asyncio',
    'websockets',
    'websockets.server',
    'websockets.legacy',
    'websockets.legacy.server',
    'websockets.exceptions',
    'aiohttp',
    'aiohttp.connector',

    # --- Audio ---
    'sounddevice',
    '_sounddevice_data',
    'numpy',
    'numpy.core',
    'numpy.core._multiarray_umath',
    'webrtcvad',
    'soundcard',
    'soundcard.mediafoundation',

    # --- TTS (online/lightweight only) ---
    'edge_tts',
    'pyttsx3',
    'pyttsx3.drivers',
    'pyttsx3.drivers.sapi5',

    # --- Cloud AI providers (lightweight, just HTTP calls) ---
    'openai',
    'anthropic',
    'groq',
    'google.generativeai',
    'google.generativeai.types',

    # --- VR ---
    'openvr',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL.ImageFilter',

    # --- OSC ---
    'pythonosc',
    'pythonosc.osc_server',
    'pythonosc.dispatcher',
    'pythonosc.osc_message_builder',
    'pythonosc.udp_client',

    # --- Keyring ---
    'keyring',
    'keyring.backends',
    'keyring.backends.Windows',

    # --- HTTP/networking ---
    'requests',
    'urllib3',
    'certifi',

    # --- Misc ---
    'yaml',
    'numpy',
    'packaging',
    'packaging.version',
    'timeit',
    'bisect',
    'copy',
    'decimal',
    'fractions',
    'numbers',
    'statistics',
    'comtypes',
    'comtypes.client',

    # --- Stdlib modules needed by torch/RVC/transformers at runtime ---
    'pickletools',
    'unittest',
    'unittest.mock',
    'filecmp',
    'cProfile',
    'pstats',
    'profile',
    'shelve',
    'dbm',
    'dbm.dumb',

    # --- HTTP server for frontend ---
    'http.server',
    'socketserver',
    'webbrowser',
    'multiprocessing',
]

# Exclude ALL heavy ML deps — user installs separately
excludes = [
    # ML/AI (heavy)
    'torch', 'torchvision', 'torchaudio',
    'transformers', 'sentencepiece',
    'faster_whisper', 'ctranslate2', 'tokenizers',
    'llama_cpp', 'llama_cpp_python',
    'onnxruntime',
    'scipy',
    'soundfile',
    'huggingface_hub',

    # GUI frameworks
    'tkinter', 'PyQt5', 'pyqt5_sip', 'qt5_applications', 'pythonwin',
    # Data science
    'matplotlib', 'pandas', 'pytest',
    # Unused
    'bitsandbytes', 'numba', 'llvmlite',
    'tensorboard', 'tensorboardX', 'sympy', 'networkx',
    'caffe2', 'av',
    'googleapiclient', 'google_api_core', 'grpc', 'grpcio',
    # Test/dev
    'doctest', '_pytest', 'distutils', 'setuptools',
    'IPython', 'jupyter', 'notebook',
    'turtle', 'idlelib',
    'pygments', 'cryptography', 'pip',
]

a = Analysis(
    ['standalone.py'],
    pathex=[str(PYTHON_DIR)],
    binaries=[],
    datas=frontend_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='STTS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX compression triggers AV heuristics — keep disabled
    runtime_tmpdir=None,
    console=True,             # Visible console window reduces AV false positives
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,   # TODO: Set to signing identity for production builds
    entitlements_file=None,
    icon=str(PROJECT_ROOT / 'assets' / 'stts-icon.ico'),
    version=str(PYTHON_DIR / 'version_info.py'),  # Embedded version info reduces AV flags
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,               # UPX compression triggers AV heuristics — keep disabled
    name='STTS-Lite',
)
