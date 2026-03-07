# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for STTS All-in-One Application
Bundles the backend, launcher, and frontend into a single executable
"""

import os
from pathlib import Path

block_cipher = None

# Paths
PROJECT_ROOT = Path('C:/repos/STTS')
PYTHON_DIR = PROJECT_ROOT / 'python'
DIST_DIR = PROJECT_ROOT / 'dist'

# Collect frontend files
frontend_datas = []
if DIST_DIR.exists():
    for root, dirs, files in os.walk(DIST_DIR):
        for file in files:
            src = Path(root) / file
            rel_path = src.relative_to(DIST_DIR)
            dst = Path('dist') / rel_path.parent
            frontend_datas.append((str(src), str(dst)))

a = Analysis(
    ['stts_launcher.py'],
    pathex=[str(PYTHON_DIR)],
    binaries=[
        # Include the backend executable
        (str(PYTHON_DIR / 'dist' / 'stts-backend.exe'), '.'),
    ],
    datas=frontend_datas,
    hiddenimports=[
        'http.server',
        'socketserver',
        'webbrowser',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Don't include ML libraries in launcher
        'torch',
        'transformers',
        'faster_whisper',
        'numpy',
        'sounddevice',
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
    name='STTS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / 'src-tauri' / 'icons' / 'icon.ico') if (PROJECT_ROOT / 'src-tauri' / 'icons' / 'icon.ico').exists() else None,
)
