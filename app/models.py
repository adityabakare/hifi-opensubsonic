from pydantic import BaseModel, Field
from typing import List, Optional, Union

class SubsonicResponseBase(BaseModel):
    status: str
    version: str

class Child(BaseModel):
    id: str
    parent: Optional[str] = None
    title: str
    artist: Optional[str] = None
    isDir: bool
    coverArt: Optional[str] = None
    # Add other common fields like album, year, etc.

class Directory(BaseModel):
    id: str
    parent: Optional[str] = None
    name: str 
    child: List[Child] = []

class Song(BaseModel):
    id: str
    parent: Optional[str] = None
    title: str
    album: Optional[str] = None
    artist: Optional[str] = None
    isDir: bool = False
    coverArt: Optional[str] = None
    duration: Optional[int] = None
    path: Optional[str] = None

class SearchResult3(BaseModel):
    song: List[Song] = []
    # artist: List[Artist] = [] 
    # album: List[Album] = []
    # Simplified for now

from sqlmodel import Field, SQLModel
from datetime import datetime, timezone

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    email: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_admin: bool = False
    lastfm_session_key: Optional[str] = None


class Star(SQLModel, table=True):
    """Starred items (favorites) per user."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    item_id: str = Field(index=True)  # "track-123", "album-456", "artist-789"
    item_type: str  # "song", "album", "artist"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Playlist(SQLModel, table=True):
    """User playlists."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str
    comment: Optional[str] = ""
    public: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    changed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlaylistEntry(SQLModel, table=True):
    """Tracks in a playlist with cached metadata."""
    id: Optional[int] = Field(default=None, primary_key=True)
    playlist_id: int = Field(foreign_key="playlist.id", index=True)
    track_id: str  # "track-123"
    position: int  # Order in playlist
    # Cached metadata (populated via getSong lookup or client-provided data)
    title: Optional[str] = None
    artist: Optional[str] = None
    artist_id: Optional[str] = None
    album: Optional[str] = None
    album_id: Optional[str] = None
    duration: Optional[int] = None
    cover_art: Optional[str] = None
    
    # Extended metadata for rich client display
    year: Optional[int] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    bit_rate: Optional[int] = 1411
    bit_depth: Optional[int] = 16
    sampling_rate: Optional[int] = 44100
    suffix: Optional[str] = "flac"
    content_type: Optional[str] = "audio/flac"
    is_video: bool = False
    is_dir: bool = False
