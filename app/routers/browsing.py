"""
Browsing endpoints for navigating the music library.
"""
from fastapi import APIRouter, Depends, Request, Query, Form
import asyncio
import random
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_session
from app.hifi_client import hifi_client
from app.models import Star
from app.responses import SubsonicResponse
from app.routers.common import common_params, extract_track_metadata, fetch_artist_albums, resolve_id

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/rest/getMusicFolders.view")
@router.get("/rest/getMusicFolders")
@router.post("/rest/getMusicFolders.view")
@router.post("/rest/getMusicFolders")
async def get_music_folders(commons: dict = Depends(common_params)):
    return SubsonicResponse.create({
        "musicFolders": {
            "musicFolder": [
                {"id": 1, "name": "Tidal"}
            ]
        }
    }, fmt=commons["f"])


@router.get("/rest/getMusicDirectory.view")
@router.get("/rest/getMusicDirectory")
@router.post("/rest/getMusicDirectory.view")
@router.post("/rest/getMusicDirectory")
async def get_music_directory(
    id: str = Query(None),
    id_form: str = Form(None, alias="id"),
    commons: dict = Depends(common_params)
):
    """
    Returns contents of a directory.
    """
    f = commons["f"]
    real_id = id or id_form
    if not real_id:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=f)
        
    id = real_id # Use merged ID
    
    # Virtual Root
    if id == "1" or id == "root":
        return SubsonicResponse.create({
            "directory": {
                "id": id,
                "name": "Tidal",
                "child": [] 
            }
        }, fmt=f)
    
    try:
        # Artist Folder -> Returns Albums
        if id.startswith("artist-") or id.startswith("ar-"):
            artist_id = resolve_id(id)
            
            # Fetch artist info and albums concurrently
            info_res, albums_data = await asyncio.gather(
                hifi_client.get_artist(artist_id),
                fetch_artist_albums(artist_id)
            )
            artist_info = info_res.get("artist", {}) if isinstance(info_res, dict) else {}
            
            children = []
            for alb in albums_data:
                cover_uuid = alb.get("cover")
                cover_art_id = cover_uuid if cover_uuid else f"al-{alb['id']}"
                
                children.append({
                    "id": f"al-{alb['id']}",
                    "parent": id,
                    "title": alb.get("title"),
                    "artist": alb.get("artist", {}).get("name"),
                    "isDir": True,
                    "coverArt": cover_art_id
                })
            
            return SubsonicResponse.create({
                "directory": {
                    "id": id,
                    "name": "Artist Albums",
                    "child": children
                }
            }, fmt=f)
            
        # Album Folder -> Returns Tracks
        elif id.startswith("album-") or id.startswith("al-"):
            real_id = resolve_id(id)
            data = await hifi_client.get_album(real_id)
            items = data.get("data", {}).get("items", [])
            children = []
            
            album_cover_uuid = data.get("data", {}).get("cover")
            
            for entry in items:
                item = entry.get("item", entry)
                track_meta = extract_track_metadata(item)
                # Override with album-level data
                cover_uuid = item.get("album", {}).get("cover") or album_cover_uuid
                track_meta["coverArt"] = cover_uuid if cover_uuid else f"al-{real_id}"
                track_meta["parent"] = id
                track_meta["album"] = data.get("data", {}).get("title") or track_meta["album"]
                track_meta["albumId"] = f"al-{real_id}"
                children.append(track_meta)

            return SubsonicResponse.create({
                "directory": {
                    "id": id,
                    "name": data.get("data", {}).get("title"),
                    "child": children
                }
            }, fmt=f)
            
        else:
            return SubsonicResponse.error(70, "Folder not found", fmt=f)

    except Exception as e:
        return SubsonicResponse.error(0, str(e), fmt=f)


