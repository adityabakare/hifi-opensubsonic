"""
Browsing endpoints for navigating the music library.
"""
from fastapi import APIRouter, Depends, Request, Query, Form
import asyncio

from app.config import settings
from app.hifi_client import hifi_client
from app.responses import SubsonicResponse
from app.routers.common import common_params, extract_track_metadata, fetch_artist_albums, resolve_id

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
