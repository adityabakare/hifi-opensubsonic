from fastapi import APIRouter, Depends, Query, Form
from app.config import settings
from app.routers.common import common_params
from app.responses import SubsonicResponse
from app.auth import create_user, get_user_by_username
from app.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

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

@router.get("/rest/createUser.view")
@router.get("/rest/createUser")
@router.post("/rest/createUser.view")
@router.post("/rest/createUser")
async def create_user_admin(
    username: str = Query(None),
    password: str = Query(None),
    email: Optional[str] = Query(None),
    adminRole: Optional[bool] = Query(False),
    # Form vars
    username_form: str = Form(None, alias="username"),
    password_form: str = Form(None, alias="password"),
    email_form: Optional[str] = Form(None, alias="email"),
    adminRole_form: Optional[bool] = Form(None, alias="adminRole"),
    
    commons: dict = Depends(common_params),
    session: AsyncSession = Depends(get_session)
):
    """
    Creates a new Subsonic user. Require admin privileges.
    """
    user = commons["user"]
    f = commons["f"]
    
    # Must be admin to create users
    if not user.is_admin:
        return SubsonicResponse.error(50, "User is not authorized for the given operation.", fmt=f)
        
    real_username = username or username_form
    real_password = password or password_form
    
    if not real_username or not real_password:
        return SubsonicResponse.error(10, "Required parameter is missing", fmt=f)
        
    real_email = email if email is not None else email_form
    real_admin = adminRole if adminRole is not None else adminRole_form
    
    # Ensure user does not already exist
    existing = await get_user_by_username(session, real_username)
    if existing:
        return SubsonicResponse.error(60, "The user already exists.", fmt=f)
        
    # Create the user natively
    try:
        new_user = await create_user(
            session=session,
            username=real_username,
            password=real_password,
            email=real_email,
            is_admin=real_admin
        )
    except Exception as e:
        return SubsonicResponse.error(0, "Generic error", fmt=f)

    # Return empty successful ack as per Subsonic API spec logic
    return SubsonicResponse.create({
        "status": "ok",
        "version": settings.API_VERSION
    }, fmt=f)
