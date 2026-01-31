"""
Common utilities shared across all Subsonic router modules.
"""
from fastapi import Query, Depends
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.hifi_client import hifi_client
from app.responses import SubsonicResponse, SubsonicException
from app.database import get_session
from app.auth import authenticate_user


async def common_params(
    u: str = Query(None),  # Username
    p: str = Query(None),  # Password
    t: str = Query(None),  # Token
    s: str = Query(None),  # Salt
    v: str = Query(None),  # Version
    c: str = Query(None),  # Client
    f: str = Query("json"),  # Format
    session: AsyncSession = Depends(get_session),
):
    """
    Common authentication dependency for all Subsonic endpoints.
    """
    fmt = f
    
    user = None
    if u and p:
        # Handle 'enc:' hex-encoded passwords
        password = p
        if p.startswith("enc:"):
            try:
                hex_str = p[4:]
                password = bytes.fromhex(hex_str).decode("utf-8")
            except Exception:
                pass  # Fallback to raw password if decode fails
        
        user = await authenticate_user(session, u, password)

    if not user:
        if not u:
            raise SubsonicException(code=10, message="Required parameter is missing.", fmt=fmt)
        else:
            raise SubsonicException(code=40, message="Wrong username or password", fmt=fmt)
    
    return {"f": fmt, "v": v, "user": user}


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
        "replayGain": track.get("trackReplayGain") or track.get("replayGain"),
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
