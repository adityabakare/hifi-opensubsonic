"""
Unit tests for the in-memory TTL cache module.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from app.cache import (
    cached_call, _make_key, clear_all_caches, cache_stats,
    _caches, _get_or_create,
    artist_cache, album_cache, track_cache, search_cache,
    lyrics_cache, similar_cache,
)


@pytest.fixture(autouse=True)
def _clean_caches():
    """Clear all caches before and after each test."""
    clear_all_caches()
    # Also remove the cache instances so TTLs from config don't leak between tests
    _caches.clear()
    yield
    clear_all_caches()
    _caches.clear()


# ---------------------------------------------------------------------------
# _make_key
# ---------------------------------------------------------------------------

def test_make_key_single_arg():
    assert _make_key("artist", 123) == "artist:123"


def test_make_key_multiple_args():
    assert _make_key("search_tracks", "hello world") == "search_tracks:hello world"


def test_make_key_empty():
    assert _make_key() == ""


# ---------------------------------------------------------------------------
# cached_call — cache hit / miss
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_miss_calls_fetch():
    """On a cache miss, the fetch function should be called."""
    fetch = AsyncMock(return_value={"data": "value"})
    result = await cached_call(artist_cache, "key1", fetch)
    assert result == {"data": "value"}
    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_cache_hit_does_not_call_fetch():
    """On a cache hit, the fetch function should NOT be called again."""
    call_count = 0

    async def fetch():
        nonlocal call_count
        call_count += 1
        return {"data": "value"}

    # First call — miss
    result1 = await cached_call(artist_cache, "key1", fetch)
    assert result1 == {"data": "value"}
    assert call_count == 1

    # Second call — hit
    result2 = await cached_call(artist_cache, "key1", fetch)
    assert result2 == {"data": "value"}
    assert call_count == 1  # fetch NOT called again


@pytest.mark.asyncio
async def test_different_keys_are_independent():
    """Different cache keys should store independent values."""
    async def fetch_a():
        return {"artist": "A"}

    async def fetch_b():
        return {"artist": "B"}

    result_a = await cached_call(artist_cache, "a", fetch_a)
    result_b = await cached_call(artist_cache, "b", fetch_b)

    assert result_a == {"artist": "A"}
    assert result_b == {"artist": "B"}


# ---------------------------------------------------------------------------
# Different cache instances are independent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_different_caches_are_independent():
    """artist_cache and album_cache should not share entries."""
    async def fetch_artist():
        return {"type": "artist"}

    async def fetch_album():
        return {"type": "album"}

    await cached_call(artist_cache, "id1", fetch_artist)
    await cached_call(album_cache, "id1", fetch_album)

    # Same key "id1" in different caches should have different values
    assert artist_cache()["id1"] == {"type": "artist"}
    assert album_cache()["id1"] == {"type": "album"}


# ---------------------------------------------------------------------------
# clear_all_caches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clear_all_caches():
    """clear_all_caches should empty every cache."""
    await cached_call(artist_cache, "k1", AsyncMock(return_value="v1"))
    await cached_call(album_cache, "k2", AsyncMock(return_value="v2"))

    assert len(artist_cache()) == 1
    assert len(album_cache()) == 1

    clear_all_caches()

    assert len(artist_cache()) == 0
    assert len(album_cache()) == 0


# ---------------------------------------------------------------------------
# cache_stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_stats():
    """cache_stats should report size and maxsize for active caches."""
    await cached_call(artist_cache, "k1", AsyncMock(return_value="v1"))
    await cached_call(artist_cache, "k2", AsyncMock(return_value="v2"))

    stats = cache_stats()
    assert "artist" in stats
    assert stats["artist"]["size"] == 2
    assert stats["artist"]["maxsize"] > 0


# ---------------------------------------------------------------------------
# TTL-based cache instances exist for all categories
# ---------------------------------------------------------------------------

def test_all_cache_factories_return_ttl_cache():
    """Verify that all cache factory functions return valid TTLCache instances."""
    for factory in [artist_cache, album_cache, track_cache, search_cache, lyrics_cache, similar_cache]:
        cache = factory()
        assert hasattr(cache, "maxsize")
        assert cache.maxsize > 0
