"""
Media endpoints for streaming and cover art.
"""
from fastapi import APIRouter, Query, Depends, Form
import asyncio
import re
from fastapi.responses import RedirectResponse, Response
from typing import Optional
import base64
import json
import logging

from app.config import settings
from app.hifi_client import hifi_client
from app.responses import SubsonicResponse
from app.routers.common import common_params, extract_track_metadata, fetch_track_info_safe, resolve_id

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/rest/getCoverArt.view")
@router.get("/rest/getCoverArt")
@router.post("/rest/getCoverArt.view")
@router.post("/rest/getCoverArt")
async def get_cover_art(
    id: str = Query(None),
    size: Optional[int] = Query(None),
    id_form: str = Form(None, alias="id"),
    size_form: Optional[int] = Form(None, alias="size"),
    commons: dict = Depends(common_params)
):

    real_id = id or id_form
    if not real_id:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=commons["f"])

    req_size = (size_form if size_form is not None else size) or 0

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

    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE
    )

    clean_id = real_id
    type_hint = "album"  # default

    # Check if it's already a UUID
    if uuid_pattern.match(clean_id):
        final_id = clean_id.replace("-", "/")
    else:
        # Extract numeric ID and type hint from various prefix formats
        if clean_id.startswith("ar-"):
            type_hint = "artist"
        elif clean_id.startswith("al-"):
            type_hint = "album"
        elif clean_id.startswith("tr-"):
            type_hint = "track"

        try:
            numeric_id = resolve_id(clean_id)
        except ValueError:
            return SubsonicResponse.error(70, "Invalid cover art ID", fmt=commons["f"])

        # Resolve numeric ID to UUID via upstream API
        resolved_uuid = None
        video_cover_uuid = None

        if type_hint == "artist":
            try:
                art = await hifi_client.get_artist(numeric_id)
                artist_data = art.get("artist", {}) if isinstance(art, dict) else {}
                resolved_uuid = artist_data.get("picture")
            except Exception as e:
                logger.warning("Failed to fetch artist cover art for %s: %s", numeric_id, e)
        else:
            try:
                alb = await hifi_client.get_album(numeric_id)
                album_data = alb.get("data", {}) if isinstance(alb, dict) else {}
                resolved_uuid = album_data.get("cover")
                video_cover_uuid = album_data.get("videoCover")
            except Exception as e:
                logger.warning("Failed to fetch album cover art for %s: %s", numeric_id, e)

        if not resolved_uuid:
            return SubsonicResponse.error(70, "Cover art not found", fmt=commons["f"])

        # If album has a video cover, serve the animated mp4 instead of static image
        if video_cover_uuid:
            video_id = video_cover_uuid.replace("-", "/")
            video_size = target_size if target_size <= 1280 else 1280
            tidal_url = f"https://resources.tidal.com/videos/{video_id}/{video_size}x{video_size}.mp4"
            return RedirectResponse(tidal_url)

        final_id = resolved_uuid.replace("-", "/")

    tidal_url = f"https://resources.tidal.com/images/{final_id}/{target_size}x{target_size}.jpg"

    return RedirectResponse(tidal_url)


@router.get("/rest/stream.view")
@router.get("/rest/stream")
@router.post("/rest/stream.view")
@router.post("/rest/stream")
@router.get("/rest/download.view")
@router.get("/rest/download")
@router.post("/rest/download.view")
@router.post("/rest/download")
async def stream(
    id: str = Query(None),
    maxBitRate: Optional[int] = Query(None),
    format: Optional[str] = Query(None),
    id_form: str = Form(None, alias="id"),
    maxBitRate_form: Optional[int] = Form(None, alias="maxBitRate"),
    format_form: Optional[str] = Form(None, alias="format"),
    commons: dict = Depends(common_params)
):
    """
    Streams the media.
    Decodes Tidal manifest and redirects to the direct stream URL.
    """
    real_id = id or id_form
    if not real_id:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=commons["f"])
    maxBitRate = maxBitRate_form if maxBitRate_form is not None else maxBitRate
    format = format_form if format_form is not None else format

    try:
        track_id = resolve_id(real_id)
    except ValueError:
        return SubsonicResponse.error(70, "Invalid stream ID", fmt=commons["f"])

    # Map maxBitRate to Tidal qualities
    # Tidal qualities: LOW (~96kbps), HIGH (~320kbps), LOSSLESS (FLAC), HI_RES_LOSSLESS
    quality = "LOSSLESS"
    if maxBitRate:
        if maxBitRate <= 160:
            quality = "LOW"
        elif maxBitRate <= 320:
            quality = "HIGH"
            
    if format and format.lower() in ("m4a", "mp3"):
        # Forcing a lossy format
        quality = "HIGH"

    try:
        data = await hifi_client.get_track(track_id, quality=quality)
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
    
    try:
        track_id = resolve_id(real_id)
    except ValueError:
        return SubsonicResponse.error(70, "Song not found", fmt=commons["f"])
    
    try:
        # Use combined endpoint which returns full track metadata + accurate replay gain
        data = await hifi_client.get_track_full(int(track_id))
        if data and "data" in data:
            track = extract_track_metadata(data["data"])
            return SubsonicResponse.create({
                "song": track
            }, fmt=commons["f"])
    except Exception as e:
        logger.error(f"Failed to get song {track_id}: {e}")
        
    return SubsonicResponse.error(70, "Song not found", fmt=commons["f"])

