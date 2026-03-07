"""
Global cache manager for STTS.
Caches data to disk (JSON) to avoid repeated API calls and computations.
Supports TTL (time-to-live) for automatic expiration.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger('stts.utils.cache')

# Default cache directory: next to the python source
_CACHE_DIR = Path(os.environ.get('STTS_CACHE_DIR', ''))


def _get_cache_dir() -> Path:
    """Get or create the cache directory."""
    global _CACHE_DIR
    if not _CACHE_DIR or not str(_CACHE_DIR):
        # Default: %APPDATA%\STTS\cache (consistent with other STTS data)
        appdata = Path(os.environ.get('APPDATA', Path.home() / '.stts'))
        _CACHE_DIR = appdata / 'STTS' / 'cache'
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def set_cache_dir(path: str):
    """Override the cache directory."""
    global _CACHE_DIR
    _CACHE_DIR = Path(path)
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cache(key: str, ttl_seconds: Optional[int] = None) -> Optional[Any]:
    """Get a cached value by key.

    Args:
        key: Cache key (used as filename)
        ttl_seconds: Max age in seconds. None = no expiration.

    Returns:
        Cached data, or None if not found / expired.
    """
    cache_dir = _get_cache_dir()
    cache_file = cache_dir / f"{key}.json"

    if not cache_file.exists():
        return None

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            entry = json.load(f)

        # Check TTL
        if ttl_seconds is not None:
            stored_at = entry.get('_timestamp', 0)
            if time.time() - stored_at > ttl_seconds:
                logger.debug(f"Cache expired for key '{key}'")
                return None

        return entry.get('data')

    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Cache read error for key '{key}': {e}")
        return None


def set_cache(key: str, data: Any):
    """Store data in the cache.

    Args:
        key: Cache key (used as filename)
        data: JSON-serializable data to cache
    """
    cache_dir = _get_cache_dir()
    cache_file = cache_dir / f"{key}.json"

    try:
        entry = {
            '_timestamp': time.time(),
            'data': data,
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(entry, f, ensure_ascii=False)
        logger.debug(f"Cached data for key '{key}' ({cache_file.stat().st_size} bytes)")

    except (OSError, TypeError) as e:
        logger.warning(f"Cache write error for key '{key}': {e}")


def delete_cache(key: str):
    """Delete a specific cache entry."""
    cache_dir = _get_cache_dir()
    cache_file = cache_dir / f"{key}.json"
    if cache_file.exists():
        cache_file.unlink()
        logger.debug(f"Deleted cache for key '{key}'")


def clear_all_cache() -> Dict[str, Any]:
    """Clear all cached data.

    Returns:
        Dict with 'files_deleted' count and 'bytes_freed'.
    """
    cache_dir = _get_cache_dir()
    files_deleted = 0
    bytes_freed = 0

    if cache_dir.exists():
        for cache_file in cache_dir.glob('*.json'):
            try:
                bytes_freed += cache_file.stat().st_size
                cache_file.unlink()
                files_deleted += 1
            except OSError as e:
                logger.warning(f"Failed to delete cache file {cache_file}: {e}")

    logger.debug(f"Cleared cache: {files_deleted} files, {bytes_freed} bytes freed")
    return {
        'files_deleted': files_deleted,
        'bytes_freed': bytes_freed,
    }


def get_cache_info() -> Dict[str, Any]:
    """Get cache statistics.

    Returns:
        Dict with 'total_files', 'total_bytes', 'cache_dir', 'entries'.
    """
    cache_dir = _get_cache_dir()
    entries = []
    total_bytes = 0

    if cache_dir.exists():
        for cache_file in cache_dir.glob('*.json'):
            try:
                stat = cache_file.stat()
                total_bytes += stat.st_size
                entries.append({
                    'key': cache_file.stem,
                    'size': stat.st_size,
                    'modified': stat.st_mtime,
                })
            except OSError:
                pass

    return {
        'total_files': len(entries),
        'total_bytes': total_bytes,
        'cache_dir': str(cache_dir),
        'entries': entries,
    }
