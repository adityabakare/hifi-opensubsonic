"""
User data endpoints - starred items, playlists, scrobbles.
These endpoints persist data per-user in the database.
"""
from fastapi import APIRouter, Query, Depends, Form, BackgroundTasks
from sqlalchemy.future import select
from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Optional, List

from app.config import settings
from app.database import get_session
from app.models import Star, Playlist, PlaylistEntry
from app.responses import SubsonicResponse
from app.routers.common import common_params, extract_playlist_entry_data
from app.hifi_client import hifi_client
from app.lastfm_client import lastfm_client
import time as pytime

router = APIRouter()


# --- Star/Unstar ---

@router.get("/rest/star.view")
@router.get("/rest/star")
@router.post("/rest/star.view")
@router.post("/rest/star")
async def star(
    id: Optional[str] = Query(None),
    albumId: Optional[str] = Query(None),
    artistId: Optional[str] = Query(None),
    # Form vars
    id_form: Optional[str] = Form(None, alias="id"),
    albumId_form: Optional[str] = Form(None, alias="albumId"),
    artistId_form: Optional[str] = Form(None, alias="artistId"),
    commons: dict = Depends(common_params),
    session: AsyncSession = Depends(get_session)
):
    """Star a song, album, or artist."""
    user = commons["user"]
    f = commons["f"]
    
    # Merge params
    final_id = id or id_form
    final_albumId = albumId or albumId_form
    final_artistId = artistId or artistId_form
    
    items_to_star = []
    if final_id:
        items_to_star.append((final_id, "song"))
    if final_albumId:
        items_to_star.append((final_albumId, "album"))
    if final_artistId:
        items_to_star.append((final_artistId, "artist"))
    
    for item_id, item_type in items_to_star:
        # Check if already starred
        stmt = select(Star).where(
            Star.user_id == user.id,
            Star.item_id == item_id
        )
        result = await session.execute(stmt)
        existing = result.scalars().first()
        
        if not existing:
            star_entry = Star(
                user_id=user.id,
                item_id=item_id,
                item_type=item_type
            )
            session.add(star_entry)
    
    await session.commit()
    
    return SubsonicResponse.create({
    }, fmt=f)


@router.get("/rest/unstar.view")
@router.get("/rest/unstar")
@router.post("/rest/unstar.view")
@router.post("/rest/unstar")
async def unstar(
    id: Optional[str] = Query(None),
    albumId: Optional[str] = Query(None),
    artistId: Optional[str] = Query(None),
    # Form vars
    id_form: Optional[str] = Form(None, alias="id"),
    albumId_form: Optional[str] = Form(None, alias="albumId"),
    artistId_form: Optional[str] = Form(None, alias="artistId"),
    commons: dict = Depends(common_params),
    session: AsyncSession = Depends(get_session)
):
    """Unstar a song, album, or artist."""
    user = commons["user"]
    f = commons["f"]
    
    # Merge params
    final_id = id or id_form
    final_albumId = albumId or albumId_form
    final_artistId = artistId or artistId_form
    
    items_to_unstar = []
    if final_id:
        items_to_unstar.append(final_id)
    if final_albumId:
        items_to_unstar.append(final_albumId)
    if final_artistId:
        items_to_unstar.append(final_artistId)
    
    for item_id in items_to_unstar:
        stmt = select(Star).where(
            Star.user_id == user.id,
            Star.item_id == item_id
        )
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if existing:
            await session.delete(existing)
    
    await session.commit()
    
    return SubsonicResponse.create({
    }, fmt=f)


