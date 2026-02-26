"""
Common utilities shared across all Subsonic router modules.
"""
from fastapi import Query, Depends, Form
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.hifi_client import hifi_client
from app.responses import SubsonicResponse, SubsonicException
from app.database import get_session
from app.auth import authenticate_user


async def common_params(
    u: Optional[str] = Query(None),
    p: Optional[str] = Query(None),
    t: Optional[str] = Query(None),
    s: Optional[str] = Query(None),
    v: Optional[str] = Query(None),
    c: Optional[str] = Query(None),
    f: str = Query("json"),
    
    # Form variants for POST requests
    u_form: Optional[str] = Form(None, alias="u"),
    p_form: Optional[str] = Form(None, alias="p"),
    t_form: Optional[str] = Form(None, alias="t"),
    s_form: Optional[str] = Form(None, alias="s"),
    v_form: Optional[str] = Form(None, alias="v"),
    c_form: Optional[str] = Form(None, alias="c"),
    f_form: Optional[str] = Form(None, alias="f"),
    
    session: AsyncSession = Depends(get_session),
):
    """
    Common authentication dependency for all Subsonic endpoints.
    Support both Query params and Form data.
    """
    # Merge values (Query takes precedence if both, or vice versa? Logic: check both)
    final_u = u or u_form
    final_p = p or p_form
    final_t = t or t_form
    final_s = s or s_form
    final_v = v or v_form
    final_c = c or c_form
    final_f = f if f != "json" else (f_form or "json")
    
    fmt = final_f
    
    user = None
    if final_u and final_p:
        # Handle 'enc:' hex-encoded passwords
        password = final_p
        if final_p.startswith("enc:"):
            try:
                hex_str = final_p[4:]
                password = bytes.fromhex(hex_str).decode("utf-8")
            except Exception:
                pass  # Fallback to raw password if decode fails
        
        user = await authenticate_user(session, final_u, password)

    if not user:
        if not final_u:
            raise SubsonicException(code=10, message="Required parameter is missing.", fmt=fmt)
        else:
            raise SubsonicException(code=40, message="Wrong username or password", fmt=fmt)
    
    return {"f": fmt, "v": final_v, "user": user}


def get_track_format(item: dict) -> dict:
    """
    Derive Subsonic format metadata from Tidal item.
    """
    quality = item.get("audioQuality", "LOSSLESS")
    
    bit_depth = item.get("bitDepth")
    sample_rate = item.get("sampleRate")
    exact_bitrate = None
    
    if bit_depth and sample_rate:
        exact_bitrate = int((bit_depth * sample_rate * 2) / 1000)

    if quality in ["HI_RES_LOSSLESS", "LOSSLESS"]:
        return {
            "suffix": "flac",
            "contentType": "audio/flac",
            "bitRate": exact_bitrate if exact_bitrate else 1411,
            "bitDepth": bit_depth if bit_depth else 16,
            "samplingRate": sample_rate if sample_rate else 44100,
            "size": int((exact_bitrate if exact_bitrate else 1411) * 1000 * item.get("duration", 0) / 8),
            "path": f"music/{item.get('id')}.flac"
        }
    elif quality == "HIGH":
        return {
            "suffix": "m4a",
            "contentType": "audio/mp4",
            "bitRate": exact_bitrate if exact_bitrate else 320,
            "size": int((exact_bitrate if exact_bitrate else 320) * 1000 * item.get("duration", 0) / 8),
            "path": f"music/{item.get('id')}.m4a"
        }
    else:
        return {
            "suffix": "m4a",
            "contentType": "audio/mp4",
            "bitRate": exact_bitrate if exact_bitrate else 96,
            "size": int((exact_bitrate if exact_bitrate else 96) * 1000 * item.get("duration", 0) / 8),
            "path": f"music/{item.get('id')}.m4a"
        }


def extract_track_metadata(track: dict) -> dict:
    """
    Extract complete track metadata from a Tidal track response.
    Used by search, browsing, and playlist endpoints for consistency.
    
    Args:
        track: Raw track data from hifi-api (/info, /search, /album)
    
    Returns:
        dict: Complete Subsonic-compatible track metadata
    """
    # Get format info (bitRate, bitDepth, samplingRate, suffix, contentType, size, path)
    fmt_info = get_track_format(track)
    
    # Cover art ID (prefer UUID, fallback to album-{id})
    cover_uuid = track.get("album", {}).get("cover")
    cover_art_id = cover_uuid if cover_uuid else f"album-{track.get('album', {}).get('id')}"
    
    # Extract year from streamStartDate or releaseDate
    year = None
    if track.get("streamStartDate"):
        try:
            year = int(track.get("streamStartDate")[:4])
        except:
            pass
    elif track.get("releaseDate"):
        try:
            year = int(track.get("releaseDate")[:4])
        except:
            pass
    
    return {
        "id": f"track-{track.get('id')}",
        "title": track.get("title") or "Unknown Title",
        "artist": track.get("artist", {}).get("name") or "Unknown Artist",
        "artistId": f"artist-{track.get('artist', {}).get('id')}",
        "album": track.get("album", {}).get("title") or "Unknown Album",
        "albumId": f"album-{track.get('album', {}).get('id')}",
        "coverArt": cover_art_id,
        "duration": track.get("duration") or 0,
        "track": track.get("trackNumber"),
        "discNumber": track.get("volumeNumber"),
        "year": year,
        "replayGain": {
            "trackGain": track.get("replayGain"),
            "trackPeak": track.get("peak"),
            "baseGain": 0,
        },
        "parent": f"album-{track.get('album', {}).get('id')}",
        "isDir": False,
        "isVideo": False,
        "type": "music",
        **fmt_info
    }


