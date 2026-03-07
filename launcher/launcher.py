"""
STTS Launcher
Starts the backend and opens the frontend in browser
"""

import os
import sys
import time
import subprocess
import webbrowser
import socket
import atexit
from pathlib import Path

# Configuration
BACKEND_PORT = 9876
FRONTEND_PORT = 5173
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"

# Global process handles for cleanup
_backend_process = None
_frontend_process = None


def get_base_path():
    """Get the base path of the application."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent


def is_port_in_use(port):
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1', port)) == 0


def wait_for_port(port, timeout=30):
    """Wait for a port to become available."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(0.5)
    return False


def cleanup():
    """Cleanup function called on exit."""
    global _backend_process, _frontend_process

    if _frontend_process:
        try:
            _frontend_process.terminate()
            _frontend_process.wait(timeout=3)
        except:
            try:
                _frontend_process.kill()
            except:
                pass

    if _backend_process:
        try:
            _backend_process.terminate()
            _backend_process.wait(timeout=3)
        except:
            try:
                _backend_process.kill()
            except:
                pass


def main():
    global _backend_process, _frontend_process

    # Register cleanup
    atexit.register(cleanup)

    print("=" * 50)
    print("  STTS - Speech to Text to Speech")
    print("=" * 50)
    print()

    base_path = get_base_path()
    print(f"Base path: {base_path}")

    # === START BACKEND ===
    if is_port_in_use(BACKEND_PORT):
        print(f"[OK] Backend already running on port {BACKEND_PORT}")
    else:
        backend_exe = base_path / "python" / "dist" / "stts-backend.exe"
        backend_script = base_path / "python" / "main.py"

        if backend_exe.exists():
            print(f"Starting backend: {backend_exe}")
            _backend_process = subprocess.Popen(
                [str(backend_exe)],
                cwd=str(base_path / "python"),
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
            )
        elif backend_script.exists():
            print(f"Starting backend (dev): {backend_script}")
            _backend_process = subprocess.Popen(
                ["python", str(backend_script)],
                cwd=str(base_path / "python"),
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
            )
        else:
            print("ERROR: Backend not found!")
            input("Press Enter to exit...")
            return 1

        # Wait for backend
        print("Waiting for backend...")
        if wait_for_port(BACKEND_PORT, timeout=30):
            print(f"[OK] Backend ready on port {BACKEND_PORT}")
        else:
            print("[WARN] Backend may not have started properly")

    # === START FRONTEND ===
    if is_port_in_use(FRONTEND_PORT):
        print(f"[OK] Frontend already running on port {FRONTEND_PORT}")
    else:
        dist_index = base_path / "dist" / "index.html"

        if dist_index.exists():
            # Serve built frontend - use explicit binding
            print(f"Starting frontend server on port {FRONTEND_PORT}...")
            _frontend_process = subprocess.Popen(
                [sys.executable, "-m", "http.server", str(FRONTEND_PORT), "--bind", "127.0.0.1"],
                cwd=str(base_path / "dist"),
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
            )
        else:
            # Dev mode - use npm
            print("Starting frontend dev server...")
            _frontend_process = subprocess.Popen(
                ["cmd", "/c", "npm", "run", "dev"],
                cwd=str(base_path),
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
            )

        # Wait for frontend
        print("Waiting for frontend...")
        if wait_for_port(FRONTEND_PORT, timeout=30):
            print(f"[OK] Frontend ready on port {FRONTEND_PORT}")
        else:
            print("[WARN] Frontend may not have started properly")

    # === OPEN BROWSER ===
    print()
    print(f"Opening browser: {FRONTEND_URL}")
    webbrowser.open(FRONTEND_URL)

    print()
    print("=" * 50)
    print("  STTS is running!")
    print("  Press Ctrl+C or close this window to stop")
    print("=" * 50)
    print()

    # Keep alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