@router.get("/rest/getStarred.view")
@router.get("/rest/getStarred")
@router.post("/rest/getStarred.view")
@router.post("/rest/getStarred")
@router.get("/rest/getStarred2.view")
@router.get("/rest/getStarred2")
@router.post("/rest/getStarred2.view")
@router.post("/rest/getStarred2")
async def get_starred(
    commons: dict = Depends(common_params),
    session: AsyncSession = Depends(get_session)
):
    """Get all starred items for the current user."""
    user = commons["user"]
    f = commons["f"]
    
    stmt = select(Star).where(Star.user_id == user.id)
    result = await session.execute(stmt)
    stars = result.scalars().all()
    
    artists = []
    albums = []
    songs = []
    
    for star in stars:
        item = {
            "id": star.item_id,
            "starred": star.created_at.isoformat() + "Z"
        }
        if star.item_type == "artist":
            item["name"] = star.item_id  # Would need metadata lookup for full name
            artists.append(item)
        elif star.item_type == "album":
            item["name"] = star.item_id
            item["artist"] = "Unknown"
            albums.append(item)
        else:  # song
            item["title"] = star.item_id
            item["artist"] = "Unknown"
            item["album"] = "Unknown"
            songs.append(item)
    
    return SubsonicResponse.create({
        "starred2": {
            "artist": artists,
            "album": albums,
            "song": songs
        }
    }, fmt=f)


# --- Playlists ---

@router.get("/rest/getPlaylists.view")
@router.get("/rest/getPlaylists")
@router.post("/rest/getPlaylists.view")
@router.post("/rest/getPlaylists")
async def get_playlists(
    commons: dict = Depends(common_params),
    session: AsyncSession = Depends(get_session)
):
    """Get all playlists for the current user."""
    user = commons["user"]
    f = commons["f"]
    
    # Single query: join playlists with aggregated entry stats
    stmt = (
        select(
            Playlist,
            func.count(PlaylistEntry.id).label("song_count"),
            func.coalesce(func.sum(PlaylistEntry.duration), 0).label("total_duration")
        )
        .outerjoin(PlaylistEntry, PlaylistEntry.playlist_id == Playlist.id)
        .where(Playlist.user_id == user.id)
        .group_by(Playlist.id)
    )
    result = await session.execute(stmt)
    rows = result.all()
    
    playlist_list = []
    for pl, song_count, total_duration in rows:
        playlist_list.append({
            "id": str(pl.id),
            "name": pl.name,
            "comment": pl.comment or "",
            "owner": user.username,
            "public": pl.public,
            "songCount": song_count,
            "duration": total_duration,
            "created": pl.created_at.isoformat() + "Z",
            "changed": pl.changed_at.isoformat() + "Z"
        })
    
    return SubsonicResponse.create({
        "playlists": {"playlist": playlist_list}
    }, fmt=f)


@router.get("/rest/getPlaylist.view")
@router.get("/rest/getPlaylist")
@router.post("/rest/getPlaylist.view")
@router.post("/rest/getPlaylist")
async def get_playlist(
    id: str = Query(None),
    id_form: str = Form(None, alias="id"),
    commons: dict = Depends(common_params),
    session: AsyncSession = Depends(get_session)
):
    """Get a specific playlist with its entries."""
    user = commons["user"]
    f = commons["f"]
    
    real_id = id or id_form
    if not real_id:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=f)
    id = real_id
    
    try:
        playlist_id_int = int(id)
    except ValueError:
        return SubsonicResponse.error(70, "Playlist not found", fmt=f)
        
    stmt = select(Playlist).where(Playlist.id == playlist_id_int)
    result = await session.execute(stmt)
    pl = result.scalars().first()
    
    if not pl:
        return SubsonicResponse.error(70, "Playlist not found", fmt=f)
    
    # Get entries
    entries_stmt = select(PlaylistEntry).where(
        PlaylistEntry.playlist_id == pl.id
    ).order_by(PlaylistEntry.position)
    entries_result = await session.execute(entries_stmt)
    entries = entries_result.scalars().all()
    
    songs = []
    total_duration = 0
    
    for entry in entries:
        duration = entry.duration or 0
        total_duration += duration
        
        songs.append({
            "id": entry.track_id,
            "parent": entry.album_id or f"album-{entry.track_id}",
            "title": entry.title or entry.track_id,
            "artist": entry.artist or "Unknown Artist",
            "artistId": entry.artist_id or "artist-0",
            "album": entry.album or "Unknown Album",
            "albumId": entry.album_id or "album-0",
            "coverArt": entry.cover_art or entry.album_id or entry.track_id,
            "duration": duration,
            "isDir": entry.is_dir or False,
            "isVideo": entry.is_video or False,
            "type": "music",
            "track": entry.track_number,
            "discNumber": entry.disc_number,
            "year": entry.year,
            "bitRate": entry.bit_rate or 1411,
            "bitDepth": entry.bit_depth or 16,
            "samplingRate": entry.sampling_rate or 44100,
            "suffix": entry.suffix or "flac",
            "contentType": entry.content_type or "audio/flac",
            "size": int(duration * (entry.bit_rate or 1411) * 125), # Estimate size (kbps -> bytes)
            "path": f"music/{entry.track_id}.{entry.suffix or 'flac'}"
        })
    
    return SubsonicResponse.create({
        "playlist": {
            "id": str(pl.id),
            "name": pl.name,
            "comment": pl.comment or "",
            "owner": user.username,
            "public": pl.public,
            "songCount": len(songs),
            "duration": total_duration,
            "created": pl.created_at.isoformat() + "Z",
            "changed": pl.changed_at.isoformat() + "Z",
            "entry": songs
        }
    }, fmt=f)


