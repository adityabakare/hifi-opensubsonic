from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User
from typing import Optional
from fastapi import Request, Depends, HTTPException
import jwt
import hashlib
from cryptography.fernet import Fernet
from app.config import settings
from app.database import get_session

import bcrypt

# Use the required TOKEN_ENCRYPTION_KEY directly
fernet = Fernet(settings.TOKEN_ENCRYPTION_KEY.encode('utf-8'))

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        # Invalid hash format
        return False

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

async def authenticate_user(
    session: AsyncSession, 
    username: str, 
    password: Optional[str] = None, 
    token: Optional[str] = None, 
    salt: Optional[str] = None
) -> Optional[User]:
    """
    Authenticate a user by username and either password OR (token + salt).
    Token is expected to be md5(password + salt).
    """
    statement = select(User).where(User.username == username)
    result = await session.execute(statement)
    user = result.scalars().first()
    
    if not user:
        return None
        
    if password is not None:
        if verify_password(password, user.password_hash):
            return user
            
    if token is not None and salt is not None:
        # Subsonic Token Auth requires knowing the raw password to compute md5(password + salt)
        if hasattr(user, 'subsonic_token') and user.subsonic_token:
            # Decrypt the stored token
            plain_password = fernet.decrypt(user.subsonic_token.encode('utf-8')).decode('utf-8')
            expected = hashlib.md5((plain_password + salt).encode('utf-8')).hexdigest()
            if token.lower() == expected.lower():
                return user

    return None

async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    statement = select(User).where(User.username == username)
    result = await session.execute(statement)
    return result.scalars().first()

async def create_user(session: AsyncSession, username: str, password: str, email: str = None, is_admin: bool = False) -> User:
    password_hash = get_password_hash(password)
    # Encrypt the plaintext password so it's not stored in the clear
    encrypted_token = fernet.encrypt(password.encode('utf-8')).decode('utf-8')
    
    user = User(
        username=username, 
        password_hash=password_hash, 
        email=email, 
        is_admin=is_admin,
        subsonic_token=encrypted_token
    )
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
