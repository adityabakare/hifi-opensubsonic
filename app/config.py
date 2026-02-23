from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    API_VERSION: str = "1.16.1"
    SERVER_VERSION: str = "0.0.1"
    DATABASE_URL: str = "postgresql+asyncpg://subsonic:subsonic@localhost:5432/subsonic"
    JWT_SECRET: str  # Required — must be set in .env or environment
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    HIFI_INSTANCES: List[str] = ["https://monochrome-api.samidy.com"]  # Upstream API URLs (JSON array in .env)

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