def extract_playlist_entry_data(track: dict) -> dict:
    """
    Extract track metadata for PlaylistEntry storage (snake_case keys).
    Uses the same logic as extract_track_metadata but returns DB-compatible field names.
    
    Args:
        track: Raw track data from hifi-api (/info endpoint)
    
    Returns:
        dict: PlaylistEntry-compatible metadata (snake_case keys)
    """
    fmt_info = get_track_format(track)
    
    cover_uuid = track.get("album", {}).get("cover")
    cover_art_id = cover_uuid if cover_uuid else f"album-{track.get('album', {}).get('id')}"
    
    year = None
    if track.get("streamStartDate"):
        try:
            year = int(track.get("streamStartDate")[:4])
        except:
            pass
    elif track.get("releaseDate"):
        try:
            year = int(track.get("releaseDate")[:4])
        except:
            pass
    
    return {
        "track_id": f"track-{track.get('id')}",
        "title": track.get("title") or "Unknown Title",
        "artist": track.get("artist", {}).get("name") or "Unknown Artist",
        "artist_id": f"artist-{track.get('artist', {}).get('id')}",
        "album": track.get("album", {}).get("title") or "Unknown Album",
        "album_id": f"album-{track.get('album', {}).get('id')}",
        "cover_art": cover_art_id,
        "duration": track.get("duration") or 0,
        "track_number": track.get("trackNumber"),
        "disc_number": track.get("volumeNumber"),
        "year": year,
        "bit_rate": fmt_info.get("bitRate", 1411),
        "bit_depth": fmt_info.get("bitDepth", 16),
        "sampling_rate": fmt_info.get("samplingRate", 44100),
        "suffix": fmt_info.get("suffix", "flac"),
        "content_type": fmt_info.get("contentType", "audio/flac"),
    }


async def fetch_artist_albums(artist_id: int, artist_name: str = "") -> list:
    """
    Fetch all albums for an artist using the upstream's direct endpoint.
    Falls back to search-based matching if the direct endpoint fails.

    Args:
        artist_id: The artist's numeric ID.
        artist_name: The artist's display name (used in fallback).

    Returns:
        List of album dicts that belong to this artist.
    """
    def preference_deduplicator(album_list: list) -> list:
        pref = settings.EXPLICIT_CONTENT_FILTER.lower()
        groups = {}
        deduped_no_title = []
        
        for alb in album_list:
            title = alb.get("title", "").strip().lower()
            if not title:
                deduped_no_title.append(alb)
            else:
                if title not in groups:
                    groups[title] = []
                groups[title].append(alb)
                
        deduped = list(deduped_no_title)
        for title, versions in groups.items():
            best_alb = None
            best_score = -100
            
            for alb in versions:
                score = 0
                is_explicit = alb.get("explicit", False)
                q = alb.get("audioQuality", "")
                
                # Quality base score
                if q in ["HI_RES", "HI_RES_LOSSLESS", "HIRES_LOSSLESS"]: score += 10
                elif q == "LOSSLESS": score += 8
                elif q == "HIGH": score += 5
                elif q == "LOW": score -= 5
                
                # Penalty for Atmos/Sony360 because they might not play right on standard clients
                tags = alb.get("mediaMetadata", {}).get("tags", [])
                if "DOLBY_ATMOS" in tags or "SONY_360RA" in tags:
                    score -= 10
                
                # Preference score
                if pref == "explicit" and is_explicit:
                    score += 50
                elif pref == "clean" and not is_explicit:
                    score += 50
                    
                if score > best_score:
                    best_score = score
                    best_alb = alb
                    
            if best_alb:
                deduped.append(best_alb)
                
        return deduped

    try:
        # Use the upstream's direct /artist/?f={id} endpoint
        res = await hifi_client.get_artist_albums(artist_id)
        albums_data = res.get("albums", {}) if isinstance(res, dict) else {}
        items = albums_data.get("items", [])
        if items:
            return preference_deduplicator(items)
    except Exception:
        pass

    # Fallback: search by name and filter
    if not artist_name:
        return []

    s_res = await hifi_client.search_albums(artist_name)
    root = s_res.get("data", s_res) if isinstance(s_res, dict) else {}
    items = []
    if "albums" in root and "items" in root["albums"]:
        items = root["albums"]["items"]
    elif "items" in root:
        items = root["items"]

    matched = []
    for it in items:
        aid = it.get("artist", {}).get("id")
        aname = it.get("artist", {}).get("name")

        match = False
        if not aid and not aname:
            if "artist" not in it:
                it["artist"] = {}
            it["artist"]["name"] = artist_name
            it["artist"]["id"] = artist_id
            match = True
        elif aid and str(aid) == str(artist_id):
            match = True
        elif aname and artist_name and aname.lower() == artist_name.lower():
            match = True

        if match:
            matched.append(it)

    return preference_deduplicator(matched)
