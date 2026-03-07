"""
RVC device configuration.

Detects available compute device: DirectML (AMD/Intel GPU) or CPU fallback.
DirectML requires the optional torch-directml package.

NOTE: We always start on CPU. DirectML is available via move_to_device() and
the UI toggle. RMVPE (pitch detection) always stays on CPU because it uses
ComplexFloat (FFT) which DirectML doesn't support.

All torch imports are deferred to avoid partial-init errors in PyInstaller exe.
"""

import logging
import sys

logger = logging.getLogger('stts.rvc.config')

# State — initialized lazily on first access
_device = None
_is_half = False
_initialized = False


def safe_import_torch():
    """Import torch safely, cleaning up sys.modules on failure.

    In PyInstaller exe, a failed torch import leaves a partially-initialized
    module in sys.modules. Subsequent imports then get the broken cached
    version instead of retrying. This function cleans up on failure so
    the next attempt gets a fresh import.

    Returns torch module or None.
    """
    # If torch is already successfully loaded, return it
    if 'torch' in sys.modules:
        t = sys.modules['torch']
        if hasattr(t, 'autograd'):
            return t
        # Partially initialized — clean up and retry
        _cleanup_torch_modules()

    # Set up DLL directories if running as frozen exe
    if getattr(sys, 'frozen', False):
        try:
            from standalone import setup_torch_dll_dirs
            setup_torch_dll_dirs()
        except ImportError:
            pass

    try:
        import torch
        # Verify it's fully initialized
        if not hasattr(torch, 'autograd'):
            raise ImportError("torch partially initialized (no autograd)")
        return torch
    except Exception as e:
        logger.warning(f"Failed to import torch: {e}")
        _cleanup_torch_modules()
        return None


def _cleanup_torch_modules():
    """Remove all torch-related modules from sys.modules."""
    to_remove = [k for k in sys.modules if k == 'torch' or k.startswith('torch.')]
    for k in to_remove:
        del sys.modules[k]


def _ensure_init():
    """Lazily initialize torch device config on first use."""
    global _device, _is_half, _initialized
    if _initialized:
        return

    torch = safe_import_torch()
    if torch is None:
        raise ImportError("torch is not available")

    _device = torch.device('cpu')
    _is_half = False

    # Check what's available
    try:
        import torch_directml
        logger.debug(f"RVC: DirectML available ({torch_directml.device_name(0)}), starting on CPU")
    except ImportError:
        logger.debug("RVC using CPU device (torch-directml not available)")

    if torch.cuda.is_available():
        logger.debug(f"RVC: CUDA available ({torch.cuda.get_device_name(0)})")

    # Limit torch threads for CPU inference to leave headroom for other STTS components
    torch.set_num_threads(4)
    logger.debug("RVC CPU inference: torch threads set to 4")
    _initialized = True


def get_device():
    """Return the configured compute device."""
    _ensure_init()
    return _device


def get_is_half():
    """Return whether half precision is enabled."""
    _ensure_init()
    return _is_half


def set_device(dev):
    """Set the compute device."""
    global _device, _is_half
    _ensure_init()
    import torch
    _device = torch.device(dev) if isinstance(dev, str) else dev
    _is_half = (dev == 'cuda')


def get_available_devices() -> list:
    """Return list of available compute device names.

    Uses safe_import_torch() to avoid poisoning sys.modules if torch
    is not installed or fails to load.
    """
    torch = safe_import_torch()
    if torch is None:
        return ['cpu']

    devices = ['cpu']
    if torch.cuda.is_available():
        devices.append('cuda')
    try:
        import torch_directml
        devices.append('directml')
    except ImportError:
        pass
    return devices
