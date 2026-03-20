"""
Search endpoints for music discovery.
"""
from fastapi import APIRouter, Depends, Query, Form, Request
import asyncio
from typing import Optional

from app.config import settings
from app.hifi_client import hifi_client
from app.responses import SubsonicResponse
from app.routers.common import common_params, get_track_format, extract_track_metadata

router = APIRouter()


@router.get("/rest/search2.view")
@router.get("/rest/search2")
@router.post("/rest/search2.view")
@router.post("/rest/search2")
@router.get("/rest/search3.view")
@router.get("/rest/search3")
@router.post("/rest/search3.view")
@router.post("/rest/search3")
async def search3(
    request: Request,
    query: str = Query(None),
    songCount: int = Query(20),
    albumCount: int = Query(20),
    artistCount: int = Query(20),
    songOffset: int = Query(0),
    albumOffset: int = Query(0),
    artistOffset: int = Query(0),
    musicFolderId: Optional[str] = Query(None),
    # Form vars
    query_form: str = Form(None, alias="query"),
    songCount_form: int = Form(None, alias="songCount"),
    albumCount_form: int = Form(None, alias="albumCount"),
    artistCount_form: int = Form(None, alias="artistCount"),
    songOffset_form: int = Form(None, alias="songOffset"),
    albumOffset_form: int = Form(None, alias="albumOffset"),
    artistOffset_form: int = Form(None, alias="artistOffset"),
    musicFolderId_form: Optional[str] = Form(None, alias="musicFolderId"),
    
    commons: dict = Depends(common_params)
):
    f = commons["f"]
    query = query or query_form
    songCount = songCount_form if songCount_form is not None else songCount
    albumCount = albumCount_form if albumCount_form is not None else albumCount
    artistCount = artistCount_form if artistCount_form is not None else artistCount
    
    songOffset = songOffset_form if songOffset_form is not None else songOffset
    albumOffset = albumOffset_form if albumOffset_form is not None else albumOffset
    artistOffset = artistOffset_form if artistOffset_form is not None else artistOffset
    
    if not query:
         return SubsonicResponse.error(10, "Required parameter is missing", fmt=f)
    
    try:
        t_res, a_res, al_res = await asyncio.gather(
            hifi_client.search_tracks(query),
            hifi_client.search_artists(query),
            hifi_client.search_albums(query),
            return_exceptions=True
        )
        
        songs = []
        if isinstance(t_res, dict):
            root = t_res.get("data", t_res)
            items = root.get("tracks", {}).get("items", [])
            if not items:
                items = root.get("items", [])

            for it in items:
                songs.append(extract_track_metadata(it))
            
        artists = []
        if isinstance(a_res, dict):
            root = a_res.get("data", a_res)
            items = root.get("artists", {}).get("items", [])
            if not items:
                items = root.get("items", [])

            for it in items:
                cover_uuid = it.get("picture")
                cover_art_id = cover_uuid if cover_uuid else f"ar-{it['id']}"
                
                artists.append({
                    "id": f"ar-{it['id']}",
                    "name": it.get("name") or "Unknown Artist",
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
                cover_art_id = cover_uuid if cover_uuid else f"al-{it['id']}"
                
                artist_name = "Unknown Artist"
                if "artist" in it:
                    artist_name = it.get("artist", {}).get("name")
                elif "artists" in it and isinstance(it["artists"], list) and len(it["artists"]) > 0:
                    artist_name = it["artists"][0].get("name")
                
                albums.append({
                    "id": f"al-{it['id']}",
                    "title": it.get("title") or "Unknown Album",
                    "name": it.get("title") or "Unknown Album", 
                    "artist": artist_name,
                    "coverArt": cover_art_id,
                    "year": int(it.get("releaseDate")[:4]) if it.get("releaseDate") else None,
                    "isDir": True
                })

        is_v2 = "search2" in request.url.path
        key = "searchResult2" if is_v2 else "searchResult3"

        return SubsonicResponse.create({
            key: {
                "song": songs[songOffset : songOffset + songCount],
                "artist": artists[artistOffset : artistOffset + artistCount],
                "album": albums[albumOffset : albumOffset + albumCount]
            }
        }, fmt=f)

    except Exception as e:
        return SubsonicResponse.error(0, str(e), fmt=f)
