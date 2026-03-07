"""
STTS All-in-One Launcher
Starts the backend, serves the frontend, and opens the browser
"""

import asyncio
import http.server
import json
import logging
import os
import signal
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('stts.launcher')

# Configuration
BACKEND_PORT = 9876
FRONTEND_PORT = 8080
DIST_DIR = None  # Set at runtime


class QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that serves files and handles SPA routing."""

    def __init__(self, *args, directory=None, **kwargs):
        self.directory = directory
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        # Suppress default logging
        pass

    def do_GET(self):
        # Handle SPA routing - serve index.html for non-file routes
        path = self.path.split('?')[0]  # Remove query string

        # Check if file exists
        file_path = Path(self.directory) / path.lstrip('/')

        if not file_path.exists() and not path.startswith('/assets'):
            # Serve index.html for SPA routes
            self.path = '/index.html'

        return super().do_GET()

    def end_headers(self):
        # Add CORS and CSP headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()


class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Threaded HTTP server for concurrent requests."""
    allow_reuse_address = True
    daemon_threads = True


def find_dist_dir():
    """Find the frontend dist directory."""
    # Check relative paths from different locations
    candidates = [
        Path(__file__).parent.parent / 'dist',  # From python/
        Path(__file__).parent / 'dist',  # From current dir
        Path.cwd() / 'dist',  # From working directory
        Path.cwd().parent / 'dist',  # One level up
    ]

    for candidate in candidates:
        index_file = candidate / 'index.html'
        if index_file.exists():
            return candidate.resolve()

    return None


def find_backend_exe():
    """Find the backend executable."""
    candidates = [
        Path(__file__).parent / 'dist' / 'stts-backend.exe',
        Path(__file__).parent / 'stts-backend.exe',
        Path.cwd() / 'stts-backend.exe',
        Path.cwd() / 'python' / 'dist' / 'stts-backend.exe',
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return None


def start_backend():
    """Start the Python backend server."""
    backend_exe = find_backend_exe()

    if backend_exe:
        logger.debug(f"Starting backend from: {backend_exe}")
        return subprocess.Popen(
            [str(backend_exe), str(BACKEND_PORT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
    else:
        # Try running from source
        main_py = Path(__file__).parent / 'main.py'
        if main_py.exists():
            logger.debug(f"Starting backend from source: {main_py}")
            return subprocess.Popen(
                [sys.executable, str(main_py), str(BACKEND_PORT)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
        else:
            logger.error("Could not find backend executable or source")
            return None


def start_frontend_server(dist_dir, port):
    """Start the HTTP server for the frontend."""
    handler = lambda *args, **kwargs: QuietHTTPHandler(*args, directory=str(dist_dir), **kwargs)

    try:
        server = ThreadedHTTPServer(('127.0.0.1', port), handler)
        logger.debug(f"Frontend server started on http://127.0.0.1:{port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Failed to start frontend server: {e}")


def wait_for_backend(timeout=10):
    """Wait for backend to be ready."""
    import socket

    start = time.time()
    while time.time() - start < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', BACKEND_PORT))
            sock.close()
            if result == 0:
                return True
        except:
            pass
        time.sleep(0.5)

    return False


def main():
    global DIST_DIR

    print("=" * 50)
    print("  STTS - Speech to Text to Speech")
    print("=" * 50)
    print()

    # Find directories
    DIST_DIR = find_dist_dir()
    if not DIST_DIR:
        print("ERROR: Could not find frontend dist directory.")
        print("Please run 'npm run build' first.")
        input("Press Enter to exit...")
        sys.exit(1)

    logger.debug(f"Frontend directory: {DIST_DIR}")

    # Start backend
    print("Starting backend server...")
    backend_process = start_backend()

    if not backend_process:
        print("ERROR: Could not start backend server.")
        input("Press Enter to exit...")
        sys.exit(1)

    # Wait for backend to be ready
    print("Waiting for backend to initialize...")
    if not wait_for_backend():
        print("WARNING: Backend may not have started properly.")
    else:
        print(f"Backend running on ws://127.0.0.1:{BACKEND_PORT}")

    # Start frontend server in a thread
    print("Starting frontend server...")
    frontend_thread = threading.Thread(
        target=start_frontend_server,
        args=(DIST_DIR, FRONTEND_PORT),
        daemon=True
    )
    frontend_thread.start()
    time.sleep(0.5)

    print(f"Frontend running on http://127.0.0.1:{FRONTEND_PORT}")
    print()
    print("=" * 50)
    print("  STTS is running!")
    print("=" * 50)
    print()

    # Open browser
    url = f"http://127.0.0.1:{FRONTEND_PORT}"
    print(f"Opening browser to {url}")
    webbrowser.open(url)

    print()
    print("Press Ctrl+C to stop...")
    print()

    # Keep running until interrupted
    try:
        while True:
            # Check if backend is still running
            if backend_process.poll() is not None:
                # Backend exited, read output
                output = backend_process.stdout.read().decode('utf-8', errors='ignore')
                if output:
                    print("Backend output:")
                    print(output)
                print("Backend process exited unexpectedly.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Clean up
        if backend_process and backend_process.poll() is None:
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()

        print("STTS stopped.")


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