@router.get("/rest/getLyricsBySongId.view")
@router.get("/rest/getLyricsBySongId")
@router.post("/rest/getLyricsBySongId.view")
@router.post("/rest/getLyricsBySongId")
async def get_lyrics_by_song_id(
    id: str = Query(None),
    id_form: str = Form(None, alias="id"),
    commons: dict = Depends(common_params)
):
    """
    OpenSubsonic extension: Get structured lyrics by song ID.
    Returns lyricsList with structuredLyrics per the OpenSubsonic spec.
    """
    real_id = id or id_form
    if not real_id:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=commons["f"])

    try:
        track_numeric_id = resolve_id(real_id)
    except ValueError:
        return SubsonicResponse.error(70, "Invalid song ID", fmt=commons["f"])
    
    try:
        # Fetch lyrics and track info in parallel
        lyrics_data, track_data = await asyncio.gather(
            hifi_client.get_lyrics(track_numeric_id),
            fetch_track_info_safe(track_numeric_id),
        )
        
        if not lyrics_data or "lyrics" not in lyrics_data:
            return SubsonicResponse.error(70, "Lyrics not found", fmt=commons["f"])
        
        content = lyrics_data["lyrics"].get("subtitles", "")
        if not content:
            return SubsonicResponse.error(70, "Lyrics not found", fmt=commons["f"])
        
        # Extract artist/title from track info
        artist_name = "Unknown"
        track_title = "Unknown"
        if track_data and "data" in track_data:
            t = track_data["data"]
            artist_name = t.get("artist", {}).get("name") or "Unknown"
            track_title = t.get("title") or "Unknown"
        
        # Parse LRC format into structured lines
        lrc_pattern = re.compile(r'\[(\d{2}):(\d{2})\.(\d{2,3})\]\s?(.*)')
        lines = []
        is_synced = False
        
        for raw_line in content.split("\n"):
            match = lrc_pattern.match(raw_line.strip())
            if match:
                minutes, seconds, centis, text = match.groups()
                # Convert to milliseconds
                ms = int(minutes) * 60000 + int(seconds) * 1000
                if len(centis) == 2:
                    ms += int(centis) * 10
                else:
                    ms += int(centis)
                lines.append({"start": ms, "value": text})
                is_synced = True
            elif raw_line.strip():
                lines.append({"value": raw_line.strip()})
        
        structured = {
            "displayArtist": artist_name,
            "displayTitle": track_title,
            "lang": "und",
            "synced": is_synced,
            "offset": 0,
            "line": lines,
        }
        
        return SubsonicResponse.create({
            "lyricsList": {
                "structuredLyrics": [structured]
            }
        }, fmt=commons["f"])
                
    except Exception as e:
        logger.warning(f"Lyrics fetch failed for {real_id}: {e}")
        
    return SubsonicResponse.error(70, "Lyrics not found", fmt=commons["f"])


@router.get("/rest/getLyrics.view")
@router.get("/rest/getLyrics")
@router.post("/rest/getLyrics.view")
@router.post("/rest/getLyrics")
async def get_lyrics(
    artist: Optional[str] = Query(None),
    title: Optional[str] = Query(None),
    artist_form: Optional[str] = Form(None, alias="artist"),
    title_form: Optional[str] = Form(None, alias="title"),
    commons: dict = Depends(common_params)
):
    """
    Standard Subsonic getLyrics.
    Attempts to find song by Artist + Title, then fetches lyrics.
    """
    artist = artist or artist_form
    title = title or title_form
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

    return SubsonicResponse.error(70, "Lyrics not found", fmt=commons["f"])
