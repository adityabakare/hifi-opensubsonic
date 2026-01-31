"""
Stub endpoints for Subsonic API compliance.
These endpoints return empty or acknowledgement responses.
"""
from fastapi import APIRouter, Depends, Query, Form

from app.config import settings
from app.responses import SubsonicResponse
from app.routers.common import common_params

router = APIRouter()


@router.get("/rest/getAlbumList.view")
@router.get("/rest/getAlbumList")
@router.post("/rest/getAlbumList.view")
@router.post("/rest/getAlbumList")
@router.get("/rest/getAlbumList2.view")
@router.get("/rest/getAlbumList2")
@router.post("/rest/getAlbumList2.view")
@router.post("/rest/getAlbumList2")
async def get_album_list(
    type: str = Query("random"), 
    size: int = Query(10), 
    offset: int = Query(0),
    # Form variants
    type_form: str = Form(None, alias="type"),
    size_form: int = Form(None, alias="size"),
    offset_form: int = Form(None, alias="offset"),
    
    commons: dict = Depends(common_params)
):
    """
    Stub for getAlbumList/2. Returns empty list.
    """
    f = commons["f"]
    # Logic to merge Query vs Form
    # type defaults to "random", type_form defaults to None.
    # If type_form is present, use it. Else use type (which captures URL or default).
    final_type = type_form if type_form else type
    final_size = size_form if size_form is not None else size
    final_offset = offset_form if offset_form is not None else offset
    
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "albumList2": {"album": []}
    }, fmt=f)


@router.get("/rest/getGenres.view")
@router.get("/rest/getGenres")
@router.post("/rest/getGenres.view")
@router.post("/rest/getGenres")
async def get_genres(commons: dict = Depends(common_params)):
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "genres": {"genre": []}
    }, fmt=commons["f"])


@router.get("/rest/getArtists.view")
@router.get("/rest/getArtists")
async def get_artists(commons: dict = Depends(common_params)):
    """
    Stub for getArtists. Returns empty index since we are a search-based proxy.
    """
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "artists": {
            "index": [],
            "ignoredArticles": "The El La Los Las Le Les"
        }
    }, fmt=commons["f"])


@router.get("/rest/getIndexes.view")
@router.get("/rest/getIndexes")
@router.post("/rest/getIndexes.view")
@router.post("/rest/getIndexes")
async def get_indexes(commons: dict = Depends(common_params)):
    """
    Stub for folder index. Returns empty.
    """
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "indexes": {
            "lastModified": 0,
            "index": [],
            "child": [],
            "ignoredArticles": "The El La Los Las Le Les"
        }
    }, fmt=commons["f"])


@router.get("/rest/search2.view")
@router.get("/rest/search2")
async def search2_stub(query: str, commons: dict = Depends(common_params)):
    """
    Stub for legacy Search2.
    """
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "searchResult2": {
            "artist": [],
            "album": [],
            "song": []
        }
    }, fmt=commons["f"])


@router.get("/rest/getTopSongs.view")
@router.get("/rest/getTopSongs")
@router.get("/rest/getRandomSongs.view")
@router.get("/rest/getRandomSongs")
async def get_random_songs_stub(commons: dict = Depends(common_params)):
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "randomSongs": {"song": []}
    }, fmt=commons["f"])


@router.get("/rest/getNowPlaying.view")
@router.get("/rest/getNowPlaying")
async def get_now_playing_stub(commons: dict = Depends(common_params)):
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "nowPlaying": {"entry": []}
    }, fmt=commons["f"])


@router.get("/rest/getPodcasts.view")
@router.get("/rest/getPodcasts")
@router.get("/rest/getNewestPodcasts.view")
@router.get("/rest/getNewestPodcasts")
async def get_podcasts_stub(commons: dict = Depends(common_params)):
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "podcasts": {"channel": []}
    }, fmt=commons["f"])
