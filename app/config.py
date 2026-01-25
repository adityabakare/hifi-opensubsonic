from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    HIFI_API_URL: str = "https://monochrome-api.samidy.com"
    API_VERSION: str = "1.16.1" # Subsonic API Version
    SERVER_VERSION: str = "0.0.1" # Our server version

    class Config:
        env_file = ".env"

settings = Settings()
