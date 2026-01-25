from fastapi import APIRouter, Query, Depends, Request
from fastapi.responses import RedirectResponse, Response
from typing import Optional
import asyncio
import base64
import json
import re
import httpx

from app.config import settings
from app.hifi_client import hifi_client
from app.responses import SubsonicResponse

router = APIRouter()

async def common_params(
    u: str = Query(None), # Username
    p: str = Query(None), # Password
    t: str = Query(None), # Token
    s: str = Query(None), # Salt
    v: str = Query(None), # Version
    c: str = Query(None), # Client
    f: str = Query("json"), # Format
):
    return {"f": f, "v": v}

def get_track_format(item: dict) -> dict:
    """
    Derive Subsonic format metadata from Tidal item.
    """
    quality = item.get("audioQuality", "LOSSLESS") # Default to LOSSLESS if missing
    
    # Try to calculate exact bitrate if deep metadata is available
    bit_depth = item.get("bitDepth")
    sample_rate = item.get("sampleRate")
    exact_bitrate = None
    
    if bit_depth and sample_rate:
        # Calculate raw PCM bitrate: depth * rate * 2 channels (approx)
        # / 1000 for kbps
        exact_bitrate = int((bit_depth * sample_rate * 2) / 1000)

    # Tidal Qualities:
    # HI_RES_LOSSLESS -> FLAC (Hi-Res)
    # LOSSLESS -> FLAC (CD)
    # HIGH -> AAC 320 (MP4)
    # LOW -> AAC 96 (MP4)
    
    if quality in ["HI_RES_LOSSLESS", "LOSSLESS"]:
        return {
            "suffix": "flac",
            "contentType": "audio/flac",
            "bitRate": exact_bitrate if exact_bitrate else 1411,
            "bitDepth": bit_depth if bit_depth else 16,
            "samplingRate": sample_rate if sample_rate else 44100
        }
    elif quality == "HIGH":
        return {
            "suffix": "m4a",
            "contentType": "audio/mp4",
            "bitRate": exact_bitrate if exact_bitrate else 320,
            # AAC is technically 16-bit equivalent mostly, simplified
        }
    else:
        # LOW or unknown
        return {
            "suffix": "m4a",
            "contentType": "audio/mp4",
            "bitRate": exact_bitrate if exact_bitrate else 96,
        }

@router.get("/rest/getMusicFolders.view")
@router.get("/rest/getMusicFolders")
async def get_music_folders(commons: dict = Depends(common_params)):
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "musicFolders": {
            "musicFolder": [
                {"id": 1, "name": "Tidal"}
            ]
        }
    }, fmt=commons["f"])