@router.get("/rest/getArtist.view")
@router.get("/rest/getArtist")
@router.post("/rest/getArtist.view")
@router.post("/rest/getArtist")
async def get_artist(
    id: str = Query(None),
    id_form: str = Form(None, alias="id"),
    commons: dict = Depends(common_params)
):
    f = commons["f"]
    real_id = id or id_form
    if not real_id:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=f)
    id = real_id
    
    try:
        artist_id = resolve_id(id)
    except ValueError:
        return SubsonicResponse.error(70, "Artist not found", fmt=f)

    try:
        # Fetch artist info and albums concurrently
        info_res, albums_items = await asyncio.gather(
            hifi_client.get_artist(artist_id),
            fetch_artist_albums(artist_id)
        )
        artist_info = info_res.get("artist", {}) if isinstance(info_res, dict) else {}
                    
        albums = []
        for alb in albums_items:
            cover_uuid = alb.get("cover")
            cover_art_id = cover_uuid if cover_uuid else f"al-{alb['id']}"
            albums.append({
                "id": f"al-{alb['id']}",
                "name": alb.get("title"),
                "artist": alb.get("artist", {}).get("name"),
                "year": int(alb.get("releaseDate")[:4]) if alb.get("releaseDate") else None,
                "songCount": alb.get("numberOfTracks"),
                "coverArt": cover_art_id,
                "isDir": True
            })

        cover_uuid = artist_info.get("picture")
        cover_art_id = cover_uuid if cover_uuid else f"ar-{artist_id}"

        return SubsonicResponse.create({
            "artist": {
                "id": f"ar-{artist_id}",
                "name": artist_info.get("name"),
                "coverArt": cover_art_id, 
                "albumCount": len(albums),
                "album": albums
            }
        }, fmt=f)

    except Exception as e:
        return SubsonicResponse.error(0, str(e), fmt=f)


@router.get("/rest/getAlbum.view")
@router.get("/rest/getAlbum")
@router.post("/rest/getAlbum.view")
@router.post("/rest/getAlbum")
async def get_album_endpoint(
    id: str = Query(None),
    id_form: str = Form(None, alias="id"),
    commons: dict = Depends(common_params)
):
    f = commons["f"]
    real_id = id or id_form
    if not real_id:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=f)
    
    try:
        album_id = resolve_id(real_id)
    except ValueError:
        return SubsonicResponse.error(70, "Album not found", fmt=f)

    try:
        data = await hifi_client.get_album(album_id)
        d = data.get("data", {}) if data else {}
        
        items = d.get("items", [])
        songs = []
        album_cover_uuid = d.get("cover")
        
        for entry in items:
            item = entry.get("item", entry)
            track_meta = extract_track_metadata(item)
            # Override with album-level data
            cover_uuid = item.get("album", {}).get("cover") or album_cover_uuid
            track_meta["coverArt"] = cover_uuid if cover_uuid else f"al-{album_id}"
            track_meta["parent"] = f"al-{album_id}"
            track_meta["album"] = d.get("title") or track_meta["album"]
            track_meta["albumId"] = f"al-{album_id}"
            track_meta["created"] = "2025-01-01T00:00:00.000Z"
            songs.append(track_meta)

        cover_art_id = album_cover_uuid if album_cover_uuid else f"al-{album_id}"
        
        return SubsonicResponse.create({
            "album": {
                "id": f"al-{album_id}",
                "name": d.get("title"),
                "artist": d.get("artist", {}).get("name"),
                "artistId": f"ar-{d.get('artist', {}).get('id')}",
                "year": int(d.get("releaseDate")[:4]) if d.get("releaseDate") else None,
                "songCount": d.get("numberOfTracks"),
                "duration": sum(s.get("duration", 0) for s in songs),
                "created": "2025-01-01T00:00:00.000Z",
                "genre": "Pop",
                "coverArt": cover_art_id,
                "song": songs
            }
        }, fmt=f)

    except Exception as e:
        return SubsonicResponse.error(0, str(e), fmt=f)


@router.get("/rest/getAlbumInfo2.view")
@router.get("/rest/getAlbumInfo2")
@router.post("/rest/getAlbumInfo2.view")
@router.post("/rest/getAlbumInfo2")
async def get_album_info2(
    request: Request,
    id: str = Query(None),
    id_form: str = Form(None, alias="id"),
    commons: dict = Depends(common_params)
):
    f = commons["f"]
    real_id = id or id_form
    if not real_id:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=f)
        
    try:
        album_id = resolve_id(real_id)
    except ValueError:
        return SubsonicResponse.error(70, "Album not found", fmt=f)

    try:
        data = await hifi_client.get_album(album_id)
        d = data.get("data", {}) if data else {}
        
        if not d:
            return SubsonicResponse.error(70, "Album not found", fmt=f)

        notes = []
        if d.get("releaseDate"):
            notes.append(f"Released: {d['releaseDate']}")
        if d.get("copyright"):
            notes.append(d['copyright'])
        if d.get("upc"):
            notes.append(f"UPC: {d['upc']}")
            
        note_text = " \n".join(notes)

        cover_uuid = d.get("cover")
        if cover_uuid:
            cover_url_base = f"https://resources.tidal.com/images/{cover_uuid.replace('-', '/')}"
            small_url = f"{cover_url_base}/320x320.jpg"
            large_url = f"{cover_url_base}/1280x1280.jpg"
        else:
            local_id = f"album-{album_id}"
            base_url = str(request.base_url).rstrip("/")
            small_url = f"{base_url}/rest/getCoverArt.view?id={local_id}&size=320"
            large_url = f"{base_url}/rest/getCoverArt.view?id={local_id}&size=1280"

        return SubsonicResponse.create({
            "albumInfo": {
                "notes": note_text,
                "musicBrainzId": "",
                "lastFmUrl": "",
                "smallImageUrl": small_url,
                "largeImageUrl": large_url,
                "year": int(d.get("releaseDate")[:4]) if d.get("releaseDate") else None
            }
        }, fmt=f)

    except Exception as e:
        return SubsonicResponse.error(0, str(e), fmt=f)

