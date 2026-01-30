from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    HIFI_API_URL: str = "https://monochrome-api.samidy.com"
    API_VERSION: str = "1.15.0"
    SERVER_VERSION: str = "0.0.1"
    DATABASE_URL: str = "postgresql+asyncpg://subsonic:subsonic@localhost:5432/subsonic"

    class Config:
        env_file = ".env"

settings = Settings()
