from passlib.context import CryptContext
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User
from typing import Optional
from fastapi import Request, Depends, HTTPException
import jwt
from app.config import settings
from app.database import get_session

# Setup password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

async def authenticate_user(session: AsyncSession, username: str, password: str) -> Optional[User]:
    """
    Authenticate a user by username and password.
    """
    statement = select(User).where(User.username == username)
    result = await session.execute(statement)
    user = result.scalars().first()
    
    if not user:
        return None
        
    if not verify_password(password, user.password_hash):
        return None
        
    return user

async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    statement = select(User).where(User.username == username)
    result = await session.execute(statement)
    return result.scalars().first()

async def create_user(session: AsyncSession, username: str, password: str, email: str = None, is_admin: bool = False) -> User:
    password_hash = get_password_hash(password)
    user = User(username=username, password_hash=password_hash, email=email, is_admin=is_admin)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

async def get_current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    """
    FastAPI dependency: extract and validate the current user from the auth_token cookie.
    Raises HTTPException(401) on any auth failure.
    """
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
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
