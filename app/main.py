from fastapi import FastAPI
from app.config import settings
from app.routers import system, browsing, search, media, stubs, user_data
from app.responses import SubsonicResponse, SubsonicException
from app.auth import get_user_by_username, create_user
from app.database import engine, get_session # for sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from contextlib import asynccontextmanager
from app.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    
    # Seed default user if not exists
    # We need a session independent of request
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        user = await get_user_by_username(session, "admin")
        if not user:
            print("Seeding default admin user...")
            await create_user(session, "admin", "admin", is_admin=True)
            
    yield

app = FastAPI(
    title="Hifi-OpenSubsonic",
    description="Subsonic API wrapper for Hifi-API (Tidal)",
    version=settings.SERVER_VERSION,
    lifespan=lifespan,
)

@app.exception_handler(SubsonicException)
async def subsonic_exception_handler(request: Request, exc: SubsonicException):
    return SubsonicResponse.error(exc.code, exc.message, fmt=exc.fmt, version=settings.API_VERSION)

app.include_router(system.router)
app.include_router(browsing.router)
app.include_router(search.router)
app.include_router(media.router)
app.include_router(user_data.router)  # Must be before stubs to override endpoints
app.include_router(stubs.router)


@app.get("/")
def read_root():
    return {"message": "Hifi-OpenSubsonic API is running. Point your Subsonic client here."}
