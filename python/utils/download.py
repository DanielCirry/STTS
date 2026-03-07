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
        last_report_time = [0.0]

        try:
            # Try to patch huggingface_hub's file download progress
            import huggingface_hub.file_download as hf_download

            if hasattr(hf_download, 'tqdm'):
                original_tqdm = hf_download.tqdm

            class ProgressTqdm:
                """Wrapper that reports progress to our callback."""
                def __init__(self, *args, **kwargs):
                    self.total = kwargs.get('total', 0) or 0
                    self.n = 0
                    self.desc = kwargs.get('desc', '')
                    # Don't actually create a tqdm bar (we're headless)

                def update(self, n=1):
                    self.n += n
                    now = time.time()
                    # Throttle progress reports to max 2x/second
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

                # Make it iterable (some code wraps iterables with tqdm)
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

            # Apply patch
            hf_download.tqdm = lambda *a, **kw: ProgressTqdm(*a, **kw)

            yield

        except ImportError:
            logger.debug("huggingface_hub not available for progress patching")
            yield
        finally:
            # Restore original
            if original_tqdm is not None:
                try:
                    import huggingface_hub.file_download as hf_download
                    hf_download.tqdm = original_tqdm
                except Exception:
                    pass

    return progress_context()