@router.get("/rest/getArtistInfo.view")
@router.get("/rest/getArtistInfo")
@router.post("/rest/getArtistInfo.view")
@router.post("/rest/getArtistInfo")
@router.get("/rest/getArtistInfo2.view")
@router.get("/rest/getArtistInfo2")
@router.post("/rest/getArtistInfo2.view")
@router.post("/rest/getArtistInfo2")
async def get_artist_info_endpoint(
    id: str = Query(None),
    count: int = Query(20),
    includeNotPresent: bool = Query(False),
    
    id_form: str = Form(None, alias="id"),
    count_form: int = Form(None, alias="count"),
    
    commons: dict = Depends(common_params)
):
    """
    Get artist details and similar artists.
    """
    f = commons["f"]
    
    real_id = id or id_form
    if not real_id:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=f)
    id = real_id
    
    count = count_form if count_form is not None else count
    
    try:
        artist_id = resolve_id(real_id)
    except ValueError:
        return SubsonicResponse.error(70, "Artist not found", fmt=f)
    
    try:
        # Fetch artist data and similar artists in parallel
        artist_res, similar_res = await asyncio.gather(
            hifi_client.get_artist(artist_id),
            hifi_client.get_similar_artists(artist_id),
            return_exceptions=True
        )

        # Process Artist Data
        artist_data = {}
        cover_urls = {}
        if isinstance(artist_res, dict):
            artist_data = artist_res.get("artist", {}) or artist_res.get("data", {})
            
            # Extract cover URLs if available
            picture_uuid = artist_data.get("picture")
            if picture_uuid:
                slug = picture_uuid.replace("-", "/")
                cover_urls = {
                   "small": f"https://resources.tidal.com/images/{slug}/320x320.jpg",
                   "medium": f"https://resources.tidal.com/images/{slug}/640x640.jpg",
                   "large": f"https://resources.tidal.com/images/{slug}/750x750.jpg" 
                }
        
        # Process Similar Artists
        similar_artists = []
        if isinstance(similar_res, dict):
            # API returns { "artists": [ ... ] } or { "data": [ ... ] } depending on endpoint wrapper
            sim_list = similar_res.get("artists", []) or similar_res.get("data", [])
            for sim in sim_list[:count]:
                sid = sim.get("id")
                sname = sim.get("name")
                if sid and sname:
                    
                     # Extract cover for similar artist
                    spic = sim.get("picture")
                    s_cover = None
                    if spic:
                        slug = spic.replace("-", "/")
                        s_cover = f"https://resources.tidal.com/images/{slug}/320x320.jpg"

                    similar_artists.append({
                        "id": f"ar-{sid}",
                        "name": sname,
                        "coverArt": f"ar-{sid}", # Fallback or actual ID
                        "albumCount": 0, # Not provided by similar endpoint
                        "imageUrl": s_cover
                    })

        # Construct Response
        info = {
            "biography": "", # Tidal API doesn't provide bio in standard endpoint
            "musicBrainzId": "",
            "lastFmUrl": f"https://www.last.fm/music/{artist_data.get('name', '').replace(' ', '+')}",
            "smallImageUrl": cover_urls.get("small"),
            "mediumImageUrl": cover_urls.get("medium"),
            "largeImageUrl": cover_urls.get("large"),
            "similarArtist": similar_artists
        }

        return SubsonicResponse.create({
            "artistInfo2": info
        }, fmt=f)

    except Exception as e:
        return SubsonicResponse.error(0, str(e), fmt=f)

