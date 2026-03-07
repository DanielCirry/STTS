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
        'check_import': 'llama_cpp',
        'requires_torch': False,
        'description': 'Run AI models locally (~50 MB)',
    },
    'rvc': {
        'name': 'RVC Voice Conversion',
        'packages': ['scipy>=1.10.0', 'faiss-cpu>=1.7.3', 'librosa>=0.9.2,<0.11.0', 'soundfile>=0.12.1', 'pydub>=0.25.1', 'transformers>=4.35.0'],
        'check_import': 'scipy',
        'requires_torch': True,
        'description': 'Real-time voice conversion (~150 MB)',
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


def _get_python_executable() -> Optional[str]:
    """Get the python executable for creating venv."""
    # Try system Python first
    for cmd in ['python', 'python3']:
        try:
            result = subprocess.run(
                [cmd, '--version'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def _ensure_venv() -> Optional[str]:
    """Ensure a venv exists next to the exe. Returns pip path or None."""
    if not getattr(sys, 'frozen', False):
        # Running from source, venv already exists
        return _get_pip_executable()

    app_dir = Path(sys.executable).parent
    venv_dir = app_dir / 'venv'
    venv_pip = venv_dir / 'Scripts' / 'pip.exe'

    if venv_pip.exists():
        return str(venv_pip)

    # Need to create venv - requires system Python
    python = _get_python_executable()
    if not python:
        return None

    try:
        logger.info(f"Creating venv at {venv_dir}")
        subprocess.run(
            [python, '-m', 'venv', str(venv_dir)],
            capture_output=True, text=True, timeout=120
        )
        # Upgrade pip
        if venv_pip.exists():
            subprocess.run(
                [str(venv_dir / 'Scripts' / 'python.exe'), '-m', 'pip', 'install', '--upgrade', 'pip'],
                capture_output=True, text=True, timeout=120
            )
        return str(venv_pip) if venv_pip.exists() else None
    except Exception as e:
        logger.error(f"Failed to create venv: {e}")
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
            return {'success': False, 'error': 'Failed to install required PyTorch dependency'}

    # Ensure venv exists
    pip = _ensure_venv()
    if not pip:
        return {
            'success': False,
            'error': 'Python is not installed. Please install Python 3.10+ from python.org and add it to PATH.',
        }

    if progress_callback:
        await progress_callback({
            'feature': feature_id,
            'stage': 'installing',
            'detail': f'Installing {feature["name"]}...',
        })

    # Build pip command
    cmd = [pip, 'install'] + feature['packages']
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
