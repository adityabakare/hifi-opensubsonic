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
