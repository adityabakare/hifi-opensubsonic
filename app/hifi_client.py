import httpx
from typing import Optional, Dict, Any, List
import json
import random
import os
from app.config import settings

class HifiClient:
    def __init__(self):
        self.instances = []
        self._load_instances()
        self.client = httpx.AsyncClient(timeout=30.0)

    def _load_instances(self):
        """Load upstream instances from JSON or config."""
        path = "instances.json"
        
        # Fallback to parent directory if running from subdir
        if not os.path.exists(path) and os.path.exists(os.path.join("..", path)):
            path = os.path.join("..", path)

        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    self.instances = json.load(f)
                print(f"Loaded {len(self.instances)} instances.")
            except Exception as e:
                print(f"Failed to load instances.json: {e}")
        
        # Fallback to default if empty
        if not self.instances:
            self.instances = [settings.HIFI_API_URL]

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
        
        print(f"All instances failed. Last error: {last_error}")
        raise last_error if last_error else Exception("No instances available")

    # --- Search ---

    async def search(self, query: str) -> Dict[str, Any]:
        return await self._get("/search/", params={"s": query})

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

    async def get_track(self, track_id: int, quality: str = "LOSSLESS"):
        return await self._get("/track/", params={"id": track_id, "quality": quality})

    async def get_stream_url(self, track_id: int) -> Optional[str]:
        return await self.get_track(track_id)

hifi_client = HifiClient()
