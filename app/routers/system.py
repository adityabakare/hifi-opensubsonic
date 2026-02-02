from fastapi import APIRouter, Depends
from app.config import settings
from app.routers.common import common_params
from app.responses import SubsonicResponse

router = APIRouter()

@router.get("/rest/ping.view")
@router.post("/rest/ping.view")
@router.get("/rest/ping")
@router.post("/rest/ping")
async def ping(commons: dict = Depends(common_params)):
    """
    Subsonic Ping.
    Returns a simple OK status.
    """
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION
    }, fmt=commons["f"])


@router.get("/rest/getOpenSubsonicExtensions.view")
@router.get("/rest/getOpenSubsonicExtensions")
@router.post("/rest/getOpenSubsonicExtensions.view")
@router.post("/rest/getOpenSubsonicExtensions")
async def get_opensubsonic_extensions(commons: dict = Depends(common_params)):
    """
    List supported OpenSubsonic extensions.
    """
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "openSubsonicExtensions": [
            {"name": "lyrics", "versions": [1]},
            {"name": "formPost", "versions": [1]}
        ]
    }, fmt=commons["f"])

@router.get("/rest/getLicense.view")
@router.get("/rest/getLicense")
async def get_license(commons: dict = Depends(common_params)):
    """
    Mock license endpoint.
    """
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "license": {
            "valid": True,
            "email": "user@example.com",
            "licenseExpires": "2099-01-01T00:00:00"
        }
    }, fmt=commons["f"])
    
@router.get("/rest/getScanStatus.view")
@router.get("/rest/getScanStatus")
async def get_scan_status(commons: dict = Depends(common_params)):
    """
    Return scanning status (always false for this proxy).
    """
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "scanStatus": {
            "scanning": False,
            "count": 0
        }
    }, fmt=commons["f"])

@router.get("/rest/scrobble.view")
@router.get("/rest/scrobble")
async def scrobble(commons: dict = Depends(common_params)):
    """
    Stub for scrobble.
    """
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION
    }, fmt=commons["f"])

@router.get("/rest/getUser.view")
@router.get("/rest/getUser")
async def get_user(commons: dict = Depends(common_params)):
    """
    Return user details.
    """
    user = commons["user"]
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION,
        "user": {
            "username": user.username,
            "email": user.email or "user@example.com",
            "scrobblingEnabled": True,
            "adminRole": user.is_admin,
            "settingsRole": user.is_admin,
            "downloadRole": True,
            "uploadRole": True,
            "playlistRole": True,
            "coverArtRole": True,
            "commentRole": True,
            "podcastRole": True,
            "streamRole": True,
            "jukeboxRole": True,
            "shareRole": True,
            "videoConversionRole": True,
            "musicFolderId": [1] 
        }
    }, fmt=commons["f"])