@router.get("/rest/createPlaylist.view")
@router.get("/rest/createPlaylist")
@router.post("/rest/createPlaylist.view")
@router.post("/rest/createPlaylist")
async def create_playlist(
    name: str = Query(None),
    playlistId: Optional[str] = Query(None),
    songId: Optional[List[str]] = Query(None),
    # Form vars
    name_form: str = Form(None, alias="name"),
    playlistId_form: Optional[str] = Form(None, alias="playlistId"),
    songId_form: Optional[List[str]] = Form(None, alias="songId"),
    
    commons: dict = Depends(common_params),
    session: AsyncSession = Depends(get_session)
):
    """Create or update a playlist."""
    user = commons["user"]
    f = commons["f"]
    
    name = name or name_form
    playlistId = playlistId or playlistId_form
    songId = songId if songId else songId_form
    
    if playlistId:
        # Update existing playlist
        try:
            playlist_id_int = int(playlistId)
        except ValueError:
            return SubsonicResponse.error(70, "Playlist not found", fmt=f)
            
        stmt = select(Playlist).where(Playlist.id == playlist_id_int)
        result = await session.execute(stmt)
        pl = result.scalars().first()
        
        if not pl or pl.user_id != user.id:
            return SubsonicResponse.error(70, "Playlist not found", fmt=f)
        
        if name:
            pl.name = name
        pl.changed_at = datetime.now(timezone.utc)
    else:
        # Create new playlist
        if not name:
            name = "New Playlist"
        pl = Playlist(
            user_id=user.id,
            name=name
        )
        session.add(pl)
        await session.flush()  # Get the ID
    # Add songs if provided
    if songId:
        
        # Get current max position
        pos_stmt = select(PlaylistEntry).where(PlaylistEntry.playlist_id == pl.id)
        pos_result = await session.execute(pos_stmt)
        existing = pos_result.scalars().all()
        max_pos = max([e.position for e in existing], default=-1)
        
        for i, track_id in enumerate(songId):
            # Normalize track_id to "track-123" format
            numeric_id = track_id.split("-")[1] if track_id.startswith("track-") else track_id
            
            # Fetch track metadata using shared function
            entry_data = {
                "track_id": track_id if track_id.startswith("track-") else f"track-{track_id}",
                "title": f"Track {numeric_id}",
            }

            try:
                data = await hifi_client.get_track_info(int(numeric_id))
                if data and "data" in data:
                    entry_data = extract_playlist_entry_data(data["data"])
            except Exception:
                pass  # Use defaults
            
            entry = PlaylistEntry(
                playlist_id=pl.id,
                position=max_pos + 1 + i,
                **entry_data
            )
            session.add(entry)
    
    await session.commit()
    
    return SubsonicResponse.create({
        "playlist": {
            "id": str(pl.id),
            "name": pl.name
        }
    }, fmt=f)