@router.get("/rest/getSimilarSongs.view")
@router.get("/rest/getSimilarSongs")
@router.post("/rest/getSimilarSongs.view")
@router.post("/rest/getSimilarSongs")
@router.get("/rest/getSimilarSongs2.view")
@router.get("/rest/getSimilarSongs2")
@router.post("/rest/getSimilarSongs2.view")
@router.post("/rest/getSimilarSongs2")
async def get_similar_songs_endpoint(
    request: Request,
    id: str = Query(None),
    count: int = Query(50),
    id_form: str = Form(None, alias="id"),
    count_form: int = Form(None, alias="count"),
    commons: dict = Depends(common_params)
):
    """
    Returns a random collection of songs from the given artist and similar artists.
    Supports both getSimilarSongs and getSimilarSongs2 parameters.
    """
    f = commons["f"]
    real_id = id or id_form
    if not real_id:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=f)
        
    count_val = count_form if count_form is not None else count
    
    try:
        track_id = resolve_id(real_id)
    except ValueError:
        return SubsonicResponse.error(70, "Track not found", fmt=f)
        
    try:
        data = await hifi_client.get_similar_tracks(track_id)
        d = data.get("data", {}) if data else {}
        items = d.get("items", [])
        
        songs = []
        for entry in items[:count_val]:
            item = entry.get("track", entry)
            if item:
                track_meta = extract_track_metadata(item)
                songs.append(track_meta)
                
        is_v2 = "getSimilarSongs2" in request.url.path
        key = "similarSongs2" if is_v2 else "similarSongs"
        
        return SubsonicResponse.create({
            key: {
                "song": songs
            }
        }, fmt=f)
        
    except Exception as e:
        return SubsonicResponse.error(0, str(e), fmt=f)


@router.get("/rest/getAlbumList.view")
@router.get("/rest/getAlbumList")
@router.post("/rest/getAlbumList.view")
@router.post("/rest/getAlbumList")
@router.get("/rest/getAlbumList2.view")
@router.get("/rest/getAlbumList2")
@router.post("/rest/getAlbumList2.view")
@router.post("/rest/getAlbumList2")
async def get_album_list(
    request: Request,
    type: str = Query("random"),
    size: int = Query(10),
    offset: int = Query(0),
    fromYear: int = Query(None),
    toYear: int = Query(None),
    genre: str = Query(None),
    musicFolderId: Optional[str] = Query(None),
    type_form: str = Form(None, alias="type"),
    size_form: int = Form(None, alias="size"),
    offset_form: int = Form(None, alias="offset"),
    fromYear_form: int = Form(None, alias="fromYear"),
    toYear_form: int = Form(None, alias="toYear"),
    genre_form: str = Form(None, alias="genre"),
    musicFolderId_form: Optional[str] = Form(None, alias="musicFolderId"),
    commons: dict = Depends(common_params),
    session: AsyncSession = Depends(get_session),
):
    """
    Returns a list of albums. Uses starred albums as the data source,
    with sorting/filtering based on the requested type.
    """
    user = commons["user"]
    f = commons["f"]

    final_type = type_form if type_form else type
    final_size = size_form if size_form is not None else size
    final_offset = offset_form if offset_form is not None else offset
    final_from_year = fromYear_form if fromYear_form is not None else fromYear
    final_to_year = toYear_form if toYear_form is not None else toYear

    # Fetch all starred albums for this user
    stmt = select(Star).where(Star.user_id == user.id, Star.item_type == "album")
    result = await session.execute(stmt)
    album_stars = result.scalars().all()

    if not album_stars:
        key = "albumList2" if "AlbumList2" in request.url.path or "albumList2" in request.url.path else "albumList"
        return SubsonicResponse.create({key: {"album": []}}, fmt=f)

    # Fetch metadata for all starred albums concurrently
    async def fetch_album_meta(star: Star):
        try:
            numeric_id = resolve_id(star.item_id)
            data = await hifi_client.get_album(numeric_id)
            d = data.get("data", {}) if data else {}
            if d:
                cover_uuid = d.get("cover")
                return {
                    "id": star.item_id,
                    "name": d.get("title") or star.item_id,
                    "artist": d.get("artist", {}).get("name") or "Unknown",
                    "artistId": f"ar-{d.get('artist', {}).get('id')}",
                    "year": int(d.get("releaseDate")[:4]) if d.get("releaseDate") else None,
                    "genre": "",
                    "songCount": d.get("numberOfTracks"),
                    "duration": d.get("duration") or 0,
                    "coverArt": cover_uuid if cover_uuid else star.item_id,
                    "created": star.created_at.isoformat() + "Z",
                    "starred": star.created_at.isoformat() + "Z",
                    "_starred_at": star.created_at,
                }
        except Exception as e:
            logger.warning("Failed to fetch album metadata for %s: %s", star.item_id, e)
        return None

    results = await asyncio.gather(*[fetch_album_meta(s) for s in album_stars])
    albums = [a for a in results if a is not None]

    # Sort/filter based on type
    if final_type == "random":
        random.shuffle(albums)
    elif final_type == "newest":
        albums.sort(key=lambda a: a.get("_starred_at") or "", reverse=True)
    elif final_type == "starred":
        albums.sort(key=lambda a: a.get("_starred_at") or "", reverse=True)
    elif final_type == "alphabeticalByName":
        albums.sort(key=lambda a: (a.get("name") or "").lower())
    elif final_type == "alphabeticalByArtist":
        albums.sort(key=lambda a: (a.get("artist") or "").lower())
    elif final_type == "byYear" and final_from_year is not None and final_to_year is not None:
        lo, hi = min(final_from_year, final_to_year), max(final_from_year, final_to_year)
        albums = [a for a in albums if a.get("year") and lo <= a["year"] <= hi]
        ascending = final_from_year <= final_to_year
        albums.sort(key=lambda a: a.get("year") or 0, reverse=not ascending)
    # For 'recent', 'frequent', 'highest' — fall through with default (starred) order

    # Strip internal fields before responding
    for a in albums:
        a.pop("_starred_at", None)

    page = albums[final_offset : final_offset + final_size]

    is_v2 = "AlbumList2" in request.url.path or "albumList2" in request.url.path
    key = "albumList2" if is_v2 else "albumList"


    return SubsonicResponse.create({key: {"album": page}}, fmt=f)


