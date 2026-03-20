from typing import Optional
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, DateTime, Index
from datetime import datetime, timezone


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    email: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    is_admin: bool = False
    lastfm_session_key: Optional[str] = None
    subsonic_token: Optional[str] = None


class Star(SQLModel, table=True):
    """Starred items (favorites) per user."""
    __table_args__ = (
        Index("ix_star_user_item", "user_id", "item_id"),       # star/unstar lookups
        Index("ix_star_user_type", "user_id", "item_type"),     # getStarred, getAlbumList, getArtists
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    item_id: str = Field(index=True)  # "tr-123", "al-456", "ar-789"
    item_type: str  # "song", "album", "artist"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))


class Playlist(SQLModel, table=True):
    """User playlists."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str
    comment: Optional[str] = None
    public: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    changed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))


class PlaylistEntry(SQLModel, table=True):
    """Tracks in a playlist with cached metadata."""
    __table_args__ = (
        Index("ix_playlistentry_playlist_pos", "playlist_id", "position"),  # ordered retrieval
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    playlist_id: int = Field(foreign_key="playlist.id", index=True)
    track_id: str  # "tr-123"
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
    bit_rate: Optional[int] = None
    bit_depth: Optional[int] = None
    sampling_rate: Optional[int] = None
    suffix: Optional[str] = None
    content_type: Optional[str] = None
    bpm: Optional[int] = None
    is_video: bool = False
    is_dir: bool = False
    
    # Replay Gain properties
    track_gain: Optional[float] = None
    album_gain: Optional[float] = None
    track_peak: Optional[float] = None
    album_peak: Optional[float] = None


class PlayQueue(SQLModel, table=True):
    """Per-user play queue state (one per user)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, unique=True)
    current_track_id: Optional[str] = None  # "tr-123" — currently playing track
    position: Optional[int] = 0  # Position in milliseconds within current track
    changed_by: Optional[str] = None  # Client name that last saved the queue
    changed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))


class PlayQueueEntry(SQLModel, table=True):
    """Tracks in a user's play queue with cached metadata."""
    __table_args__ = (
        Index("ix_playqueueentry_queue_pos", "play_queue_id", "position"),  # ordered retrieval
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    play_queue_id: int = Field(foreign_key="playqueue.id", index=True)
    track_id: str  # "tr-123"
    position: int  # Order in queue
    # Cached metadata
    title: Optional[str] = None
    artist: Optional[str] = None
    artist_id: Optional[str] = None
    album: Optional[str] = None
    album_id: Optional[str] = None
    duration: Optional[int] = None
    cover_art: Optional[str] = None
    year: Optional[int] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    bit_rate: Optional[int] = None
    bit_depth: Optional[int] = None
    sampling_rate: Optional[int] = None
    suffix: Optional[str] = "flac"
    content_type: Optional[str] = "audio/flac"
    bpm: Optional[int] = None
    is_video: bool = False
    is_dir: bool = False
    # Replay Gain
    track_gain: Optional[float] = None
    album_gain: Optional[float] = None
    track_peak: Optional[float] = None
    album_peak: Optional[float] = None
