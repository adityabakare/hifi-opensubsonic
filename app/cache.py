"""
In-memory TTL cache for upstream API responses.

Uses cachetools.TTLCache — safe in single-process asyncio apps because
all coroutines share the same event loop and dict mutations do not interleave
within a single await expression.
"""
import logging
from typing import Any, Callable, Optional
from cachetools import TTLCache

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named cache instances
# ---------------------------------------------------------------------------

_caches: dict[str, TTLCache] = {}


def _get_or_create(name: str, maxsize: int, ttl: int) -> TTLCache:
    if name not in _caches:
        _caches[name] = TTLCache(maxsize=maxsize, ttl=ttl)
    return _caches[name]


# Lazy initialisers (called after settings are loaded)

def artist_cache() -> TTLCache:
    return _get_or_create("artist", maxsize=500, ttl=settings.CACHE_TTL_METADATA)

def album_cache() -> TTLCache:
    return _get_or_create("album", maxsize=500, ttl=settings.CACHE_TTL_METADATA)

def track_cache() -> TTLCache:
    return _get_or_create("track", maxsize=1000, ttl=settings.CACHE_TTL_METADATA // 2 or 1800)

def search_cache() -> TTLCache:
    return _get_or_create("search", maxsize=200, ttl=settings.CACHE_TTL_SEARCH)

def lyrics_cache() -> TTLCache:
    return _get_or_create("lyrics", maxsize=300, ttl=settings.CACHE_TTL_METADATA)

def similar_cache() -> TTLCache:
    return _get_or_create("similar", maxsize=300, ttl=settings.CACHE_TTL_METADATA)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_key(*args: Any) -> str:
    """Build a hashable cache key from positional arguments."""
    return ":".join(str(a) for a in args)


async def cached_call(
    cache_fn: Callable[[], TTLCache],
    key: str,
    fetch: Callable,
) -> Any:
    """
    Return a cached value if present, otherwise call *fetch* (an awaitable),
    store the result, and return it.
    """
    cache = cache_fn()
    if key in cache:
        return cache[key]

    result = await fetch()
    cache[key] = result
    return result


# ---------------------------------------------------------------------------
# Stats & management
# ---------------------------------------------------------------------------

def cache_stats() -> dict[str, dict[str, int]]:
    """Return current size / maxsize for every active cache."""
    return {
        name: {"size": len(c), "maxsize": c.maxsize}
        for name, c in _caches.items()
    }


def clear_all_caches() -> None:
    """Empty every cache. Useful for testing or admin endpoints."""
    for c in _caches.values():
        c.clear()
    logger.info("All caches cleared.")
