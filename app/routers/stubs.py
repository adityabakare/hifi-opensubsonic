"""
Stub endpoints for Subsonic API compliance.
These endpoints return empty or acknowledgement responses.
"""
from fastapi import APIRouter, Depends

from app.responses import SubsonicResponse
from app.routers.common import common_params

router = APIRouter()


@router.get("/rest/getGenres.view")
@router.get("/rest/getGenres")
@router.post("/rest/getGenres.view")
@router.post("/rest/getGenres")
async def get_genres(commons: dict = Depends(common_params)):
    return SubsonicResponse.create({
        "genres": {"genre": []}
    }, fmt=commons["f"])


@router.get("/rest/getNowPlaying.view")
@router.get("/rest/getNowPlaying")
async def get_now_playing_stub(commons: dict = Depends(common_params)):
    return SubsonicResponse.create({
        "nowPlaying": {"entry": []}
    }, fmt=commons["f"])


@router.get("/rest/getPodcasts.view")
@router.get("/rest/getPodcasts")
@router.get("/rest/getNewestPodcasts.view")
@router.get("/rest/getNewestPodcasts")
async def get_podcasts_stub(commons: dict = Depends(common_params)):
    return SubsonicResponse.create({
        "podcasts": {"channel": []}
    }, fmt=commons["f"])