@router.get("/rest/deletePlaylist.view")
@router.get("/rest/deletePlaylist")
@router.post("/rest/deletePlaylist.view")
@router.post("/rest/deletePlaylist")
async def delete_playlist(
    id: str = Query(None),
    id_form: str = Form(None, alias="id"),
    commons: dict = Depends(common_params),
    session: AsyncSession = Depends(get_session)
):
    """Delete a playlist."""
    user = commons["user"]
    f = commons["f"]
    real_id = id or id_form
    if not real_id:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=f)
    id = real_id
    
    try:
        playlist_id_int = int(id)
    except ValueError:
        return SubsonicResponse.error(70, "Playlist not found", fmt=f)
        
    stmt = select(Playlist).where(Playlist.id == playlist_id_int)
    result = await session.execute(stmt)
    pl = result.scalars().first()
    
    if not pl or pl.user_id != user.id:
        return SubsonicResponse.error(70, "Playlist not found", fmt=f)
    
    # Delete entries first using bulk delete
    # We need to import delete at top level or use it here
    await session.execute(delete(PlaylistEntry).where(PlaylistEntry.playlist_id == pl.id))
    await session.flush()
    
    await session.delete(pl)
    await session.commit()
    
    return SubsonicResponse.create({
    }, fmt=f)


@router.get("/rest/updatePlaylist.view")
@router.get("/rest/updatePlaylist")
@router.post("/rest/updatePlaylist.view")
@router.post("/rest/updatePlaylist")
async def update_playlist(
    playlistId: str = Query(None),
    name: Optional[str] = Query(None),
    comment: Optional[str] = Query(None),
    public: Optional[bool] = Query(None),
    songIdToAdd: Optional[List[str]] = Query(None),
    songIndexToRemove: Optional[List[int]] = Query(None),
    # Form vars
    playlistId_form: str = Form(None, alias="playlistId"),
    name_form: Optional[str] = Form(None, alias="name"),
    comment_form: Optional[str] = Form(None, alias="comment"),
    public_form: Optional[bool] = Form(None, alias="public"),
    songIdToAdd_form: Optional[List[str]] = Form(None, alias="songIdToAdd"),
    songIndexToRemove_form: Optional[List[int]] = Form(None, alias="songIndexToRemove"),
    
    commons: dict = Depends(common_params),
    session: AsyncSession = Depends(get_session)
):
    """Update a playlist's metadata and entries."""
    user = commons["user"]
    f = commons["f"]
    
    real_pid = playlistId or playlistId_form
    if not real_pid:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=f)
    playlistId = real_pid
    
    name = name if name is not None else name_form
    comment = comment if comment is not None else comment_form
    public = public if public is not None else public_form
    songIdToAdd = songIdToAdd if songIdToAdd else songIdToAdd_form
    songIndexToRemove = songIndexToRemove if songIndexToRemove else songIndexToRemove_form
    
    try:
        playlist_id_int = int(playlistId)
    except ValueError:
        return SubsonicResponse.error(70, "Playlist not found", fmt=f)
        
    stmt = select(Playlist).where(Playlist.id == playlist_id_int)
    result = await session.execute(stmt)
    pl = result.scalars().first()
    
    if not pl or pl.user_id != user.id:
        return SubsonicResponse.error(70, "Playlist not found", fmt=f)
    
    # Update metadata
    if name is not None:
        pl.name = name
    if comment is not None:
        pl.comment = comment
    if public is not None:
        pl.public = public
    pl.changed_at = datetime.now(timezone.utc)
    
    # Remove songs by index
    if songIndexToRemove:
        entries_stmt = select(PlaylistEntry).where(
            PlaylistEntry.playlist_id == pl.id
        ).order_by(PlaylistEntry.position)
        entries_result = await session.execute(entries_stmt)
        entries = list(entries_result.scalars().all())
        
        for idx in sorted(songIndexToRemove, reverse=True):
            if 0 <= idx < len(entries):
                await session.delete(entries[idx])
    
    # Add songs
    if songIdToAdd:
        pos_stmt = select(PlaylistEntry).where(PlaylistEntry.playlist_id == pl.id)
        pos_result = await session.execute(pos_stmt)
        existing = pos_result.scalars().all()
        max_pos = max([e.position for e in existing], default=-1)
        
        for i, track_id in enumerate(songIdToAdd):
            # Normalize track_id to "track-123" format
            numeric_id = track_id.split("-")[1] if track_id.startswith("track-") else track_id
            
            # Fetch track metadata using shared function
            entry_data = {
                "track_id": track_id if track_id.startswith("track-") else f"track-{track_id}",
                "title": f"Track {numeric_id}",
            }

            try:
                data = await hifi_client.get_track_info(int(numeric_id))
                if data and "data" in data:
                    entry_data = extract_playlist_entry_data(data["data"])
            except Exception:
                pass  # Use defaults
            
            entry = PlaylistEntry(
                playlist_id=pl.id,
                position=max_pos + 1 + i,
                **entry_data
            )
            session.add(entry)
    
    await session.commit()
    
    return SubsonicResponse.create({
    }, fmt=f)


