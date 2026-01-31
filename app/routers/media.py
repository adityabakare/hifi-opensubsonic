"""
Media endpoints for streaming and cover art.
"""
from fastapi import APIRouter, Query, Depends, Form
from fastapi.responses import RedirectResponse, Response
from typing import Optional
import base64
import json
import re
import logging

from app.config import settings
from app.hifi_client import hifi_client
from app.responses import SubsonicResponse
from app.routers.common import common_params, get_track_format

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/rest/getCoverArt.view")
@router.get("/rest/getCoverArt")
async def get_cover_art(
    id: str,
    size: Optional[int] = Query(None),
    commons: dict = Depends(common_params)
):
    # Map requested size to Tidal sizes
    req_size = size if size else 0
    
    target_size = 1280
    if req_size > 0:
        if req_size <= 80:
            target_size = 80
        elif req_size <= 160:
            target_size = 160
        elif req_size <= 320:
            target_size = 320
        elif req_size <= 640:
            target_size = 640
        elif req_size <= 750:
            target_size = 750
        else:
            target_size = 1280
    else:
        target_size = 750
    
    # Detect type from prefix
    type_hint = "album"
    clean_id = id
    for prefix in ["album-", "track-", "artist-"]:
        if clean_id.startswith(prefix):
            type_hint = prefix.replace("-", "")
            clean_id = clean_id[len(prefix):]
            break
            
    final_id = clean_id.replace("-", "/") 
    
    # If numeric ID (legacy or prefixed), resolve to UUID
    if "-" not in clean_id:
        resolved_uuid = None
         
        async def try_album():
            try:
                alb = await hifi_client.get_album(clean_id)
                if alb and "cover" in alb:
                    return alb["cover"]
            except Exception:
                return None
             
        async def try_artist():
            try:
                art = await hifi_client.get_artist(clean_id)
                if art and "picture" in art:
                    return art["picture"]
            except Exception:
                return None

        if type_hint == "artist":
            resolved_uuid = await try_artist()
        elif type_hint == "album":
            resolved_uuid = await try_album()
        else:
            resolved_uuid = await try_album()
            if not resolved_uuid:
                resolved_uuid = await try_artist()
         
        if resolved_uuid:
            final_id = resolved_uuid.replace("-", "/")

    tidal_url = f"https://resources.tidal.com/images/{final_id}/{target_size}x{target_size}.jpg"
    
    try:
        resp = await hifi_client.client.get(tidal_url, timeout=10.0)
        if resp.status_code != 200:
            return SubsonicResponse.error(70, "Cover art inaccessible", fmt=commons["f"])
        
        return Response(content=resp.content, media_type=resp.headers.get("content-type", "image/jpeg"))
        
    except Exception:
        return SubsonicResponse.error(70, "Failed to fetch cover art", fmt=commons["f"])


@router.get("/rest/stream.view")
@router.get("/rest/stream")
async def stream(
    id: str,
    commons: dict = Depends(common_params)
):
    """
    Streams the media.
    Decodes Tidal manifest and redirects to the direct stream URL.
    """
    track_id = id
    if id.startswith("track-"):
        track_id = id.split("-")[1]

    try:
        data = await hifi_client.get_track(int(track_id))
        if not data or "data" not in data:
            return SubsonicResponse.error(70, "Stream not found", fmt=commons["f"])
             
        d = data["data"]
        
        # 1. Direct URL
        if "url" in d:
            return RedirectResponse(d["url"])
            
        # 2. Manifest
        if "manifest" in d:
            manifest_data = d["manifest"]
            mime = d.get("manifestMimeType")
             
            try:
                decoded = base64.b64decode(manifest_data).decode('utf-8')
                 
                if mime == "application/vnd.tidal.bts":
                    manifest = json.loads(decoded)
                    if "urls" in manifest and manifest["urls"]:
                        return RedirectResponse(manifest["urls"][0])
                 
                elif mime == "application/dash+xml":
                    match = re.search(r'media="(https://[^"]+)"', decoded)
                    if match:
                        return RedirectResponse(match.group(1))
                    
                    match_base = re.search(r'<BaseURL>(https://[^<]+)</BaseURL>', decoded)
                    if match_base:
                        return RedirectResponse(match_base.group(1))

            except Exception as e:
                logger.warning(f"Manifest decode error: {e}")
                pass
             
    except Exception as e:
        logger.error(f"Stream error: {e}")
        
    return SubsonicResponse.error(70, "Stream not found", fmt=commons["f"])


