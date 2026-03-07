# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for STTS Standalone
Builds a complete standalone application
"""

import sys
from pathlib import Path

base_path = Path(SPECPATH)
dist_path = base_path.parent / 'dist'

block_cipher = None

# Hidden imports
hidden_imports = [
    'asyncio',
    'websockets',
    'numpy',
    'sounddevice',
    'soundfile',
    'webrtcvad',
    'faster_whisper',
    'ctranslate2',
    'tokenizers',
    'torch',
    'torchaudio',
    'edge_tts',
    'pyttsx3',
    'llama_cpp',
    'openai',
    'anthropic',
    'groq',
    'google.generativeai',
    'openvr',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'pythonosc',
    'keyring',
    'keyring.backends',
    'keyring.backends.Windows',
    'soundcard',
    'http.server',
    'socketserver',
    'webbrowser',
]

# Include the frontend dist folder
datas = []
if dist_path.exists():
    datas.append((str(dist_path), 'dist'))

a = Analysis(
    ['standalone.py'],
    pathex=[str(base_path)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas', 'pytest'],
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
    name='STTS',
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
    icon=None,
)
