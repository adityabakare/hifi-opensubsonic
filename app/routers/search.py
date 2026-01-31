"""
Search endpoints for music discovery.
"""
from fastapi import APIRouter, Depends
import asyncio

from app.config import settings
from app.hifi_client import hifi_client
from app.responses import SubsonicResponse
from app.routers.common import common_params, get_track_format, extract_track_metadata

router = APIRouter()


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
                cover_art_id = cover_uuid if cover_uuid else f"artist-{it['id']}"
                
                artists.append({
                    "id": f"artist-{it['id']}",
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
                cover_art_id = cover_uuid if cover_uuid else f"album-{it['id']}"
                
                artist_name = "Unknown Artist"
                if "artist" in it:
                    artist_name = it.get("artist", {}).get("name")
                elif "artists" in it and isinstance(it["artists"], list) and len(it["artists"]) > 0:
                    artist_name = it["artists"][0].get("name")
                
                albums.append({
                    "id": f"album-{it['id']}",
                    "title": it.get("title") or "Unknown Album",
                    "name": it.get("title") or "Unknown Album", 
                    "artist": artist_name,
                    "coverArt": cover_art_id,
                    "year": int(it.get("releaseDate")[:4]) if it.get("releaseDate") else None,
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
