"""Search service wrapping adapter logic and returning domain models."""

from __future__ import annotations

from typing import List, Dict, Any

from ..events import EventBus
from ..adapters.ytdlp_adapter import YtDlpAdapter
from ..models import VideoItem, PlaylistItem
from ..errors import ExtractionError


class SearchService:
    def __init__(self, ytdlp: YtDlpAdapter, event_bus: EventBus, logger=None) -> None:
        self.ytdlp = ytdlp
        self.event_bus = event_bus
        self.logger = logger

    def search_videos(self, query: str, limit: int = 25) -> List[VideoItem]:
        self.event_bus.publish("search.started", {"type": "videos", "query": query})
        try:
            info = self.ytdlp.extract_info(f"ytsearch{limit}:{query}", download=False)
        except ExtractionError:
            self.event_bus.publish("search.failed", query)
            raise
        entries = info.get("entries", []) or []
        results: List[VideoItem] = []
        for e in entries:
            results.append(
                VideoItem(
                    id=str(e.get("id")),
                    title=e.get("title") or "",
                    url=e.get("webpage_url")
                    or f"https://www.youtube.com/watch?v={e.get('id')}",
                    uploader=e.get("uploader") or "",
                    duration=e.get("duration") or 0,
                    thumbnail=e.get("thumbnail") or "",
                    description=e.get("description") or "",
                )
            )
        self.event_bus.publish(
            "search.completed", {"count": len(results), "type": "videos"}
        )
        return results

    def search_playlists(self, query: str, limit: int = 25) -> List[PlaylistItem]:
        self.event_bus.publish("search.started", {"type": "playlists", "query": query})
        try:
            info = self.ytdlp.extract_info(f"ytsearch{limit}:{query}", download=False)
        except ExtractionError:
            self.event_bus.publish("search.failed", query)
            raise
        entries = info.get("entries", []) or []
        # Filter for playlist entries (yt-dlp may mix types depending on extractor)
        playlists: List[PlaylistItem] = []
        for e in entries:
            if (
                e.get("_type") == "playlist"
                or "playlist" in (e.get("ie_key") or "").lower()
            ):
                pid = e.get("id") or e.get("playlist_id") or ""
                playlists.append(
                    PlaylistItem(
                        id=str(pid),
                        title=e.get("title") or "",
                        url=e.get("webpage_url")
                        or f"https://www.youtube.com/playlist?list={pid}",
                        uploader=e.get("uploader") or "",
                        thumbnail=e.get("thumbnail") or "",
                        description=e.get("description") or "",
                        count=e.get("playlist_count") or 0,
                    )
                )
        self.event_bus.publish(
            "search.completed", {"count": len(playlists), "type": "playlists"}
        )
        return playlists
