from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    API_VERSION: str = "1.16.1"
    SERVER_VERSION: str = "0.0.1"
    DATABASE_URL: str = "postgresql+asyncpg://subsonic:subsonic@localhost:5432/subsonic"
    JWT_SECRET: str  # Required — must be set in .env or environment
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    HIFI_INSTANCES: List[str] = ["https://monochrome-api.samidy.com"]  # Upstream API URLs (JSON array in .env)
    LASTFM_API_KEY: Optional[str] = None
    LASTFM_API_SECRET: Optional[str] = None
    EXPLICIT_CONTENT_FILTER: str = "All"  # "All", "Clean", "Explicit"
    TOKEN_ENCRYPTION_KEY: str  # 32-url-safe-base64 key for encrypting subsonic_token

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

