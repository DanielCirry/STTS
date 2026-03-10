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

logger = logging.getLogger('stts.standalone')


def _preload_torch_dlls(site_packages: Path):
    """Pre-load torch DLLs into process address space using ctypes.

    In PyInstaller frozen exes, os.add_dll_directory() doesn't reliably make
    DLLs findable for *transitive* dependencies. When torch._C.pyd loads
    torch_python.dll which needs torch_cpu.dll which needs c10.dll — the OS
    linker resolves each hop, and add_dll_directory may not apply to those
    intermediate lookups (WinError 126).

    Loading DLLs with ctypes.WinDLL() puts them directly in the process
    address space. The OS linker then finds them by name without searching.

    Multi-pass loading handles dependency order automatically.
    """
    import ctypes

    dirs_to_scan = []

    torch_lib = site_packages / 'torch' / 'lib'
    if torch_lib.exists():
        dirs_to_scan.append(torch_lib)

    torch_bin = site_packages / 'torch' / 'bin'
    if torch_bin.exists():
        dirs_to_scan.append(torch_bin)

    # CUDA: nvidia/*/lib/ and nvidia/*/bin/
    nvidia_dir = site_packages / 'nvidia'
    if nvidia_dir.exists():
        try:
            for pkg in nvidia_dir.iterdir():
                if pkg.is_dir():
                    for sub in ('lib', 'bin'):
                        d = pkg / sub
                        if d.exists():
                            dirs_to_scan.append(d)
        except OSError:
            pass

    if not dirs_to_scan:
        return

    all_dlls = []
    for d in dirs_to_scan:
        try:
            all_dlls.extend(d.glob('*.dll'))
        except OSError:
            pass

    if not all_dlls:
        return

    # Multi-pass: if torch_cpu.dll fails because c10.dll isn't loaded yet,
    # skip it and retry on the next pass
    remaining = list(all_dlls)
    loaded = 0
    last_errors = {}
    for pass_num in range(4):
        still_remaining = []
        for dll in remaining:
            try:
                ctypes.WinDLL(str(dll))
                loaded += 1
            except OSError as e:
                still_remaining.append(dll)
                last_errors[dll] = str(e)
        remaining = still_remaining
        if not remaining:
            break

    if remaining:
        logger.warning(f"Pre-loaded {loaded} torch DLLs, {len(remaining)} FAILED:")
        for dll in remaining[:10]:
            logger.warning(f"  FAILED: {dll.name} — {last_errors.get(dll, 'unknown')}")
    else:
        logger.debug(f"Pre-loaded {loaded} torch DLLs (all successful)")

    # Log CUDA DLL dirs found
    nvidia_dirs_found = [d for d in dirs_to_scan if 'nvidia' in str(d).lower()]
    if nvidia_dirs_found:
        logger.debug(f"NVIDIA DLL dirs ({len(nvidia_dirs_found)}): {[str(d) for d in nvidia_dirs_found]}")
    else:
        logger.debug("No NVIDIA DLL dirs found — CUDA torch may not work")


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

    # CUDA torch: add nvidia package DLL directories
    # (cublas, cuda_runtime, cudnn, etc. each have their own lib dir)
    nvidia_dir = site_packages / 'nvidia'
    if nvidia_dir.exists():
        try:
            for pkg in nvidia_dir.iterdir():
                if pkg.is_dir():
                    for lib_dir in [pkg / 'lib', pkg / 'bin']:
                        if lib_dir.exists():
                            lib_str = str(lib_dir)
                            if lib_str not in os.environ.get('PATH', ''):
                                os.environ['PATH'] = lib_str + os.pathsep + os.environ.get('PATH', '')
                            try:
                                os.add_dll_directory(lib_str)
                            except (AttributeError, OSError):
                                pass
        except OSError:
            pass

    # Pre-load DLLs directly into the process (most reliable for frozen exes)
    _preload_torch_dlls(site_packages)

    # Quick CUDA diagnostic after DLL setup
    try:
        import torch
        cuda_avail = torch.cuda.is_available()
        cuda_ver = getattr(torch.version, 'cuda', None)
        logger.info(f"[CUDA diag] torch.cuda.is_available()={cuda_avail}, torch.version.cuda={cuda_ver}, torch.__version__={torch.__version__}")
        if cuda_avail:
            logger.info(f"[CUDA diag] GPU: {torch.cuda.get_device_name(0)}, VRAM: {torch.cuda.get_device_properties(0).total_mem / 1024**3:.1f}GB")
        elif cuda_ver:
            logger.warning(f"[CUDA diag] CUDA torch installed (cuda={cuda_ver}) but torch.cuda.is_available()=False — DLL issue likely")
    except Exception as e:
        logger.debug(f"[CUDA diag] torch import failed (may not be installed yet): {e}")

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