@router.get("/rest/getArtists.view")
@router.get("/rest/getArtists")
@router.post("/rest/getArtists.view")
@router.post("/rest/getArtists")
async def get_artists(
    musicFolderId: Optional[str] = Query(None),
    musicFolderId_form: Optional[str] = Form(None, alias="musicFolderId"),
    commons: dict = Depends(common_params),
    session: AsyncSession = Depends(get_session)
):
    """
    Returns a list of all artists. Uses starred artists as the data source,
    grouped by the first letter of the artist's name.
    """
    user = commons["user"]
    f = commons["f"]

    # Fetch all starred artists for this user
    stmt = select(Star).where(Star.user_id == user.id, Star.item_type == "artist")
    result = await session.execute(stmt)
    artist_stars = result.scalars().all()

    if not artist_stars:
        return SubsonicResponse.create({
            "artists": {
                "ignoredArticles": "The El La Los Las Le Les",
                "index": []
            }
        }, fmt=f)

    # Fetch metadata for all starred artists concurrently
    async def fetch_artist_meta(star: Star):
        try:
            numeric_id = resolve_id(star.item_id)
            data = await hifi_client.get_artist(numeric_id)
            artist_data = data.get("artist", {}) if isinstance(data, dict) else {}
            if artist_data:
                cover_uuid = artist_data.get("picture")
                return {
                    "id": star.item_id,
                    "name": artist_data.get("name") or "Unknown Artist",
                    "coverArt": cover_uuid if cover_uuid else star.item_id,
                    "albumCount": 0,
                    "starred": star.created_at.isoformat() + "Z",
                    "_sort_name": (artist_data.get("name") or "Unknown Format").upper()
                }
        except Exception as e:
            logger.warning("Failed to fetch artist metadata for %s: %s", star.item_id, e)
        return None

    results = await asyncio.gather(*[fetch_artist_meta(s) for s in artist_stars])
    artists = [a for a in results if a is not None]

    # Subsonic groups artists alphabetically by the first character of their name
    indices = {}
    for artist in artists:
        sort_name = artist.pop("_sort_name", "")
        # Determine the group letter. Use '#' for non-alphabetical
        first_char = sort_name[0] if sort_name else "#"
        if not first_char.isalpha():
            first_char = "#"
        elif sort_name.startswith("THE "):
            first_char = sort_name[4] if len(sort_name) > 4 else "T"
            
        group = first_char.upper()
        if group not in indices:
            indices[group] = {"name": group, "artist": []}
        indices[group]["artist"].append(artist)
        
    # Sort groups alphabetically, ensuring '#' is first or properly sorted
    sorted_groups = []
    for group_name in sorted(indices.keys()):
        # Sort artists inside the group
        indices[group_name]["artist"].sort(key=lambda a: a.get("name", "").lower())
        sorted_groups.append(indices[group_name])

    return SubsonicResponse.create({
        "artists": {
            "ignoredArticles": "The El La Los Las Le Les",
            "index": sorted_groups
        }
    }, fmt=f)
