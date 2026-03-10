"""
VOICEVOX Engine Setup & Lifecycle Manager.
Downloads, installs, and manages the VOICEVOX Engine (API-only) process.
"""

import asyncio
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

import aiohttp

logger = logging.getLogger('stts.voicevox_setup')

DEFAULT_INSTALL_DIR = Path(os.environ.get('APPDATA', Path.home() / '.stts')) / 'STTS' / 'voicevox-engine'
GITHUB_API_LATEST = 'https://api.github.com/repos/VOICEVOX/voicevox_engine/releases/latest'
ENGINE_EXECUTABLE = 'run.exe'
ENGINE_PORT = 50021

# Asset name patterns for Windows builds
ASSET_PATTERN = re.compile(
    r'voicevox_engine-windows-(directml|cpu)-[\d.]+\.7z\.001$'
)


class VoicevoxEngineManager:
    """Manages VOICEVOX Engine download, installation, and process lifecycle."""

    def __init__(
        self,
        install_dir: Optional[Path] = None,
        on_progress: Optional[Callable[[str, float, str], None]] = None,
        on_status: Optional[Callable[[str, Dict], None]] = None,
    ):
        self._install_dir = install_dir or DEFAULT_INSTALL_DIR
        self._on_progress = on_progress or (lambda *_: None)
        self._on_status = on_status or (lambda *_: None)
        self._process: Optional[subprocess.Popen] = None
        self._cancel_requested = False
        self._start_cancelled = False
        self._run_exe_path: Optional[Path] = None

    # ── Status ──────────────────────────────────────────────────────────

    def get_install_status(self) -> Dict:
        """Get current installation and engine status."""
        exe = self._find_run_exe()
        free_gb = 0.0
        try:
            usage = shutil.disk_usage(self._install_dir.anchor or self._install_dir)
            free_gb = round(usage.free / (1024 ** 3), 1)
        except Exception:
            pass

        return {
            'installed': exe is not None,
            'install_path': str(self._install_dir),
            'engine_running': self.is_engine_running(),
            'engine_pid': self._process.pid if self._process and self._process.poll() is None else None,
            'disk_space_gb': free_gb,
        }

    def is_engine_running(self) -> bool:
        """Check if the managed engine process is alive."""
        return self._process is not None and self._process.poll() is None

    # ── GitHub Release ──────────────────────────────────────────────────

    async def fetch_latest_release(self) -> Dict:
        """Query GitHub API for the latest VOICEVOX Engine release.

        Returns:
            Dict with 'version' and 'assets' (filtered to Windows builds).
        """
        timeout = aiohttp.ClientTimeout(total=15)
        headers = {'Accept': 'application/vnd.github.v3+json'}

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(GITHUB_API_LATEST, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"GitHub API returned {resp.status}")
                release = await resp.json()

        version = release.get('tag_name', '').lstrip('v') or release.get('name', 'unknown')
        assets = []
        for asset in release.get('assets', []):
            name = asset.get('name', '')
            match = ASSET_PATTERN.match(name)
            if match:
                assets.append({
                    'name': name,
                    'size_bytes': asset.get('size', 0),
                    'download_url': asset.get('browser_download_url', ''),
                    'build_type': match.group(1),
                })

        return {'version': version, 'assets': assets}

    # ── Download & Install ──────────────────────────────────────────────

    async def download_and_install(self, build_type: str = 'directml') -> bool:
        """Download and install VOICEVOX Engine.

        Args:
            build_type: 'directml' or 'cpu'

        Returns:
            True on success.
        """
        self._cancel_requested = False
        self._on_progress('downloading', 0.0, 'Fetching release info...')

        try:
            release = await self.fetch_latest_release()
        except Exception as e:
            self._on_progress('error', 0.0, f'Failed to fetch release: {e}')
            return False

        # Find matching assets (may be multi-part: .7z.001, .7z.002, ...)
        assets = [a for a in release['assets'] if a['build_type'] == build_type]
        if not assets:
            self._on_progress('error', 0.0, f'No {build_type} build found in release')
            return False

        total_size = sum(a['size_bytes'] for a in assets)
        total_mb = total_size / (1024 * 1024)

        # Prepare directories
        self._install_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = self._install_dir / '_download_temp'
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Download all parts
        downloaded_bytes = 0
        last_report = 0.0
        timeout = aiohttp.ClientTimeout(total=3600, sock_read=120)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for asset in sorted(assets, key=lambda a: a['name']):
                    dest = temp_dir / asset['name']
                    logger.debug(f"Downloading {asset['name']} ({asset['size_bytes'] / 1024 / 1024:.0f} MB)")

                    async with session.get(asset['download_url']) as resp:
                        if resp.status != 200:
                            self._on_progress('error', 0.0, f"Download failed: HTTP {resp.status}")
                            return False

                        with open(dest, 'wb') as f:
                            async for chunk in resp.content.iter_chunked(256 * 1024):
                                if self._cancel_requested:
                                    self._on_progress('error', 0.0, 'Download cancelled')
                                    shutil.rmtree(temp_dir, ignore_errors=True)
                                    return False
                                f.write(chunk)
                                downloaded_bytes += len(chunk)

                                now = time.monotonic()
                                if now - last_report >= 0.5:
                                    pct = (downloaded_bytes / total_size) * 100
                                    dl_mb = downloaded_bytes / (1024 * 1024)
                                    self._on_progress(
                                        'downloading', pct,
                                        f'{dl_mb:.0f} / {total_mb:.0f} MB'
                                    )
                                    last_report = now

            self._on_progress('downloading', 100.0, f'{total_mb:.0f} / {total_mb:.0f} MB')

        except Exception as e:
            self._on_progress('error', 0.0, f'Download error: {e}')
            shutil.rmtree(temp_dir, ignore_errors=True)
            return False

        # Extract
        self._on_progress('extracting', 0.0, 'Extracting VOICEVOX Engine...')
        first_part = temp_dir / sorted(a['name'] for a in assets)[0]

        try:
            success = await asyncio.get_event_loop().run_in_executor(
                None, self._extract_7z, first_part
            )
            if not success:
                return False
        except Exception as e:
            self._on_progress('error', 0.0, f'Extraction error: {e}')
            shutil.rmtree(temp_dir, ignore_errors=True)
            return False

        # Cleanup temp
        shutil.rmtree(temp_dir, ignore_errors=True)

        # Verify
        self._run_exe_path = None  # clear cache
        exe = self._find_run_exe()
        if exe:
            self._on_progress('complete', 100.0, 'Installation complete')
            logger.debug(f"VOICEVOX Engine installed at {exe.parent}")
            return True
        else:
            self._on_progress('error', 0.0, f'{ENGINE_EXECUTABLE} not found after extraction')
            return False

    def _extract_7z(self, archive_path: Path) -> bool:
        """Extract a 7z archive to the install directory (runs in executor)."""
        try:
            import py7zr
        except ImportError:
            self._on_progress('error', 0.0, 'py7zr not installed')
            return False

        try:
            with py7zr.SevenZipFile(str(archive_path), mode='r') as z:
                all_files = z.getnames()
                total = len(all_files)
                logger.debug(f"Extracting {total} files from {archive_path.name}")
                z.extractall(path=str(self._install_dir))
                self._on_progress('extracting', 100.0, f'Extracted {total} files')
            return True
        except Exception as e:
            logger.error(f"7z extraction failed: {e}")
            self._on_progress('error', 0.0, f'Extraction failed: {e}')
            return False

    # ── Engine Lifecycle ────────────────────────────────────────────────

    async def start_engine(self) -> bool:
        """Start the VOICEVOX Engine process.

        Returns:
            True if engine is running and responding.
        """
        if self.is_engine_running():
            return True

        exe = self._find_run_exe()
        if not exe:
            logger.error("Cannot start VOICEVOX: run.exe not found")
            return False

        self._start_cancelled = False
        logger.debug(f"Starting VOICEVOX Engine: {exe}")
        try:
            self._process = subprocess.Popen(
                [str(exe), '--host', '127.0.0.1', '--port', str(ENGINE_PORT)],
                cwd=str(exe.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
        except Exception as e:
            logger.error(f"Failed to start VOICEVOX: {e}")
            return False

        # Wait for engine to respond
        timeout = aiohttp.ClientTimeout(total=3)
        for i in range(60):
            await asyncio.sleep(1)
            # Check if stop_engine() was called while we were waiting
            if self._start_cancelled:
                logger.debug("VOICEVOX start_engine cancelled by stop_engine()")
                return False
            proc = self._process  # local ref — stop_engine may set to None
            if proc is None:
                logger.debug("VOICEVOX process was cleared (stop called during start)")
                return False
            if proc.poll() is not None:
                # Capture output to understand why it crashed
                try:
                    out = proc.stdout.read().decode('utf-8', errors='ignore')[-2000:] if proc.stdout else ''
                    logger.error(f"VOICEVOX process exited prematurely (code={proc.returncode}). Output:\n{out}")
                except Exception:
                    logger.error(f"VOICEVOX process exited prematurely (code={proc.returncode})")
                self._process = None
                return False
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(f'http://127.0.0.1:{ENGINE_PORT}/version') as resp:
                        if resp.status == 200:
                            version = await resp.text()
                            logger.debug(f"VOICEVOX Engine started, version: {version}")
                            return True
            except Exception:
                continue

        logger.error("VOICEVOX Engine did not respond within 60 seconds")
        self.stop_engine()
        return False

    def stop_engine(self):
        """Stop the VOICEVOX Engine process (managed or orphaned)."""
        self._start_cancelled = True  # abort any in-flight start_engine polling
        # Stop managed process
        if self._process and self._process.poll() is None:
            logger.debug("Stopping managed VOICEVOX Engine")
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"Error stopping VOICEVOX: {e}")
        self._process = None

        # Also kill any orphaned run.exe on our port
        self._kill_orphaned_engine()

    def cancel(self):
        """Cancel an in-progress download."""
        self._cancel_requested = True

    def uninstall(self) -> bool:
        """Remove the VOICEVOX Engine installation."""
        self.stop_engine()
        # Give processes time to release file handles
        time.sleep(1)
        try:
            if self._install_dir.exists():
                shutil.rmtree(self._install_dir)
                logger.debug("VOICEVOX Engine uninstalled")
            self._run_exe_path = None
            return True
        except Exception as e:
            logger.error(f"Uninstall failed: {e}")
            return False

    # ── Helpers ─────────────────────────────────────────────────────────

    def _kill_orphaned_engine(self):
        """Kill any run.exe process listening on ENGINE_PORT."""
        try:
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True, text=True, timeout=5,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            for line in result.stdout.splitlines():
                if f':{ENGINE_PORT}' in line and 'LISTENING' in line:
                    parts = line.split()
                    pid = int(parts[-1])
                    if pid > 0:
                        logger.debug(f"Killing orphaned VOICEVOX process (PID {pid})")
                        subprocess.run(
                            ['taskkill', '/PID', str(pid), '/F'],
                            capture_output=True, timeout=5,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                        )
        except Exception as e:
            logger.debug(f"Could not check for orphaned engine: {e}")

    def _find_run_exe(self) -> Optional[Path]:
        """Find run.exe in the install directory (cached)."""
        if self._run_exe_path and self._run_exe_path.exists():
            return self._run_exe_path

        if not self._install_dir.exists():
            return None

        # Check top-level first
        direct = self._install_dir / ENGINE_EXECUTABLE
        if direct.exists():
            self._run_exe_path = direct
            return direct

        # Search one level deep (7z may extract into a subfolder)
        for child in self._install_dir.iterdir():
            if child.is_dir():
                candidate = child / ENGINE_EXECUTABLE
                if candidate.exists():
                    self._run_exe_path = candidate
                    return candidate

        return None