try:
    from main import main as run_backend
except Exception as _import_err:
    # Crash during import — write crash log and show error
    import traceback
    _crash = traceback.format_exc()
    print(_crash)
    _crash_path = None
    try:
        _crash_path = Path(sys.executable).parent / 'crash.log' if getattr(sys, 'frozen', False) else Path('crash.log')
        with open(_crash_path, 'w') as _f:
            _f.write(_crash)
    except Exception:
        pass
    _msg = f"STTS failed to start.\n\n{type(_import_err).__name__}: {_import_err}"
    if _crash_path:
        _msg += f"\n\nDetails saved to:\n{_crash_path}"
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, _msg, 'STTS Startup Error', 0x10)
    except Exception:
        input("Press Enter to exit...")
    sys.exit(1)

# Logging is configured by main.py's setup_logging() (called on import above).


def _show_error(message: str, title: str = 'STTS Error'):
    """Show error via Windows MessageBox (visible even if console closes fast)."""
    print(message)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
    except Exception:
        input("Press Enter to exit...")


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
        # Prevent browser caching stale frontend builds
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_POST(self):
        """Handle POST requests (e.g. /shutdown)."""
        if self.path == '/shutdown':
            logger.info('[HTTP] Received /shutdown POST request')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"status":"shutting_down"}')
            # Schedule shutdown after response is sent
            def _do_shutdown():
                import time
                time.sleep(0.5)
                logger.info('[HTTP] Shutting down via HTTP endpoint')
                os._exit(0)
            shutdown_thread = threading.Thread(target=_do_shutdown, daemon=True)
            shutdown_thread.start()
            return
        self.send_error(404, 'Not Found')

    def do_OPTIONS(self):
        """Handle CORS preflight for POST requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


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
        _show_error("Frontend files not found!\n\nPlease run 'npm run build' first to build the frontend.")
        sys.exit(1)

    # Check if WebSocket port is already in use (previous instance still running)
    import socket
    import time as _time
    is_restart = '--no-browser' in sys.argv
    port_retries = 15 if is_restart else 1  # Restart: wait for old process to die
    port_free = False
    for _attempt in range(port_retries):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', WS_PORT))
            port_free = True
            break
        except OSError:
            if _attempt < port_retries - 1:
                print(f"Waiting for port {WS_PORT} to be released... ({_attempt + 1}/{port_retries})")
                _time.sleep(1)
    if not port_free:
        msg = (
            "Another instance of STTS is already running!\n\n"
            f"Port {WS_PORT} is in use.\n"
            "Close the other instance or check Task Manager for STTS.exe."
        )
        _show_error(msg)
        sys.exit(1)

    print(f"Frontend: {dist_path}")
    print(f"Backend:  ws://localhost:{WS_PORT}")
    print()

    # Start HTTP server for frontend in a thread
    http_thread = threading.Thread(target=run_http_server, args=(dist_path,), daemon=True)
    http_thread.start()

    # Open browser unless --no-browser was passed (e.g. auto-restart after torch install)
    if '--no-browser' not in sys.argv:
        def open_browser():
            import time
            time.sleep(2)
            webbrowser.open(f'http://localhost:{HTTP_PORT}')
            print(f"Opened browser to http://localhost:{HTTP_PORT}")
            print()
            print("STTS is running! Close this window to stop.")

        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()
    else:
        print("STTS is running! (restarted for GPU support)")
        print("Reconnecting to existing browser tab...")

    # Run the WebSocket backend (blocking)
    try:
        asyncio.run(run_backend())
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    try:
        main()
    except Exception as _e:
        import traceback
        _crash = traceback.format_exc()
        print(_crash)
        _crash_path = None
        try:
            _crash_path = Path(sys.executable).parent / 'crash.log' if getattr(sys, 'frozen', False) else Path('crash.log')
            with open(_crash_path, 'a') as _f:
                _f.write('\n--- runtime crash ---\n' + _crash)
        except Exception:
            pass
        _msg = f"STTS crashed unexpectedly.\n\n{type(_e).__name__}: {_e}"
        if _crash_path:
            _msg += f"\n\nDetails saved to:\n{_crash_path}"
        _show_error(_msg, 'STTS Crash')