@router.get("/rest/getMusicDirectory.view")
@router.get("/rest/getMusicDirectory")
async def get_music_directory(
    id: str,
    commons: dict = Depends(common_params)
):
    """
    Returns contents of a directory.
    """
    f = commons["f"]
    
    # Virtual Root
    if id == "1" or id == "root":
        return SubsonicResponse.create({
            "status": "ok",
            "version": settings.API_VERSION,
            "directory": {
                "id": id,
                "name": "Tidal",
                "child": [] 
            }
        }, fmt=f)
    
    try:
        # Artist Folder -> Returns Albums
        if id.startswith("artist-"):
            real_id = int(id.split("-")[1])
            data = await hifi_client.get_artist_albums(real_id)
            children = []
            albums_data = data.get("albums", {}).get("items", [])
            for alb in albums_data:
                # Prefer UUID for cover
                cover_uuid = alb.get("cover")
                cover_art_id = cover_uuid if cover_uuid else f"album-{alb['id']}"
                
                children.append({
                    "id": f"album-{alb['id']}",
                    "parent": id,
                    "title": alb.get("title"),
                    "artist": alb.get("artist", {}).get("name"),
                    "isDir": True,
                    "coverArt": cover_art_id
                })
            
            return SubsonicResponse.create({
                "status": "ok",
                "version": settings.API_VERSION,
                "directory": {
                    "id": id,
                    "name": "Artist Albums",
                    "child": children
                }
            }, fmt=f)
            
        # Album Folder -> Returns Tracks
        elif id.startswith("album-"):
            real_id = int(id.split("-")[1])
            data = await hifi_client.get_album(real_id)
            items = data.get("data", {}).get("items", [])
            children = []
            
            # Album global cover
            album_cover_uuid = data.get("data", {}).get("cover")
            
            for item in items:
                # Use track specific cover or album cover
                cover_uuid = item.get("album", {}).get("cover") or album_cover_uuid
                cover_art_id = cover_uuid if cover_uuid else f"album-{real_id}"

                fmt_info = get_track_format(item)
                fmt_info = get_track_format(item)
                children.append({
                    "id": f"track-{item['id']}",
                    "parent": id,
                    "title": item.get("title"),
                    "artist": item.get("artist", {}).get("name"),
                    "artistId": f"artist-{item.get('artist', {}).get('id')}",
                    "album": data.get("data", {}).get("title"),
                    "albumId": f"album-{real_id}",
                    "isDir": False,
                    "duration": item.get("duration"),
                    "coverArt": cover_art_id,
                    "track": item.get("trackNumber"),
                    "discNumber": item.get("volumeNumber"),
                    "replayGain": item.get("replayGain"),
                    "year": int(item.get("streamStartDate")[:4]) if item.get("streamStartDate") else None,
                    **fmt_info
                })

            return SubsonicResponse.create({
                "status": "ok",
                "version": settings.API_VERSION,
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


@router.get("/rest/search3.view")
@router.get("/rest/search3")
async def search3(
    query: str,
    songCount: int = 20,
    albumCount: int = 20,
    artistCount: int = 20,
    commons: dict = Depends(common_params)
):
    f = commons["f"]
    
    try:
        t_res, a_res, al_res = await asyncio.gather(
            hifi_client.search_tracks(query),
            hifi_client.search_artists(query),
            hifi_client.search_albums(query),
            return_exceptions=True
        )
        
        songs = []
        if isinstance(t_res, dict):
            # Unwrap 'data' if present at top level (some instances wrapper)
            root = t_res.get("data", t_res)
            # Flattened fallback or nested?
            # Standard hifi-api: root['tracks']['items']
            # Fallback (raw list): root['items']
            items = root.get("tracks", {}).get("items", [])
            if not items:
                items = root.get("items", []) # If direct list

            for it in items:
                cover_uuid = it.get("album", {}).get("cover")
                cover_art_id = cover_uuid if cover_uuid else f"album-{it.get('album', {}).get('id')}"

                fmt_info = get_track_format(it)
                songs.append({
                    "id": f"track-{it['id']}",
                    "title": it.get("title"),
                    "artist": it.get("artist", {}).get("name"),
                    "artistId": f"artist-{it.get('artist', {}).get('id')}",
                    "album": it.get("album", {}).get("title"),
                    "albumId": f"album-{it.get('album', {}).get('id')}",
                    "coverArt": cover_art_id,
                    "duration": it.get("duration"),
                    "isDir": False,
                    "track": it.get("trackNumber"),
                    "discNumber": it.get("volumeNumber"),
                    "replayGain": it.get("replayGain"),
                    "year": int(it.get("streamStartDate")[:4]) if it.get("streamStartDate") else None,
                    **fmt_info
                })

        artists = []
        if isinstance(a_res, dict):
            root = a_res.get("data", a_res)
            items = root.get("artists", {}).get("items", [])
            if not items:
                items = root.get("items", [])

            for it in items:
                # Artists have 'picture' (UUID)
                cover_uuid = it.get("picture")
                cover_art_id = cover_uuid if cover_uuid else f"artist-{it['id']}"
                
                artists.append({
                    "id": f"artist-{it['id']}",
                    "name": it.get("name"),
                    "coverArt": cover_art_id, 
                    "isDir": True
                })

        albums = []
        if isinstance(al_res, dict):
             root = al_res.get("data", al_res)
             items = root.get("albums", {}).get("items", [])
             if not items:
                 items = root.get("items", [])

             for it in items:
                 cover_uuid = it.get("cover")
                 cover_art_id = cover_uuid if cover_uuid else f"album-{it['id']}"
                 
                 albums.append({
                     "id": f"album-{it['id']}",
                     "title": it.get("title"),
                     "name": it.get("title"), 
                     "artist": it.get("artist", {}).get("name"),
                     "coverArt": cover_art_id,
                     "isDir": True
                 })

        return SubsonicResponse.create({
            "status": "ok",
            "version": settings.API_VERSION,
            "searchResult3": {
                "song": songs[:songCount],
                "artist": artists[:artistCount],
                "album": albums[:albumCount]
            }
        }, fmt=f)

    except Exception as e:
        return SubsonicResponse.error(0, str(e), fmt=f)

@router.get("/rest/getCoverArt.view")
@router.get("/rest/getCoverArt")
async def get_cover_art(
    id: str,
    size: Optional[int] = Query(None),
    commons: dict = Depends(common_params)
):
    # Map requested size to Tidal sizes
    # Default to 750 (High quality) if not specified or large
    size_mapping = {
        0: 750, 20: 80, 80: 80,
        100: 160, 200: 320, 256: 320, 300: 320,
        450: 640, 500: 750, 512: 750, 600: 750,
        2137: 1280
    }
    target_size = size_mapping.get(size if size else 0, 160)
    
    # Clean ID (Handle prefixes)
    clean_id = id
    for prefix in ["album-", "track-", "artist-"]:
        if clean_id.startswith(prefix):
            clean_id = clean_id[len(prefix):]
            break
            
    final_id = clean_id.replace("-", "/") 
    
    # If numeric ID (legacy or prefixed), resolve to UUID
    if "-" not in clean_id:
         try:
             data = await hifi_client._get("/cover/", params={"id": clean_id})
             if data and "covers" in data and len(data["covers"]) > 0:
                  cover_obj = data["covers"][0]
                  # Try to extract from URL
                  sample_url = cover_obj.get("1280") or cover_obj.get("640")
                  if sample_url and "/images/" in sample_url:
                      path_part = sample_url.split("/images/")[1]
                      final_id = "/".join(path_part.split("/")[:-1])
         except Exception:
             pass

    tidal_url = f"https://resources.tidal.com/images/{final_id}/{target_size}x{target_size}.jpg"
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(tidal_url, timeout=10.0)
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
                    # Regex for media URL
                    match = re.search(r'media="(https://[^"]+)"', decoded)
                    if match:
                        return RedirectResponse(match.group(1))
                    
                    match_base = re.search(r'<BaseURL>(https://[^<]+)</BaseURL>', decoded)
                    if match_base:
                         return RedirectResponse(match_base.group(1))

             except Exception as e:
                 print(f"Manifest decode error: {e}")
                 pass
             
    except Exception as e:
        print(f"Stream error: {e}")
        
    return SubsonicResponse.error(70, "Stream not found", fmt=commons["f"])


@router.get("/rest/getSong.view")
@router.get("/rest/getSong")
async def get_song(
    id: str,
    commons: dict = Depends(common_params)
):
    track_id = id
    if id.startswith("track-"):
        track_id = id.split("-")[1]
    
    try:
        data = await hifi_client.get_track(int(track_id))
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
                 "replayGain": track.get("trackReplayGain") or track.get("replayGain"), # Check deep vs shallow names
                 "year": int(track.get("streamStartDate")[:4]) if track.get("streamStartDate") else None,
                 "isDir": False,
                 "isVideo": False,
                 **fmt_info
            }
            return SubsonicResponse.create({"song": song}, fmt=commons["f"])
    
    except Exception:
        pass
        
    return SubsonicResponse.error(70, "Song not found", fmt=commons["f"])

# --- Stubs ---

@router.get("/rest/getArtist.view")
@router.get("/rest/getArtist")
async def get_artist(
    id: str,
    commons: dict = Depends(common_params)
):
    f = commons["f"]
    artist_id = id
    if id.startswith("artist-"):
        artist_id = id.split("-")[1]

    try:
        # Fetch artist info + albums concurrently
        info_coro = hifi_client.get_artist(int(artist_id))
        albums_coro = hifi_client.get_artist_albums(int(artist_id))
        
        info_res, albums_res = await asyncio.gather(info_coro, albums_coro, return_exceptions=True)
        
        artist_info = info_res.get("data", {}) if isinstance(info_res, dict) else {}
        albums_items = albums_res.get("albums", {}).get("items", []) if isinstance(albums_res, dict) else []

        albums = []
        for alb in albums_items:
            cover_uuid = alb.get("cover")
            cover_art_id = cover_uuid if cover_uuid else f"album-{alb['id']}"
            albums.append({
                "id": f"album-{alb['id']}",
                "name": alb.get("title"),
                "artist": alb.get("artist", {}).get("name"),
                "year": int(alb.get("releaseDate")[:4]) if alb.get("releaseDate") else None,
                "songCount": alb.get("numberOfTracks"),
                "coverArt": cover_art_id,
                "isDir": True
            })

        cover_uuid = artist_info.get("picture")
        cover_art_id = cover_uuid if cover_uuid else f"artist-{artist_id}"

        return SubsonicResponse.create({
            "status": "ok",
            "version": settings.API_VERSION,
            "artist": {
                "id": f"artist-{artist_id}",
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
    id: str,
    commons: dict = Depends(common_params)
):
    f = commons["f"]
    album_id = id
    if id.startswith("album-"):
        album_id = id.split("-")[1]

    try:
        data = await hifi_client.get_album(int(album_id))
        d = data.get("data", {}) if data else {}
        
        items = d.get("items", [])
        songs = []
        album_cover_uuid = d.get("cover")
        
        for entry in items:
            # Handle wrapper object {"item": {...}, "type": "track"}
            item = entry.get("item", entry)
            
            cover_uuid = item.get("album", {}).get("cover") or album_cover_uuid
            cover_art_id = cover_uuid if cover_uuid else f"album-{album_id}"
            
            fmt_info = get_track_format(item)
            songs.append({
                 "id": f"track-{item['id']}",
                 "title": item.get("title") or "Unknown Title",
                 "artist": item.get("artist", {}).get("name"),
                 "artistId": f"artist-{item.get('artist', {}).get('id')}",
                 "album": d.get("title"),
                 "albumId": f"album-{album_id}",
                 "coverArt": cover_art_id, 
                 "duration": item.get("duration"),
                 "track": item.get("trackNumber"),
                 "discNumber": item.get("volumeNumber"),
                 "replayGain": item.get("replayGain"),
                 "year": int(item.get("streamStartDate")[:4]) if item.get("streamStartDate") else None,
                 "isDir": False,
                 "isVideo": False,
                 **fmt_info
            })

        cover_art_id = album_cover_uuid if album_cover_uuid else f"album-{album_id}"

        return SubsonicResponse.create({
            "status": "ok",
            "version": settings.API_VERSION,
            "album": {
                "id": f"album-{album_id}",
                "name": d.get("title"),
                "artist": d.get("artist", {}).get("name"),
                "year": int(d.get("releaseDate")[:4]) if d.get("releaseDate") else None,
                "songCount": d.get("numberOfTracks"),
                "coverArt": cover_art_id,
                "song": songs
            }
        }, fmt=f)

    except Exception as e:
        return SubsonicResponse.error(0, str(e), fmt=f)

@router.get("/rest/getAlbumInfo2.view")
@router.get("/rest/getAlbumInfo2")
async def get_album_info2(
    id: str,
    request: Request,
    commons: dict = Depends(common_params)
):
    f = commons["f"]
    album_id = id
    if id.startswith("album-"):
        album_id = id.split("-")[1]

    try:
        data = await hifi_client.get_album(int(album_id))
        d = data.get("data", {}) if data else {}
        
        if not d:
             # Try to see if it's an artist ID passed by mistake? No.
             return SubsonicResponse.error(70, "Album not found", fmt=f)

        # Construct Notes
        notes = []
        if d.get("releaseDate"):
            notes.append(f"Released: {d['releaseDate']}")
        if d.get("copyright"):
            notes.append(d['copyright'])
        if d.get("upc"):
            notes.append(f"UPC: {d['upc']}")
            
        note_text = " \n".join(notes)

        # Covers
        cover_uuid = d.get("cover")
        if cover_uuid:
            cover_url_base = f"https://resources.tidal.com/images/{cover_uuid.replace('-', '/')}"
            small_url = f"{cover_url_base}/320x320.jpg"
            large_url = f"{cover_url_base}/1280x1280.jpg"
        else:
            # Fallback local proxy URL
            local_id = f"album-{album_id}"
            base_url = str(request.base_url).rstrip("/")
            small_url = f"{base_url}/rest/getCoverArt.view?id={local_id}&size=320"
            large_url = f"{base_url}/rest/getCoverArt.view?id={local_id}&size=1280"

        return SubsonicResponse.create({
            "status": "ok",
            "version": settings.API_VERSION,
            "albumInfo": {
                "notes": note_text,
                "musicBrainzId": "", # Not available
                "lastFmUrl": "", # Tidal URL is not Last.fm URL
                "smallImageUrl": small_url,
                "largeImageUrl": large_url,
                "year": int(d.get("releaseDate")[:4]) if d.get("releaseDate") else None
            }
        }, fmt=f)

    except Exception as e:
        return SubsonicResponse.error(0, str(e), fmt=f)


@router.get("/rest/getAlbumList2.view")
@router.get("/rest/getAlbumList2")
async def get_album_list(commons: dict = Depends(common_params)):
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "albumList2": {"album": []}
    }, fmt=commons["f"])

@router.get("/rest/getPlaylists.view")
@router.get("/rest/getPlaylists")
async def get_playlists(commons: dict = Depends(common_params)):
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "playlists": {"playlist": []}
    }, fmt=commons["f"])

@router.get("/rest/getGenres.view")
@router.get("/rest/getGenres")
async def get_genres(commons: dict = Depends(common_params)):
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "genres": {"genre": []}
    }, fmt=commons["f"])