# --- Scrobble ---

@router.get("/rest/scrobble.view")
@router.get("/rest/scrobble")
@router.post("/rest/scrobble.view")
@router.post("/rest/scrobble")
async def scrobble(
    background_tasks: BackgroundTasks,
    id: str = Query(None),
    time: Optional[int] = Query(None),
    submission: bool = Query(True),
    # Form vars
    id_form: str = Form(None, alias="id"),
    time_form: Optional[int] = Form(None, alias="time"),
    submission_form: Optional[bool] = Form(None, alias="submission"),
    
    commons: dict = Depends(common_params),
    session: AsyncSession = Depends(get_session)
):
    """Record a play for scrobbling."""
    user = commons["user"]
    f = commons["f"]
    
    id = id or id_form
    if not id:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=f)
    
    time_val = time if time is not None else time_form
    submission_val = submission_form if (submission_form is not None) else submission
    
    if submission_val and user.lastfm_session_key:
        track_id = id.split("-")[1] if id.startswith("track-") else id
        try:
            # Fetch track metadata to scrobble
            data = await hifi_client.get_track_info(int(track_id))
            if data and "data" in data:
                track = data["data"]
                artist = track.get("artist", {}).get("name")
                title = track.get("title")
                album = track.get("album", {}).get("title")
                if artist and title:
                    timestamp = int(time_val / 1000) if time_val else int(pytime.time())
                    
                    background_tasks.add_task(
                        lastfm_client.scrobble_track,
                        session_key=user.lastfm_session_key,
                        artist=artist,
                        track=title,
                        timestamp=timestamp,
                        album=album
                    )
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to scrobble to Last.fm: {e}")
            
    return SubsonicResponse.create({
    }, fmt=f)


# --- Rating (simple implementation) ---

@router.get("/rest/setRating.view")
@router.get("/rest/setRating")
@router.post("/rest/setRating.view")
@router.post("/rest/setRating")
async def set_rating(
    id: str = Query(None),
    rating: int = Query(0),
    # Form vars
    id_form: str = Form(None, alias="id"),
    rating_form: int = Form(None, alias="rating"),

    commons: dict = Depends(common_params)
):
    """Set rating for an item. Currently stubbed (no persistence)."""
    # TODO: Add Rating table if needed
    id = id or id_form
    if not id:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=commons["f"])
    
    rating = rating_form if rating_form is not None else rating
    return SubsonicResponse.create({
    }, fmt=commons["f"])
