# Runtime hook: ensure CUDA DLLs are on PATH when running from PyInstaller bundle
import os
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # Add torch's lib directory to PATH so CUDA DLLs are found
    torch_lib = Path(sys._MEIPASS) / 'torch' / 'lib'
    if torch_lib.exists():
        os.environ['PATH'] = str(torch_lib) + os.pathsep + os.environ.get('PATH', '')
