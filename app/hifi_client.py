import httpx
from typing import Optional, Dict, Any, List
import random
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class HifiClient:
    def __init__(self):
        self.instances = []
        self._load_instances()
        self.client = httpx.AsyncClient(
            http2=True,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
            timeout=60.0,
        )

    def _load_instances(self):
        """Load upstream instances from HIFI_INSTANCES config."""
        self.instances = list(settings.HIFI_INSTANCES)
        logger.info(f"Loaded {len(self.instances)} upstream instances from environment.")

    async def close(self):
        await self.client.aclose()

    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute GET request with random instance failover.
        """
        candidates = list(self.instances)
        random.shuffle(candidates)
        
        last_error = None
        
        for base_url in candidates:
            url = f"{base_url}{endpoint}"
            try:
                resp = await self.client.get(url, params=params)
                if resp.status_code >= 500:
                    last_error = f"Status {resp.status_code}"
                    continue
                
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                # Do not retry on 4xx client errors
                raise e
            except Exception as e:
                # Retry on connection errors or 5xx (handled above via continue)
                last_error = e
                continue
        
        logger.warning(f"All upstream instances failed. Last error: {last_error}")
        raise last_error if last_error else Exception("No instances available")

    # --- Search ---

    async def search_tracks(self, query: str):
        return await self._get("/search/", params={"s": query})

    async def search_artists(self, query: str):
        return await self._get("/search/", params={"a": query})
    
    async def search_albums(self, query: str):
        return await self._get("/search/", params={"al": query})

    # --- Metadata ---

    async def get_artist(self, artist_id: int):
        return await self._get("/artist/", params={"id": artist_id})

    async def get_artist_albums(self, artist_id: int):
        return await self._get("/artist/", params={"f": artist_id})

    async def get_album(self, album_id: int):
        return await self._get("/album/", params={"id": album_id})

    async def get_similar_artists(self, artist_id: int):
        return await self._get("/artist/similar/", params={"id": artist_id})

    async def get_track(self, track_id: int, quality: str = "LOSSLESS"):
        """Get track streaming info (manifest/url). For metadata use get_track_info()."""
        return await self._get("/track/", params={"id": track_id, "quality": quality})

    async def get_track_info(self, track_id: int):
        """
        Get full track metadata (title, artist, album, duration, cover).
        Uses /info/ endpoint which returns complete track information.
        """
        return await self._get("/info/", params={"id": track_id})

    async def get_lyrics(self, track_id: int):
        """Get lyrics for a track ID."""
        return await self._get("/lyrics/", params={"id": track_id})

hifi_client = HifiClient()
