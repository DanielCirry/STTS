"""
STTS Standalone Launcher
Runs both the WebSocket backend and serves the frontend
"""

import asyncio
import logging
import os
import sys
import webbrowser
from pathlib import Path
import http.server
import socketserver
import threading

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def setup_torch_dll_dirs(site_packages: Path = None):
    """Set up DLL directories for torch loaded from external venv.

    Must be called BEFORE importing torch. Safe to call multiple times
    (e.g. after installing torch via Features Manager).

    On Windows, Python 3.8+ no longer searches PATH for DLLs by default.
    We must use os.add_dll_directory() so torch can find its C extensions
    (c10.dll, torch_cpu.dll, etc.).
    """
    if site_packages is None:
        if getattr(sys, 'frozen', False):
            site_packages = Path(sys.executable).parent / 'venv' / 'Lib' / 'site-packages'
        else:
            return  # Not needed when running from source

    torch_lib = site_packages / 'torch' / 'lib'
    if not torch_lib.exists():
        return

    # Add to PATH (fallback for older Python / edge cases)
    path_str = str(torch_lib)
    if path_str not in os.environ.get('PATH', ''):
        os.environ['PATH'] = path_str + os.pathsep + os.environ.get('PATH', '')

    # Add DLL directory (required for Python 3.8+ on Windows)
    try:
        os.add_dll_directory(path_str)
    except (AttributeError, OSError):
        pass

    # Also add torch/bin if it exists (some torch builds put DLLs there)
    torch_bin = site_packages / 'torch' / 'bin'
    if torch_bin.exists():
        bin_str = str(torch_bin)
        if bin_str not in os.environ.get('PATH', ''):
            os.environ['PATH'] = bin_str + os.pathsep + os.environ.get('PATH', '')
        try:
            os.add_dll_directory(bin_str)
        except (AttributeError, OSError):
            pass

# If running from PyInstaller, check for an external venv with extra packages
# This lets users pip install heavy deps (torch, whisper, etc.) next to the exe
if getattr(sys, 'frozen', False):
    _app_dir = Path(sys.executable).parent
    _ext_site_packages = _app_dir / 'venv' / 'Lib' / 'site-packages'
    if _ext_site_packages.exists():
        sys.path.insert(0, str(_ext_site_packages))
    # Also check for venv/Scripts for DLLs (e.g. torch)
    _ext_scripts = _app_dir / 'venv' / 'Scripts'
    if _ext_scripts.exists():
        os.environ['PATH'] = str(_ext_scripts) + os.pathsep + os.environ.get('PATH', '')
    setup_torch_dll_dirs(_ext_site_packages)

from main import main as run_backend

# Logging is configured by main.py's setup_logging() (called on import above).
# No need to call basicConfig here — it would be a no-op anyway.
logger = logging.getLogger('stts.standalone')

# HTTP Server for frontend
def _find_free_port(preferred=5173):
    """Find a free port, starting with the preferred one."""
    import socket
    for port in [preferred] + list(range(5174, 5200)):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    return 0

HTTP_PORT = _find_free_port()
WS_PORT = 9876


class QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that serves the frontend and suppresses logs."""

    def __init__(self, *args, directory=None, **kwargs):
        self.directory = directory
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs

    def end_headers(self):
        # Add CORS headers for WebSocket
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()


def find_frontend_dist():
    """Find the frontend dist directory."""
    # Check various possible locations
    possible_paths = []

    if getattr(sys, 'frozen', False):
        # PyInstaller --onedir: exe is in dist/STTS/STTS.exe, frontend at dist/STTS/dist/
        possible_paths.append(Path(sys._MEIPASS) / 'dist')
        possible_paths.append(Path(sys.executable).parent / 'dist')
    else:
        possible_paths.append(Path(__file__).parent.parent / 'dist')  # Development
        possible_paths.append(Path(__file__).parent / 'dist')

    possible_paths.append(Path.cwd() / 'dist')  # Current directory

    for path in possible_paths:
        if path.exists() and (path / 'index.html').exists():
            return path

    return None


def run_http_server(directory: Path):
    """Run HTTP server for frontend in a thread."""
    handler = lambda *args, **kwargs: QuietHTTPHandler(*args, directory=str(directory), **kwargs)

    with socketserver.TCPServer(("127.0.0.1", HTTP_PORT), handler) as httpd:
        logger.debug(f"Frontend server running on http://localhost:{HTTP_PORT}")
        httpd.serve_forever()


def main():
    """Main entry point for standalone mode."""
    print("=" * 50)
    print("  STTS - Speech to Text to Speech")
    print("=" * 50)
    print()

    # Find frontend
    dist_path = find_frontend_dist()
    if not dist_path:
        print("ERROR: Frontend files not found!")
        print("Please run 'npm run build' first to build the frontend.")
        input("Press Enter to exit...")
        sys.exit(1)

    print(f"Frontend: {dist_path}")
    print(f"Backend:  ws://localhost:{WS_PORT}")
    print()

    # Start HTTP server for frontend in a thread
    http_thread = threading.Thread(target=run_http_server, args=(dist_path,), daemon=True)
    http_thread.start()

    # Wait a moment then open browser
    def open_browser():
        import time
        time.sleep(2)
        webbrowser.open(f'http://localhost:{HTTP_PORT}')
        print(f"Opened browser to http://localhost:{HTTP_PORT}")
        print()
        print("STTS is running! Close this window to stop.")

    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # Run the WebSocket backend (blocking)
    try:
        asyncio.run(run_backend())
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
