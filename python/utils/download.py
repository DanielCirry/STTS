"""
Download utilities with progress tracking.
Hooks into HuggingFace Hub to report download progress via callbacks.
"""

import logging
import os
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger('stts.download')


class DownloadProgressTracker:
    """Track download progress for HuggingFace model downloads.

    Uses the huggingface_hub snapshot_download with a progress callback
    to report download progress to the frontend.
    """

    def __init__(self, on_progress: Optional[Callable[[str, float], None]] = None):
        """
        Args:
            on_progress: Callback(model_id, progress_percent) called during downloads.
                         progress_percent is 0.0 to 100.0
        """
        self.on_progress = on_progress
        self._cancel_requested = False

    def cancel(self):
        """Request cancellation of the current download."""
        self._cancel_requested = True

    def _report_progress(self, model_id: str, progress: float):
        """Report progress via callback."""
        if self.on_progress:
            self.on_progress(model_id, min(100.0, max(0.0, progress)))

    def check_model_cached(self, model_name: str) -> bool:
        """Check if a HuggingFace model is already cached locally.

        Args:
            model_name: HuggingFace model name (e.g., 'facebook/nllb-200-distilled-600M')

        Returns:
            True if model files exist in cache
        """
        try:
            from huggingface_hub import try_to_load_from_cache
            # Check if the config file is cached as a proxy for the full model
            result = try_to_load_from_cache(model_name, 'config.json')
            return result is not None
        except Exception:
            pass

        # Fallback: check the HF cache directory
        try:
            cache_dir = os.environ.get(
                'HF_HOME',
                os.path.join(os.path.expanduser('~'), '.cache', 'huggingface', 'hub')
            )
            # HF stores models as models--org--name
            safe_name = model_name.replace('/', '--')
            model_dir = os.path.join(cache_dir, f'models--{safe_name}')
            if os.path.isdir(model_dir):
                # Check if there are snapshot directories
                snapshots_dir = os.path.join(model_dir, 'snapshots')
                if os.path.isdir(snapshots_dir) and os.listdir(snapshots_dir):
                    return True
        except Exception:
            pass

        return False

    def get_disk_space(self, path: Optional[str] = None) -> dict:
        """Get available disk space.

        Args:
            path: Path to check. Defaults to home directory.

        Returns:
            Dict with 'free_gb' and 'total_gb'
        """
        import shutil
        check_path = path or os.path.expanduser('~')
        try:
            usage = shutil.disk_usage(check_path)
            return {
                'free_gb': round(usage.free / (1024 ** 3), 2),
                'total_gb': round(usage.total / (1024 ** 3), 2),
            }
        except Exception:
            return {'free_gb': 0, 'total_gb': 0}


def patch_transformers_download_progress(model_id: str, on_progress: Callable[[str, float], None]):
    """Create a context that monkey-patches HuggingFace's download to track progress.

    This patches the tqdm progress bars that transformers/huggingface_hub uses
    to report download progress.

    Args:
        model_id: Model identifier for the callback
        on_progress: Callback(model_id, progress_percent)

    Returns:
        Context manager to use around model loading
    """
    import contextlib

    @contextlib.contextmanager
    def progress_context():
        """Monkey-patch huggingface_hub's tqdm to capture progress."""
        original_tqdm = None
        original_tqdm_auto = None
        original_tqdm_std = None
        last_report_time = [0.0]
        _progress_lock = threading.Lock()

        class ProgressTqdm:
            """Wrapper that reports progress to our callback.

            Must implement enough of the tqdm API that libraries like
            faster-whisper, transformers, and huggingface_hub don't crash.
            """
            _lock = _progress_lock  # Class-level _lock attribute (tqdm compat)
            monitor_interval = 0
            monitor = None

            def __init__(self, *args, **kwargs):
                self.total = kwargs.get('total', 0) or 0
                self.n = 0
                self.desc = kwargs.get('desc', '')
                self.disable = kwargs.get('disable', False)
                self.unit = kwargs.get('unit', 'it')
                self.lock = _progress_lock
                self.pos = 0
                self.miniters = 1
                self.last_print_t = 0
                self.sp = None

            def update(self, n=1):
                self.n += n
                now = time.time()
                if now - last_report_time[0] >= 0.5 and self.total > 0:
                    pct = (self.n / self.total) * 100
                    on_progress(model_id, pct)
                    last_report_time[0] = now

            def close(self):
                if self.total > 0:
                    on_progress(model_id, 100.0)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

            def __iter__(self):
                return self

            def __next__(self):
                raise StopIteration

            def set_description(self, desc=None, refresh=True):
                if desc:
                    self.desc = desc

            def set_postfix(self, *args, **kwargs):
                pass

            def refresh(self):
                pass

            def reset(self, total=None):
                self.n = 0
                if total is not None:
                    self.total = total

            def clear(self):
                pass

            def display(self, *args, **kwargs):
                pass

            @classmethod
            def get_lock(cls):
                return _progress_lock

            @classmethod
            def set_lock(cls, lock):
                cls._lock = lock
                nonlocal _progress_lock
                _progress_lock = lock

            @classmethod
            def external_write_mode(cls, *args, **kwargs):
                return contextlib.nullcontext()

            @classmethod
            def pandas(cls, *args, **kwargs):
                return cls(*args, **kwargs)

            def unpause(self):
                pass

            def moveto(self, n=0):
                pass

            @property
            def format_dict(self):
                return {'n': self.n, 'total': self.total, 'elapsed': 0, 'rate': None}

        try:
            # Try to patch huggingface_hub's file download progress
            import huggingface_hub.file_download as hf_download

            if hasattr(hf_download, 'tqdm'):
                original_tqdm = hf_download.tqdm

            # Apply patch to huggingface_hub's file_download
            hf_download.tqdm = lambda *a, **kw: ProgressTqdm(*a, **kw)

            # Also patch tqdm.auto which newer huggingface_hub versions may use directly
            try:
                import tqdm.auto as tqdm_auto
                original_tqdm_auto = tqdm_auto.tqdm
                tqdm_auto.tqdm = ProgressTqdm
            except (ImportError, AttributeError):
                pass

            # Also patch tqdm.std for broader coverage (faster-whisper uses this)
            try:
                import tqdm.std as tqdm_std
                original_tqdm_std = tqdm_std.tqdm
                tqdm_std.tqdm = ProgressTqdm
            except (ImportError, AttributeError):
                pass

            yield

        except ImportError:
            logger.debug("huggingface_hub not available for progress patching")
            yield
        finally:
            # Restore originals
            if original_tqdm is not None:
                try:
                    import huggingface_hub.file_download as hf_download
                    hf_download.tqdm = original_tqdm
                except Exception:
                    pass
            if original_tqdm_auto is not None:
                try:
                    import tqdm.auto as tqdm_auto
                    tqdm_auto.tqdm = original_tqdm_auto
                except Exception:
                    pass
            if original_tqdm_std is not None:
                try:
                    import tqdm.std as tqdm_std
                    tqdm_std.tqdm = original_tqdm_std
                except Exception:
                    pass

    return progress_context()
