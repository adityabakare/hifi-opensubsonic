"""
Common utilities shared across all Subsonic router modules.
"""
from fastapi import Query, Depends
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.hifi_client import hifi_client
from app.responses import SubsonicResponse, SubsonicException
from app.database import get_session
from app.auth import authenticate_user


async def common_params(
    u: str = Query(None),  # Username
    p: str = Query(None),  # Password
    t: str = Query(None),  # Token
    s: str = Query(None),  # Salt
    v: str = Query(None),  # Version
    c: str = Query(None),  # Client
    f: str = Query("json"),  # Format
    session: AsyncSession = Depends(get_session),
):
    """
    Common authentication dependency for all Subsonic endpoints.
    """
    fmt = f
    
    user = None
    if u and p:
        # Handle 'enc:' hex-encoded passwords
        password = p
        if p.startswith("enc:"):
            try:
                hex_str = p[4:]
                password = bytes.fromhex(hex_str).decode("utf-8")
            except Exception:
                pass  # Fallback to raw password if decode fails
        
        user = await authenticate_user(session, u, password)

    if not user:
        if not u:
            raise SubsonicException(code=10, message="Required parameter is missing.", fmt=fmt)
        else:
            raise SubsonicException(code=40, message="Wrong username or password", fmt=fmt)
    
    return {"f": fmt, "v": v, "user": user}


def get_track_format(item: dict) -> dict:
    """
    Derive Subsonic format metadata from Tidal item.
    """
    quality = item.get("audioQuality", "LOSSLESS")
    
    bit_depth = item.get("bitDepth")
    sample_rate = item.get("sampleRate")
    exact_bitrate = None
    
    if bit_depth and sample_rate:
        exact_bitrate = int((bit_depth * sample_rate * 2) / 1000)

    if quality in ["HI_RES_LOSSLESS", "LOSSLESS"]:
        return {
            "suffix": "flac",
            "contentType": "audio/flac",
            "bitRate": exact_bitrate if exact_bitrate else 1411,
            "bitDepth": bit_depth if bit_depth else 16,
            "samplingRate": sample_rate if sample_rate else 44100,
            "size": int((exact_bitrate if exact_bitrate else 1411) * 1000 * item.get("duration", 0) / 8),
            "path": f"music/{item.get('id')}.flac"
        }
    elif quality == "HIGH":
        return {
            "suffix": "m4a",
            "contentType": "audio/mp4",
            "bitRate": exact_bitrate if exact_bitrate else 320,
            "size": int((exact_bitrate if exact_bitrate else 320) * 1000 * item.get("duration", 0) / 8),
            "path": f"music/{item.get('id')}.m4a"
        }
    else:
        return {
            "suffix": "m4a",
            "contentType": "audio/mp4",
            "bitRate": exact_bitrate if exact_bitrate else 96,
            "size": int((exact_bitrate if exact_bitrate else 96) * 1000 * item.get("duration", 0) / 8),
            "path": f"music/{item.get('id')}.m4a"
        }
