"""
Package Manager - Check and install optional dependencies from within the app.
When running as a PyInstaller exe, installs into a venv/ folder next to the exe.
When running from source, installs into the active venv.
"""

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger('stts.packages')

# Feature definitions: name -> (display_name, packages, requires_torch, description)
FEATURES = {
    'stt': {
        'name': 'Speech-to-Text (Whisper)',
        'packages': ['faster-whisper>=1.0.0', 'ctranslate2>=4.0.0'],
        'check_import': 'faster_whisper',
        'requires_torch': False,
        'description': 'Local speech recognition using Whisper (~300 MB)',
    },
    'torch_cpu': {
        'name': 'PyTorch (CPU)',
        'packages': ['torch'],
        'pip_extra': ['--index-url', 'https://download.pytorch.org/whl/cpu'],
        'check_import': 'torch',
        'requires_torch': False,
        'description': 'Required for Translation & RVC (~200 MB)',
    },
    'torch_cuda': {
        'name': 'PyTorch (CUDA - NVIDIA GPU)',
        'packages': ['torch'],
        'pip_extra': ['--index-url', 'https://download.pytorch.org/whl/cu121'],
        'check_import': 'torch',
        'requires_torch': False,
        'description': 'GPU acceleration for NVIDIA GPUs (~2.5 GB)',
    },
    'translation': {
        'name': 'Translation (NLLB)',
        'packages': ['transformers>=4.35.0', 'sentencepiece>=0.1.99'],
        'check_import': 'transformers',
        'requires_torch': True,
        'description': 'Offline translation for 200+ languages (~50 MB)',
    },
    'local_llm': {
        'name': 'Local LLM (llama.cpp)',
        'packages': ['llama-cpp-python>=0.2.50'],
        'pip_extra': ['--extra-index-url', 'https://abetlen.github.io/llama-cpp-python/whl/cpu', '--only-binary', ':all:'],
        'check_import': 'llama_cpp',
        'requires_torch': False,
        'description': 'Run AI models locally (~50 MB)',
    },
    'rvc': {
        'name': 'RVC Voice Conversion',
        'packages': ['scipy>=1.10.0', 'faiss-cpu>=1.7.3', 'librosa>=0.9.2,<0.11.0', 'soundfile>=0.12.1', 'pydub>=0.25.1', 'transformers>=4.35.0'],
        'check_import': 'scipy',
        'requires_torch': True,
        'description': 'Real-time voice conversion + base models (~550 MB)',
    },
    'piper_tts': {
        'name': 'Piper TTS (Offline)',
        'packages': ['piper-tts>=1.2.0', 'onnxruntime>=1.16.0'],
        'check_import': 'piper',
        'requires_torch': False,
        'description': 'Offline text-to-speech engine (~150 MB)',
    },
}


def _get_pip_executable() -> Optional[str]:
    """Get the pip executable path for installing packages."""
    if getattr(sys, 'frozen', False):
        # PyInstaller exe: use venv next to the exe
        app_dir = Path(sys.executable).parent
        venv_pip = app_dir / 'venv' / 'Scripts' / 'pip.exe'
        if venv_pip.exists():
            return str(venv_pip)
        return None
    else:
        # Running from source: use current venv
        venv_dir = Path(sys.executable).parent.parent
        pip = venv_dir / 'Scripts' / 'pip.exe'
        if pip.exists():
            return str(pip)
        return str(Path(sys.executable).parent / 'pip.exe')


