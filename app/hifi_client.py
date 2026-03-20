import httpx
import copy
import time
from typing import Optional, Dict, Any
import asyncio
import random
import logging
from app.config import settings
from app.cache import (
    artist_cache, album_cache, track_cache,
    search_cache, lyrics_cache, similar_cache,
    cached_call, _make_key,
)

logger = logging.getLogger(__name__)


class _CircuitState:
    """Per-instance circuit breaker state."""
    __slots__ = ("failures", "open_until")

    def __init__(self):
        self.failures: int = 0
        self.open_until: float = 0.0  # monotonic timestamp

    @property
    def is_open(self) -> bool:
        return (
            self.failures >= settings.CIRCUIT_BREAKER_THRESHOLD
            and time.monotonic() < self.open_until
        )

    @property
    def is_half_open(self) -> bool:
        """Recovery window expired — allow a single probe request."""
        return (
            self.failures >= settings.CIRCUIT_BREAKER_THRESHOLD
            and time.monotonic() >= self.open_until
        )

    def record_failure(self):
        self.failures += 1
        if self.failures >= settings.CIRCUIT_BREAKER_THRESHOLD:
            self.open_until = time.monotonic() + settings.CIRCUIT_BREAKER_RECOVERY
            logger.warning(
                "Circuit OPEN for instance (failures=%d, recovery in %ds)",
                self.failures,
                settings.CIRCUIT_BREAKER_RECOVERY,
            )

    def record_success(self):
        if self.failures > 0:
            logger.info("Circuit RESET (was at %d failures)", self.failures)
        self.failures = 0
        self.open_until = 0.0