@router.get("/rest/getSong.view")
@router.get("/rest/getSong")
@router.post("/rest/getSong.view")
@router.post("/rest/getSong")
async def get_song(
    id: str = Query(None),
    id_form: str = Form(None, alias="id"),
    commons: dict = Depends(common_params)
):
    real_id = id or id_form
    if not real_id:
        return SubsonicResponse.error(10, "Required parameter is missing, id not found", fmt=commons["f"])
    
    id = real_id
    track_id = id
    if id.startswith("track-"):
        track_id = id.split("-")[1]
    
    try:
        # Use /info endpoint which returns full track metadata
        data = await hifi_client.get_track_info(int(track_id))
        if data and "data" in data:
            track = data["data"]
            cover_uuid = track.get("album", {}).get("cover")
            cover_art_id = cover_uuid if cover_uuid else f"album-{track.get('album', {}).get('id')}"

            fmt_info = get_track_format(track)
            song = {
                "id": f"track-{track.get('id')}",
                "title": track.get("title") or "Unknown Title",
                "artist": track.get("artist", {}).get("name"),
                "artistId": f"artist-{track.get('artist', {}).get('id')}",
                "album": track.get("album", {}).get("title"),
                "albumId": f"album-{track.get('album', {}).get('id')}",
                "coverArt": cover_art_id, 
                "duration": track.get("duration"),
                "track": track.get("trackNumber"),
                "discNumber": track.get("volumeNumber"),
                "replayGain": track.get("trackReplayGain") or track.get("replayGain"),
                "year": int(track.get("streamStartDate")[:4]) if track.get("streamStartDate") else None,
                "isDir": False,
                "isVideo": False,
                **fmt_info
            }
            return SubsonicResponse.create({"song": song}, fmt=commons["f"])
    
    except Exception:
        pass
        
    return SubsonicResponse.error(70, "Song not found", fmt=commons["f"])

@router.get("/rest/getLyricsBySongId.view")
@router.get("/rest/getLyricsBySongId")
async def get_lyrics_by_song_id(
    id: str,
    commons: dict = Depends(common_params)
):
    """
    OpenSubsonic extension: Get lyrics by song ID.
    PROXIES to hifi-api /lyrics/ endpoint.
    """
    track_id = id
    if id.startswith("track-"):
        track_id = id.split("-")[1]
    
    try:
        data = await hifi_client.get_lyrics(int(track_id))
        if data and "lyrics" in data:
            # hifi-api returns raw string or dict? upstream main.py says: return {"lyrics": data}
            # and data comes from Tidal /lyrics endpoint which returns JSON.
            # We need to extract the actual lyrics text.
            
            # Tidal /lyrics response structure:
            # {
            #   "trackId": 123,
            #   "lyrics": "Line 1\nLine 2...",
            #   "syncLyrics": "..."
            # }
            # hifi-api returns: {"version":..., "lyrics": <tidal_resp>}
            
            lyrics_data = data["lyrics"]
            content = lyrics_data.get("lyrics")
            
            if content:
                return SubsonicResponse.create({
                    "lyrics": {
                        "artist": "Unknown", # We don't have this unless we fetch track info too
                        "title": "Unknown",
                        "value": content
                    }
                }, fmt=commons["f"])
                
    except Exception as e:
        logger.warning(f"Lyrics fetch failed for {id}: {e}")
        pass
        
    return SubsonicResponse.error(70, "Lyrics not found", fmt=commons["f"])


@router.get("/rest/getLyrics.view")
@router.get("/rest/getLyrics")
async def get_lyrics(
    artist: Optional[str] = None,
    title: Optional[str] = None,
    commons: dict = Depends(common_params)
):
    """
    Standard Subsonic getLyrics.
    Attempts to find song by Artist + Title, then fetches lyrics.
    """
    if not artist or not title:
         return SubsonicResponse.error(10, "Artist and title required", fmt=commons["f"])
         
    query = f"{artist} {title}"
    try:
        # 1. Search for the track
        search_res = await hifi_client.search_tracks(query)
        items = []
        if search_res and "data" in search_res:
             items = search_res["data"].get("items", [])
             
        if not items:
             return SubsonicResponse.error(70, "Song not found", fmt=commons["f"])
             
        # 2. Use the first match's ID to get lyrics
        first_match = items[0]
        track_id = first_match.get("id")
        
        # 3. Fetch Lyrics
        data = await hifi_client.get_lyrics(track_id)
        if data and "lyrics" in data:
            lyrics_data = data["lyrics"]
            content = lyrics_data.get("lyrics")
            
            if content:
                return SubsonicResponse.create({
                    "lyrics": {
                        "artist": artist,
                        "title": title,
                        "value": content
                    }
                }, fmt=commons["f"])

    except Exception as e:
        logger.warning(f"Lyrics search/fetch failed for {query}: {e}")
        pass

    return SubsonicResponse.error(70, "Lyrics not found", fmt=commons["f"])
