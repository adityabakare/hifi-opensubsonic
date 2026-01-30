from sqlmodel import SQLModel, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Create async engine
engine = create_async_engine(settings.DATABASE_URL, echo=True, future=True)

import asyncio
import logging

logger = logging.getLogger(__name__)

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
                logger.error(f"Failed to connect to database after {retries} attempts.")
                raise e
            logger.warning(f"Database connection failed ({e}), retrying in {delay}s...")
            await asyncio.sleep(delay)

async def get_session() -> AsyncSession:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
