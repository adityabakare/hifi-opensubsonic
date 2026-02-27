from fastapi import APIRouter, Depends, Query, Form, Response, Request
import jwt
from datetime import datetime, timedelta, timezone
from app.config import settings
from app.routers.common import common_params
from app.responses import SubsonicResponse
from app.auth import create_user, get_user_by_username, get_current_user, authenticate_user
from app.models import User
from app.database import get_session
from app.limiter import limiter
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

router = APIRouter()

@router.get("/rest/ping.view")
@router.post("/rest/ping.view")
@router.get("/rest/ping")
@router.post("/rest/ping")
async def ping(
    f: Optional[str] = Query("xml"),
    f_form: Optional[str] = Form(None, alias="f")
):
    """
    Subsonic Ping.
    Returns a simple OK status.
    """
    final_f = f_form if f_form else f
    return SubsonicResponse.create({}, fmt=final_f)


@router.get("/rest/getOpenSubsonicExtensions.view")
@router.get("/rest/getOpenSubsonicExtensions")
@router.post("/rest/getOpenSubsonicExtensions.view")
@router.post("/rest/getOpenSubsonicExtensions")
async def get_opensubsonic_extensions(commons: dict = Depends(common_params)):
    """
    List supported OpenSubsonic extensions.
    """
    return SubsonicResponse.create({
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
        "scanStatus": {
            "scanning": False,
            "count": 0
        }
    }, fmt=commons["f"])



@router.get("/rest/getUser.view")
@router.get("/rest/getUser")
async def get_user(commons: dict = Depends(common_params)):
    """
    Return user details.
    """
    user = commons["user"]
    return SubsonicResponse.create({
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
    return SubsonicResponse.create({}, fmt=f)

@router.post("/api/register")
async def register_public_user(
    payload: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_session)
):
    """
    Public, unauthenticated endpoint to register a new user from the Web UI.
    Always enforces is_admin=False and automatically logs the user in upon success.
    """
    if not payload.username or not payload.password:
        return {"status": "error", "message": "Username and password are required"}
        
    # Check if user exists
    existing = await get_user_by_username(session, payload.username)
    if existing:
        return {"status": "error", "message": "Username already taken"}
        
    try:
        new_user = await create_user(
            session=session,
            username=payload.username,
            password=payload.password,
            email=payload.email,
            is_admin=False
        )
        # Create JWT token
        token = create_access_token(data={"sub": new_user.username})
        response.set_cookie(
            key="auth_token",
            value=token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=settings.JWT_EXPIRATION_HOURS * 3600
        )
        return {"status": "ok", "message": "User created successfully"}
    except Exception as e:
        return {"status": "error", "message": "Failed to create user"}

@router.post("/api/login")
async def login_public_user(
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session)
):
    user = await authenticate_user(session, payload.username, payload.password)
    if not user:
        return {"status": "error", "message": "Invalid username or password"}
        
    token = create_access_token(data={"sub": user.username})
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.JWT_EXPIRATION_HOURS * 3600
    )
    return {"status": "ok", "message": "Login successful"}

@router.post("/api/logout")
async def logout_user(response: Response):
    response.delete_cookie(key="auth_token", httponly=True, secure=False, samesite="lax")
    return {"status": "ok", "message": "Logged out successfully"}

@router.get("/api/me")
async def get_current_user_info(user: User = Depends(get_current_user)):
    return {"status": "ok", "username": user.username}
