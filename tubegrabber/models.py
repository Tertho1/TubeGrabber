"""Domain models for TubeGrabber."""

from dataclasses import dataclass


@dataclass(slots=True)
class VideoItem:
    id: str
    title: str
    url: str
    uploader: str = "Unknown"
    duration: int = 0  # seconds
    thumbnail: str = ""
    description: str = ""


@dataclass(slots=True)
class PlaylistItem:
    id: str
    title: str
    url: str
    uploader: str = "Unknown"
    thumbnail: str = ""
    description: str = ""
    count: int | None = None  # number of videos if known
