import asyncio
import logging
from typing import AsyncGenerator

from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# Create async engine with tuned connection pool
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_size=20,           # Persistent connections in the pool
    max_overflow=10,        # Extra connections allowed under load
    pool_recycle=1800,      # Recycle connections every 30 min (avoid stale)
    pool_pre_ping=True,     # Detect dead connections before use
)

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    retries = 10
    delay = 5
    for i in range(retries):
        try:
            async with engine.begin() as conn:
                # await conn.run_sync(SQLModel.metadata.drop_all)
                await conn.run_sync(SQLModel.metadata.create_all)
            logger.info("Database initialized successfully.")
            return
        except Exception as e:
            if i == retries - 1:
                logger.error("Failed to connect to database after %d attempts.", retries)
                raise e
            logger.warning("Database connection failed (%s), retrying in %ds...", e, delay)
            await asyncio.sleep(delay)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
