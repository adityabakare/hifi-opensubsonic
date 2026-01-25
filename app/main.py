from fastapi import FastAPI
from app.config import settings
from app.routers import system, subsonic

app = FastAPI(
    title="Hifi-OpenSubsonic",
    description="Subsonic API wrapper for Hifi-API (Tidal)",
    version=settings.SERVER_VERSION,
)

app.include_router(system.router)
app.include_router(subsonic.router)

@app.get("/")
def read_root():
    return {"message": "Hifi-OpenSubsonic API is running. Point your Subsonic client here."}
