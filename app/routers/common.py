"""
Common utilities shared across all Subsonic router modules.
"""
import logging
from fastapi import Query, Depends, Form
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.hifi_client import hifi_client
from app.responses import SubsonicResponse, SubsonicException
from app.database import get_session
from app.auth import authenticate_user

logger = logging.getLogger(__name__)


async def fetch_track_info_safe(numeric_id: int):
    """Fetch track info from upstream, returning None on failure."""
    try:
        return await hifi_client.get_track_full(numeric_id)
    except Exception as e:
        logger.warning("Failed to fetch track info for %s: %s", numeric_id, e)
        return None


def resolve_id(id_string: str) -> int:
    """
    Standardize parsing of OpenSubsonic IDs into raw upstream numeric IDs.
    Handles plain numbers (123) and Subsonic client prefixes/suffixes (ar-artist-123_0, al-album-456_0).
    
    Raises ValueError if the ID cannot be parsed to an integer.
    """
    if not id_string:
        raise ValueError("ID cannot be empty")
        
    s = str(id_string)
    
    # Strip client prefixes (ar-, al-, etc.)
    while s.startswith("ar-") or s.startswith("al-") or s.startswith("tr-"):
        s = s[3:]
    
    # Strip _0 suffix from clients
    if s.endswith("_0"):
        s = s[:-2]
        
    return int(s)


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
            except (ValueError, UnicodeDecodeError) as e:
                logger.debug("Failed to decode enc: password, using raw value: %s", e)
        
        user = await authenticate_user(session, final_u, password=password)

    elif final_u and final_t and final_s:
        # User provided token auth (md5(password + salt))
        user = await authenticate_user(session, final_u, token=final_t, salt=final_s)

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
    cover_art_id = cover_uuid if cover_uuid else f"al-{track.get('album', {}).get('id')}"
    
    # Extract year and created timestamp from streamStartDate or releaseDate
    date_source = track.get("streamStartDate") or track.get("releaseDate")
    year = None
    if date_source:
        try:
            year = int(date_source[:4])
        except (ValueError, TypeError) as e:
            logger.debug("Failed to parse year from date: %s", e)

    # streamStartDate is already full ISO 8601; releaseDate is date-only
    created = date_source or "2025-01-01"
    if "T" not in created:
        created += "T00:00:00Z"

    return {
        "id": f"tr-{track.get('id')}",
        "title": track.get("title") or "Unknown Title",
        "artist": track.get("artist", {}).get("name") or "Unknown Artist",
        "artistId": f"ar-{track.get('artist', {}).get('id')}",
        "album": track.get("album", {}).get("title") or "Unknown Album",
        "albumId": f"al-{track.get('album', {}).get('id')}",
        "coverArt": cover_art_id,
        "duration": track.get("duration") or 0,
        "track": track.get("trackNumber"),
        "discNumber": track.get("volumeNumber"),
        "year": year,
        "created": created,
        "replayGain": {
            "trackGain": track.get("trackReplayGain", track.get("replayGain")),
            "albumGain": track.get("albumReplayGain"),
            "trackPeak": track.get("trackPeakAmplitude", track.get("peak")),
            "albumPeak": track.get("albumPeakAmplitude"),
            "baseGain": 0,
        },
        "bpm": track.get("bpm") or 0,
        "parent": f"al-{track.get('album', {}).get('id')}",
        "isDir": False,
        "isVideo": False,
        "type": "music",
        "mediaType": "song",
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
    base = extract_track_metadata(track)
    
    return {
        "track_id": base["id"],
        "title": base["title"],
        "artist": base["artist"],
        "artist_id": base["artistId"],
        "album": base["album"],
        "album_id": base["albumId"],
        "cover_art": base["coverArt"],
        "duration": base["duration"],
        "track_number": base["track"],
        "disc_number": base["discNumber"],
        "year": base["year"],
        "bit_rate": base.get("bitRate", 1411),
        "bit_depth": base.get("bitDepth", 16),
        "sampling_rate": base.get("samplingRate", 44100),
        "suffix": base.get("suffix", "flac"),
        "content_type": base.get("contentType", "audio/flac"),
        "bpm": base.get("bpm"),
        
        # Gain properties
        "track_gain": base.get("replayGain", {}).get("trackGain"),
        "album_gain": base.get("replayGain", {}).get("albumGain"),
        "track_peak": base.get("replayGain", {}).get("trackPeak"),
        "album_peak": base.get("replayGain", {}).get("albumPeak"),
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
    except Exception as e:
        logger.warning("Failed to fetch albums for artist %s, falling back to search: %s", artist_id, e)

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


async def add_tracks_to_playlist(session, pl, track_ids: list[str]) -> None:
    """
    Fetch metadata in parallel for a list of track IDs and append them as PlaylistEntry objects
    to the given playlist.
    """
    if not track_ids:
        return
        
    import asyncio
    from sqlalchemy.future import select
    from app.models import PlaylistEntry
    
    # Get current max position
    pos_stmt = select(PlaylistEntry).where(PlaylistEntry.playlist_id == pl.id)
    pos_result = await session.execute(pos_stmt)
    existing = pos_result.scalars().all()
    max_pos = max([e.position for e in existing], default=-1)
    
    # Normalize track IDs and fetch all metadata in parallel
    numeric_ids = []
    for track_id in track_ids:
        try:
            numeric_ids.append((track_id, resolve_id(track_id)))
        except ValueError:
            # If a track ID is completely invalid, we skip it
            # To be more robust, we might just use the raw track_id string
            numeric_ids.append((track_id, track_id))
    
    results = await asyncio.gather(*[fetch_track_info_safe(int(nid)) for _, nid in numeric_ids])
    
    for i, ((track_id, numeric_id), data) in enumerate(zip(numeric_ids, results)):
        entry_data = {
            "track_id": track_id if track_id.startswith("tr-") else f"tr-{track_id}",
            "title": f"Track {numeric_id}",
        }
        if data and "data" in data:
            entry_data = extract_playlist_entry_data(data["data"])
        
        entry = PlaylistEntry(
            playlist_id=pl.id,
            position=max_pos + 1 + i,
            **entry_data
        )
        session.add(entry)