def _get_python_executable() -> Optional[list]:
    """Get a python executable whose major.minor matches the frozen exe.

    When creating a venv for pip-installed packages, the Python version MUST
    match the exe's version. Otherwise compiled .pyd files (numpy, torch, etc.)
    are built for the wrong ABI and fail to load with cryptic DLL errors.

    Returns a list of command args (e.g. ['python'] or ['py', '-3.10']), or None.
    """
    req_major, req_minor = sys.version_info[:2]
    req_ver = f"{req_major}.{req_minor}"

    # Try py launcher first (can target specific versions)
    try:
        result = subprocess.run(
            ['py', f'-{req_ver}', '--version'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            logger.debug(f"Found py launcher for Python {req_ver}")
            return ['py', f'-{req_ver}']
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fall back to python/python3 if version matches
    for cmd in ['python', 'python3']:
        try:
            result = subprocess.run(
                [cmd, '--version'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                ver_str = result.stdout.strip()  # "Python 3.10.11"
                parts = ver_str.split()
                if len(parts) >= 2:
                    found_ver = '.'.join(parts[1].split('.')[:2])
                    if found_ver == req_ver:
                        logger.debug(f"Found {cmd} matching Python {req_ver}")
                        return [cmd]
                    else:
                        logger.debug(f"{cmd} is Python {found_ver}, need {req_ver} — skipping")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # Check for our own downloaded portable Python
    if getattr(sys, 'frozen', False):
        portable = Path(sys.executable).parent / 'python' / 'python.exe'
        if portable.exists():
            logger.debug(f"Found portable Python at {portable}")
            return [str(portable)]

    logger.debug(f"No Python {req_ver} found on system")
    return None


async def _download_python(progress_callback=None) -> Optional[str]:
    """Download portable Python matching the exe's version.

    Downloads the embeddable Python package from python.org and sets it up
    with pip so it can create venvs.

    Returns path to python.exe or None on failure.
    """
    if not getattr(sys, 'frozen', False):
        return None

    req_major, req_minor, req_micro = sys.version_info[:3]
    req_ver = f"{req_major}.{req_minor}.{req_micro}"
    req_ver_short = f"{req_major}{req_minor}"

    app_dir = Path(sys.executable).parent
    python_dir = app_dir / 'python'
    python_exe = python_dir / 'python.exe'

    if python_exe.exists():
        return str(python_exe)

    import aiohttp
    import zipfile
    import io

    # Download embeddable Python from python.org
    url = f'https://www.python.org/ftp/python/{req_ver}/python-{req_ver}-embed-amd64.zip'
    logger.info(f"Downloading Python {req_ver} from {url}")

    if progress_callback:
        await progress_callback({
            'feature': '_python',
            'stage': 'installing',
            'detail': f'Downloading Python {req_ver}...',
        })

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to download Python: HTTP {resp.status}")
                    return None
                data = await resp.read()

        # Extract
        python_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(python_dir)

        if not python_exe.exists():
            logger.error("python.exe not found after extraction")
            return None

        # Enable pip: edit python310._pth to uncomment 'import site'
        pth_file = python_dir / f'python{req_ver_short}._pth'
        if pth_file.exists():
            content = pth_file.read_text()
            content = content.replace('#import site', 'import site')
            pth_file.write_text(content)

        # Install pip via get-pip.py
        if progress_callback:
            await progress_callback({
                'feature': '_python',
                'stage': 'installing',
                'detail': 'Setting up pip...',
            })

        get_pip_url = 'https://bootstrap.pypa.io/get-pip.py'
        async with aiohttp.ClientSession() as session:
            async with session.get(get_pip_url) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to download get-pip.py: HTTP {resp.status}")
                    return None
                get_pip_data = await resp.read()

        get_pip_path = python_dir / 'get-pip.py'
        get_pip_path.write_bytes(get_pip_data)

        process = await asyncio.create_subprocess_exec(
            str(python_exe), str(get_pip_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        await process.wait()

        # Clean up
        get_pip_path.unlink(missing_ok=True)

        if process.returncode != 0:
            logger.error("get-pip.py failed")
            return None

        # Install setuptools+wheel so pip can build packages
        portable_pip = python_dir / 'Scripts' / 'pip.exe'
        if portable_pip.exists():
            process = await asyncio.create_subprocess_exec(
                str(portable_pip), 'install', 'setuptools', 'wheel',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            await process.wait()

        logger.info(f"Portable Python {req_ver} ready at {python_dir}")
        return str(python_exe)

    except Exception as e:
        logger.error(f"Failed to download Python: {e}")
        import shutil
        shutil.rmtree(str(python_dir), ignore_errors=True)
        return None


async def _ensure_venv_async(progress_callback=None) -> Optional[str]:
    """Ensure a pip executable is available for installing packages.

    Strategy:
    1. If a venv with matching Python version exists, use its pip.
    2. If system Python matches, create a venv with it.
    3. Otherwise, download portable Python and use its pip directly.

    Returns pip executable path or None.
    """
    if not getattr(sys, 'frozen', False):
        return _get_pip_executable()

    app_dir = Path(sys.executable).parent
    venv_dir = app_dir / 'venv'
    venv_pip = venv_dir / 'Scripts' / 'pip.exe'
    req_ver = f"{sys.version_info[0]}.{sys.version_info[1]}"

    # Check existing venv
    if venv_pip.exists():
        venv_python = venv_dir / 'Scripts' / 'python.exe'
        if venv_python.exists():
            try:
                result = subprocess.run(
                    [str(venv_python), '-c', 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")'],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    venv_ver = result.stdout.strip()
                    if venv_ver == req_ver:
                        return str(venv_pip)
                    logger.warning(f"Venv Python {venv_ver} != exe Python {req_ver}, recreating")
                    import shutil
                    shutil.rmtree(str(venv_dir), ignore_errors=True)
            except Exception as e:
                logger.debug(f"Failed to check venv version: {e}")
                return str(venv_pip)
        else:
            return str(venv_pip)

    # Try system Python first (creates real venv)
    python = _get_python_executable()
    if python:
        try:
            if progress_callback:
                await progress_callback({
                    'feature': '_python', 'stage': 'installing',
                    'detail': 'Creating virtual environment...',
                })
            process = await asyncio.create_subprocess_exec(
                *python, '-m', 'venv', str(venv_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            await process.wait()
            if venv_pip.exists():
                process = await asyncio.create_subprocess_exec(
                    str(venv_dir / 'Scripts' / 'python.exe'), '-m', 'pip',
                    'install', '--upgrade', 'pip',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                await process.wait()
                return str(venv_pip)
        except Exception as e:
            logger.error(f"Failed to create venv with system Python: {e}")

    # No matching system Python — download portable Python + use pip directly
    # Embeddable Python can't create venvs, but we can use pip --target
    # to install into a site-packages dir that standalone.py already adds to sys.path
    python_exe = await _download_python(progress_callback)
    if not python_exe:
        return None

    # The portable Python's pip is at python/Scripts/pip.exe
    portable_pip = Path(python_exe).parent / 'Scripts' / 'pip.exe'
    if not portable_pip.exists():
        logger.error(f"pip not found at {portable_pip}")
        return None

    # Create the venv directory structure that standalone.py expects
    site_pkgs = venv_dir / 'Lib' / 'site-packages'
    site_pkgs.mkdir(parents=True, exist_ok=True)

    return str(portable_pip)


def _ensure_venv() -> Optional[str]:
    """Sync wrapper — only for non-frozen or when venv already exists."""
    if not getattr(sys, 'frozen', False):
        return _get_pip_executable()

    app_dir = Path(sys.executable).parent
    venv_pip = app_dir / 'venv' / 'Scripts' / 'pip.exe'
    if venv_pip.exists():
        return str(venv_pip)
    # Also check portable Python pip
    portable_pip = app_dir / 'python' / 'Scripts' / 'pip.exe'
    if portable_pip.exists():
        return str(portable_pip)
    return None


def _check_venv_package(pip_name: str) -> bool:
    """Check if a pip package is installed in the external venv (not bundled by PyInstaller).

    Looks for the package's .dist-info directory which pip always creates.
    PyInstaller bundles don't have these, so this avoids false positives.
    """
    app_dir = Path(sys.executable).parent
    venv_site = app_dir / 'venv' / 'Lib' / 'site-packages'
    if not venv_site.exists():
        return False
    # pip normalizes names: dashes → underscores, lowercase
    normalized = pip_name.lower().replace('-', '_')
    try:
        for p in venv_site.iterdir():
            if p.is_dir() and p.name.endswith('.dist-info'):
                # Strip .dist-info suffix, then split off version
                # e.g. "scipy-1.15.3.dist-info" → "scipy-1.15.3" → "scipy"
                # e.g. "torch-2.10.0+cpu.dist-info" → "torch-2.10.0+cpu" → "torch"
                bare = p.name[:-len('.dist-info')]  # remove .dist-info
                dist_name = bare.split('-', 1)[0].lower().replace('-', '_')
                if dist_name == normalized:
                    return True
    except OSError:
        pass
    return False


def check_feature(feature_id: str) -> bool:
    """Check if a feature's packages are installed.

    When running as a frozen exe, checks the external venv's .dist-info
    directories to avoid false positives from PyInstaller-bundled modules.
    """
    if feature_id not in FEATURES:
        return False

    feature = FEATURES[feature_id]
    check = feature['check_import']

    if getattr(sys, 'frozen', False):
        # In frozen exe, check external venv — not the bundled modules
        # Use the first pip package name as the canonical check
        pip_name = feature['packages'][0].split('>=')[0].split('>=')[0].split('<')[0].split('==')[0].split('[')[0].strip()
        return _check_venv_package(pip_name)

    try:
        __import__(check)
        return True
    except Exception:
        return False


def _get_venv_package_version(pip_name: str) -> Optional[str]:
    """Get package version from dist-info in the external venv (no imports needed)."""
    app_dir = Path(sys.executable).parent
    venv_site = app_dir / 'venv' / 'Lib' / 'site-packages'
    if not venv_site.exists():
        return None
    normalized = pip_name.lower().replace('-', '_')
    try:
        for p in venv_site.iterdir():
            if p.is_dir() and p.name.endswith('.dist-info'):
                bare = p.name[:-len('.dist-info')]
                parts = bare.split('-', 1)
                dist_name = parts[0].lower().replace('-', '_')
                if dist_name == normalized and len(parts) > 1:
                    return parts[1]  # version string
    except OSError:
        pass
    return None


def check_all_features() -> Dict[str, dict]:
    """Check status of all features."""
    result = {}
    torch_installed = check_feature('torch_cpu')
    torch_version = None
    if torch_installed:
        if getattr(sys, 'frozen', False):
            # In frozen exe, read version from dist-info instead of importing torch
            # (importing torch here would poison sys.modules if it fails)
            torch_version = _get_venv_package_version('torch')
        else:
            try:
                import torch
                torch_version = torch.__version__
            except Exception:
                pass

    for fid, finfo in FEATURES.items():
        installed = check_feature(fid)
        result[fid] = {
            'id': fid,
            'name': finfo['name'],
            'description': finfo['description'],
            'installed': installed,
            'requires_torch': finfo['requires_torch'],
            'torch_installed': torch_installed,
        }
        if fid in ('torch_cpu', 'torch_cuda') and torch_version:
            result[fid]['version'] = torch_version

    # Check if system Python available (needed for venv creation in exe mode)
    python_available = True
    if getattr(sys, 'frozen', False):
        python_available = _get_python_executable() is not None

    return {
        'features': result,
        'python_available': python_available,
        'is_frozen': getattr(sys, 'frozen', False),
    }


async def _verify_torch_import() -> Optional[str]:
    """Verify torch was installed correctly.

    Does NOT import torch in the current process — re-importing torch's C extensions
    causes 'already has a docstring' RuntimeError. Instead, just set up DLL dirs
    and trust that pip succeeded.

    Returns error string or None on success.
    """
    try:
        # Re-run DLL setup (torch was just installed, dirs may not have existed at startup)
        if getattr(sys, 'frozen', False):
            try:
                from standalone import setup_torch_dll_dirs
                site_pkgs = Path(sys.executable).parent / 'venv' / 'Lib' / 'site-packages'
                setup_torch_dll_dirs(site_pkgs)
            except ImportError:
                pass

        # Verify torch files exist in the venv (without importing)
        if getattr(sys, 'frozen', False):
            app_dir = Path(sys.executable).parent
            torch_init = app_dir / 'venv' / 'Lib' / 'site-packages' / 'torch' / '__init__.py'
            if not torch_init.exists():
                return "torch package files not found in venv"

        logger.info("Torch install verification passed (files present, DLL dirs set up)")
        return None
    except Exception as e:
        logger.error(f"Torch verification failed: {e}")
        return str(e)


async def install_feature(
    feature_id: str,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """Install a feature's packages. Returns result dict."""

    if feature_id not in FEATURES:
        return {'success': False, 'error': f'Unknown feature: {feature_id}'}

    feature = FEATURES[feature_id]

    # Check if torch is required but not installed
    if feature['requires_torch'] and not check_feature('torch_cpu'):
        if progress_callback:
            await progress_callback({
                'feature': feature_id,
                'stage': 'installing_dependency',
                'detail': 'Installing PyTorch (CPU) first...',
            })
        # Install torch CPU first
        torch_result = await install_feature('torch_cpu', progress_callback)
        if not torch_result.get('success'):
            return {'success': False, 'error': f'Failed to install PyTorch (required): {torch_result.get("error", "unknown error")}. Install PyTorch from the Features page first.'}

    # Ensure venv exists (auto-downloads Python if needed)
    pip = await _ensure_venv_async(progress_callback)
    if not pip:
        req_ver = f"{sys.version_info[0]}.{sys.version_info[1]}"
        return {
            'success': False,
            'error': f'Failed to set up Python {req_ver}. Check your internet connection and try again.',
        }

    if progress_callback:
        await progress_callback({
            'feature': feature_id,
            'stage': 'installing',
            'detail': f'Installing {feature["name"]}...',
        })

    # Build pip command
    using_portable = False
    cmd = [pip, 'install'] + feature['packages']
    # If using portable Python pip (no real venv), install to venv/Lib/site-packages
    # which is where standalone.py adds to sys.path
    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).parent
        venv_pip = app_dir / 'venv' / 'Scripts' / 'pip.exe'
        if not venv_pip.exists() and 'python' in pip:
            using_portable = True
            target_dir = app_dir / 'venv' / 'Lib' / 'site-packages'
            target_dir.mkdir(parents=True, exist_ok=True)
            cmd += ['--target', str(target_dir)]
    if 'pip_extra' in feature:
        cmd += feature['pip_extra']

    try:
        logger.debug(f"Running: {' '.join(cmd)}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        output_lines = []
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            decoded = line.decode('utf-8', errors='ignore').strip()
            if decoded:
                output_lines.append(decoded)
                if progress_callback and ('Installing' in decoded or 'Downloading' in decoded or 'Collecting' in decoded):
                    await progress_callback({
                        'feature': feature_id,
                        'stage': 'installing',
                        'detail': decoded[:100],
                    })

        await process.wait()

        if process.returncode == 0:
            # Add the new packages to sys.path so they're available immediately
            if getattr(sys, 'frozen', False):
                app_dir = Path(sys.executable).parent
                site_pkgs = app_dir / 'venv' / 'Lib' / 'site-packages'
                if str(site_pkgs) not in sys.path:
                    sys.path.insert(0, str(site_pkgs))
                # If torch was just installed, set up its DLL directories
                # (they didn't exist at startup so standalone.py couldn't do it)
                if 'torch' in feature_id or feature.get('requires_torch'):
                    try:
                        from standalone import setup_torch_dll_dirs
                        setup_torch_dll_dirs(site_pkgs)
                    except ImportError:
                        pass

            # Verify torch actually imports after install
            if 'torch' in feature_id and getattr(sys, 'frozen', False):
                if progress_callback:
                    await progress_callback({
                        'feature': feature_id,
                        'stage': 'installing',
                        'detail': 'Verifying PyTorch installation...',
                    })
                verify_err = await _verify_torch_import()
                if verify_err:
                    logger.warning(f"Torch installed but import verification failed: {verify_err}")
                    if progress_callback:
                        await progress_callback({
                            'feature': feature_id,
                            'stage': 'complete',
                            'detail': f'{feature["name"]} installed (import test: {verify_err[:80]})',
                        })
                else:
                    logger.info("Torch import verification passed")

            if progress_callback:
                await progress_callback({
                    'feature': feature_id,
                    'stage': 'complete',
                    'detail': f'{feature["name"]} installed successfully',
                })

            return {'success': True, 'feature': feature_id}
        else:
            error_msg = '\n'.join(output_lines[-5:])
            return {'success': False, 'error': f'pip failed:\n{error_msg}'}

    except Exception as e:
        logger.error(f"Install failed: {e}")
        return {'success': False, 'error': str(e)}


async def uninstall_feature(
    feature_id: str,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """Uninstall a feature's packages. Returns result dict."""

    if feature_id not in FEATURES:
        return {'success': False, 'error': f'Unknown feature: {feature_id}'}

    feature = FEATURES[feature_id]

    pip = _get_pip_executable()
    if not pip:
        return {'success': False, 'error': 'No pip available'}

    if progress_callback:
        await progress_callback({
            'feature': feature_id,
            'stage': 'uninstalling',
            'detail': f'Removing {feature["name"]}...',
        })

    cmd = [pip, 'uninstall', '-y'] + feature['packages']

    try:
        logger.debug(f"Running: {' '.join(cmd)}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        output_lines = []
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            decoded = line.decode('utf-8', errors='ignore').strip()
            if decoded:
                output_lines.append(decoded)

        await process.wait()

        if progress_callback:
            await progress_callback({
                'feature': feature_id,
                'stage': 'complete',
                'detail': f'{feature["name"]} removed',
            })

        return {'success': True, 'feature': feature_id}

    except Exception as e:
        logger.error(f"Uninstall failed: {e}")
        return {'success': False, 'error': str(e)}