class HifiClient:
    def __init__(self):
        self.instances: list[str] = []
        self._load_instances()
        self.client = httpx.AsyncClient(
            http2=True,
            limits=httpx.Limits(
                max_connections=settings.UPSTREAM_MAX_CONNECTIONS,
                max_keepalive_connections=settings.UPSTREAM_MAX_KEEPALIVE,
            ),
            timeout=settings.UPSTREAM_TIMEOUT,
        )
        self._semaphore = asyncio.Semaphore(settings.UPSTREAM_MAX_CONCURRENCY)
        self._circuits: dict[str, _CircuitState] = {
            url: _CircuitState() for url in self.instances
        }

    def _load_instances(self):
        """Load upstream instances from HIFI_INSTANCES config."""
        self.instances = list(settings.HIFI_INSTANCES)
        logger.info(f"Loaded {len(self.instances)} upstream instances from environment.")

    def _get_circuit(self, base_url: str) -> _CircuitState:
        """Get or create circuit state for an instance."""
        if base_url not in self._circuits:
            self._circuits[base_url] = _CircuitState()
        return self._circuits[base_url]

    async def close(self):
        await self.client.aclose()

    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute GET request with:
        - Concurrency limiting (semaphore)
        - Random instance selection with failover
        - Per-instance circuit breaker
        """
        async with self._semaphore:
            candidates = list(self.instances)
            random.shuffle(candidates)

            # Partition into available and open-circuit instances
            available = []
            half_open = []
            for url in candidates:
                circuit = self._get_circuit(url)
                if circuit.is_open:
                    continue  # Skip fully-open circuits
                elif circuit.is_half_open:
                    half_open.append(url)  # Allow as last resort
                else:
                    available.append(url)

            # Try available first, then half-open as probes
            ordered = available + half_open

            if not ordered:
                logger.error("All upstream instances have open circuits")
                raise ConnectionError("All upstream instances are unavailable")

            last_error = None

            for base_url in ordered:
                circuit = self._get_circuit(base_url)
                url = f"{base_url}{endpoint}"
                try:
                    resp = await self.client.get(url, params=params)
                    if resp.status_code >= 500:
                        circuit.record_failure()
                        last_error = f"Status {resp.status_code}"
                        continue

                    resp.raise_for_status()
                    circuit.record_success()
                    return resp.json()
                except httpx.HTTPStatusError as e:
                    # Do not retry on 4xx client errors — not the instance's fault
                    circuit.record_success()  # Instance is reachable
                    raise e
                except Exception as e:
                    circuit.record_failure()
                    last_error = e
                    continue

            logger.warning(f"All upstream instances failed. Last error: {last_error}")
            raise last_error if isinstance(last_error, Exception) else Exception(str(last_error) if last_error else "No instances available")

    # --- Search (cached, short TTL) ---

    async def search_tracks(self, query: str):
        key = _make_key("search_tracks", query)
        return await cached_call(search_cache, key, lambda: self._get("/search/", params={"s": query}))

    async def search_artists(self, query: str):
        key = _make_key("search_artists", query)
        return await cached_call(search_cache, key, lambda: self._get("/search/", params={"a": query}))
    
    async def search_albums(self, query: str):
        key = _make_key("search_albums", query)
        return await cached_call(search_cache, key, lambda: self._get("/search/", params={"al": query}))

    # --- Metadata (cached, long TTL) ---

    async def get_artist(self, artist_id: int):
        key = _make_key("artist", artist_id)
        return await cached_call(artist_cache, key, lambda: self._get("/artist/", params={"id": artist_id}))

    async def get_artist_albums(self, artist_id: int):
        key = _make_key("artist_albums", artist_id)
        return await cached_call(album_cache, key, lambda: self._get("/artist/", params={"f": artist_id}))

    async def get_album(self, album_id: int):
        key = _make_key("album", album_id)
        return await cached_call(album_cache, key, lambda: self._get("/album/", params={"id": album_id}))

    async def get_similar_artists(self, artist_id: int):
        key = _make_key("similar_artists", artist_id)
        return await cached_call(similar_cache, key, lambda: self._get("/artist/similar/", params={"id": artist_id}))

    async def get_artist_top_tracks(self, artist_id: int):
        """Get an artist's top tracks via /artist/?f={id} (tracks sorted by popularity)."""
        key = _make_key("artist_top_tracks", artist_id)
        return await cached_call(artist_cache, key, lambda: self._get("/artist/", params={"f": artist_id}))

    async def get_track(self, track_id: int, quality: str = "LOSSLESS"):
        """Get track streaming info (manifest/url). NOT cached — URLs are time-limited."""
        return await self._get("/track/", params={"id": track_id, "quality": quality})

    async def get_track_info(self, track_id: int):
        """
        Get full track metadata (title, artist, album, duration, cover).
        Uses /info/ endpoint which returns complete track information.
        """
        key = _make_key("track_info", track_id)
        return await cached_call(track_cache, key, lambda: self._get("/info/", params={"id": track_id}))

    async def get_track_full(self, track_id: int, quality: str = "LOSSLESS"):
        """
        Concurrently fetches both /info/ (full metadata, BPM) and /track/ (accurate Replay Gain).
        Merges the precise gain data from /track/ into the /info/ payload and returns the unified track dictionary.
        
        /info/ results are cached; /track/ is always live (stream URLs are time-limited).
        """
        info_task = self.get_track_info(track_id)
        # Pass quality to get accurate format/gain for the requested stream quality
        track_task = self.get_track(track_id, quality=quality)
        
        info_res, track_res = await asyncio.gather(info_task, track_task, return_exceptions=True)
        
        # If info failed, we can't return a unified payload, return early or raise
        if isinstance(info_res, Exception):
            raise info_res
        
        # Deep copy so cached /info/ data isn't mutated
        merged = copy.deepcopy(info_res)
        
        # If we successfully got track details, inject its specialized gain fields into info["data"]
        if not isinstance(track_res, Exception) and track_res and "data" in track_res:
            td = track_res["data"]
            if merged and "data" in merged:
                md = merged["data"]
                # Save the album-level gain values from /track into the /info dict
                if "albumReplayGain" in td:
                    md["albumReplayGain"] = td["albumReplayGain"]
                if "albumPeakAmplitude" in td:
                    md["albumPeakAmplitude"] = td["albumPeakAmplitude"]
                if "trackReplayGain" in td:
                    md["trackReplayGain"] = td["trackReplayGain"]
                if "trackPeakAmplitude" in td:
                    md["trackPeakAmplitude"] = td["trackPeakAmplitude"]
                    
        return merged

    async def get_lyrics(self, track_id: int):
        """Get lyrics for a track ID."""
        key = _make_key("lyrics", track_id)
        return await cached_call(lyrics_cache, key, lambda: self._get("/lyrics/", params={"id": track_id}))

    async def get_similar_tracks(self, track_id: int):
        """Get similar tracks (recommendations) for a track ID."""
        key = _make_key("similar_tracks", track_id)
        return await cached_call(similar_cache, key, lambda: self._get("/recommendations/", params={"id": track_id}))

hifi_client = HifiClient()
