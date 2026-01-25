from fastapi import APIRouter
from app.config import settings

router = APIRouter()

@router.get("/rest/ping.view")
@router.post("/rest/ping.view")
@router.get("/rest/ping")
@router.post("/rest/ping")
async def ping(u: str = None, p: str = None, v: str = None, c: str = None, f: str = "json"):
    """
    Subsonic Ping.
    Returns a simple OK status.
    """
    # TODO: Use response helper to format XML/JSON
    return {
        "subsonic-response": {
            "status": "ok",
            "version": settings.API_VERSION
        }
    }

@router.get("/rest/getLicense.view")
@router.get("/rest/getLicense")
async def get_license(f: str = "json"):
    """
    Mock license endpoint.
    """
    return {
         "subsonic-response": {
            "status": "ok",
            "version": settings.API_VERSION,
            "license": {
                "valid": True,
                "email": "user@example.com",
                "licenseExpires": "2099-01-01T00:00:00"
            }
        }
    }

@router.get("/rest/getUser.view")
@router.get("/rest/getUser")
async def get_user(u: str = None, f: str = "json"):
    """
    Return user details (mocked).
    """
    # Some clients default to "admin"
    username = u or "admin"
    return {
        "subsonic-response": {
            "status": "ok",
            "version": settings.API_VERSION,
            "user": {
                "username": username,
                "email": "user@example.com",
                "scrobblingEnabled": True,
                "adminRole": True,
                "settingsRole": True,
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
                "musicFolderId": [1] # Access to our Tidal folder
            }
        }
    }
