from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
import jwt

from app.config import settings
from app.database import get_session
from app.lastfm_client import lastfm_client
from app.models import User
from app.auth import get_user_by_username

router = APIRouter()

class TokenRequest(BaseModel):
    token: str

async def get_current_user(request: Request, session: AsyncSession = Depends(get_session)):
    """Helper to get current user based on auth_token cookie."""
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        user = await get_user_by_username(session, username)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
            
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

@router.get("/api/lastfm/auth-url")
async def get_auth_url(callback_url: str = ""):
    """Returns the URL for the user to authenticate with Last.fm."""
    if not lastfm_client.is_configured():
        return {"status": "error", "message": "Last.fm is not configured on the server."}
        
    url = f"http://www.last.fm/api/auth/?api_key={settings.LASTFM_API_KEY}"
    if callback_url:
        url += f"&cb={callback_url}"
        
    return {"status": "ok", "url": url}

@router.post("/api/lastfm/session")
async def link_lastfm_session(
    payload: TokenRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Exchanges a token for a session key and saves it to the user."""
    if not lastfm_client.is_configured():
        return {"status": "error", "message": "Last.fm is not configured on the server."}
        
    session_key = await lastfm_client.get_session(payload.token)
    if not session_key:
        return {"status": "error", "message": "Failed to authenticate with Last.fm using the provided token."}
        
    user.lastfm_session_key = session_key
    await session.commit()
    
    return {"status": "ok", "message": "Last.fm account linked successfully!"}

@router.post("/api/lastfm/unlink")
async def unlink_lastfm_session(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Unlinks the user's Last.fm account."""
    if user.lastfm_session_key:
        user.lastfm_session_key = None
        await session.commit()
    return {"status": "ok", "message": "Last.fm account unlinked."}

@router.get("/api/lastfm/status")
async def get_lastfm_status(user: User = Depends(get_current_user)):
    """Check if the user has linked a Last.fm account."""
    is_linked = bool(user.lastfm_session_key)
    return {"status": "ok", "linked": is_linked}
