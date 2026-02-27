import httpx
import hashlib
import time
import logging
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

class LastFmClient:
    def __init__(self):
        self.base_url = "http://ws.audioscrobbler.com/2.0/"
        self.client = httpx.AsyncClient(timeout=10.0)

    def is_configured(self) -> bool:
        return bool(settings.LASTFM_API_KEY and settings.LASTFM_API_SECRET)

    def _get_api_signature(self, params: Dict[str, str]) -> str:
        """
        Generates the api_sig for Last.fm API calls.
        """
        sorted_keys = sorted(params.keys())
        sig_string = "".join(f"{k}{params[k]}" for k in sorted_keys if k != "format" and k != "callback")
        sig_string += settings.LASTFM_API_SECRET
        return hashlib.md5(sig_string.encode('utf-8')).hexdigest()

    async def get_session(self, token: str) -> Optional[str]:
        """
        Exchange an auth token for a session key.
        """
        if not self.is_configured():
            logger.warning("Last.fm is not configured.")
            return None

        params = {
            "method": "auth.getSession",
            "api_key": settings.LASTFM_API_KEY,
            "token": token
        }
        params["api_sig"] = self._get_api_signature(params)
        params["format"] = "json"

        try:
            resp = await self.client.get(self.base_url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if "session" in data and "key" in data["session"]:
                return data["session"]["key"]
            logger.error(f"Last.fm getSession error: {data}")
            return None
        except Exception as e:
            logger.error(f"Failed to get Last.fm session: {e}")
            return None

    async def scrobble_track(self, session_key: str, artist: str, track: str, timestamp: int, album: Optional[str] = None):
        """
        Scrobble a single track.
        timestamp must be a unix timestamp.
        """
        if not self.is_configured() or not session_key:
            return False

        params = {
            "method": "track.scrobble",
            "api_key": settings.LASTFM_API_KEY,
            "sk": session_key,
            "artist": artist,
            "track": track,
            "timestamp": str(timestamp)
        }
        if album:
            params["album"] = album

        params["api_sig"] = self._get_api_signature(params)
        params["format"] = "json"

        try:
            resp = await self.client.post(self.base_url, data=params)
            logger.info("Successfully scrobbled to Last.fm: %s - %s", artist, track)
            return True
        except httpx.HTTPError as e:
            logger.error("Failed to scrobble track %s to Last.fm: %s", track, e)
            try:
                logger.error("Response: %s", e.response.text)
            except AttributeError:
                logger.debug("No response body available for scrobble error")
            return False

lastfm_client = LastFmClient()
