"""Search service wrapping adapter logic and returning domain models.

Fixes D3: Implements proper playlist searching using YouTube playlist search filters.
"""

from __future__ import annotations

import urllib.parse
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
        """Search for videos using ytsearch."""
        self.event_bus.publish("search.started", {"type": "videos", "query": query})
        try:
            info = self.ytdlp.extract_info(
                f"ytsearch{limit}:{query}",
                download=False,
                extract_flat=True,
            )
        except ExtractionError:
            self.event_bus.publish("search.failed", query)
            raise

        entries = info.get("entries", []) or []
        results: List[VideoItem] = []
        for e in entries:
            if not e:
                continue
            vid_id = str(e.get("id") or "")
            if not vid_id:
                continue

            results.append(
                VideoItem(
                    id=vid_id,
                    title=e.get("title") or "Unknown Video",
                    url=e.get("url") or e.get("webpage_url") or f"https://www.youtube.com/watch?v={vid_id}",
                    uploader=e.get("uploader") or e.get("channel") or "Unknown",
                    duration=e.get("duration") or 0,
                    thumbnail=e.get("thumbnail") or "",
                    description=e.get("description") or "",
                )
            )
            if len(results) >= limit:
                break

        self.event_bus.publish(
            "search.completed", {"count": len(results), "type": "videos"}
        )
        return results

    def search_playlists(self, query: str, limit: int = 25) -> List[PlaylistItem]:
        """Search for YouTube playlists using playlist search filter (D3 fix)."""
        self.event_bus.publish("search.started", {"type": "playlists", "query": query})

        # YouTube filter for playlists: sp=EgIQAw%253D%253D (type: Playlist)
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}&sp=EgIQAw%253D%253D"

        try:
            info = self.ytdlp.extract_info(
                search_url,
                download=False,
                extract_flat=True,
            )
        except ExtractionError:
            self.event_bus.publish("search.failed", query)
            raise

        entries = info.get("entries", []) or []
        playlists: List[PlaylistItem] = []

        for e in entries:
            if not e:
                continue
            pid = str(e.get("id") or e.get("playlist_id") or "")
            if not pid:
                continue

            # Ensure url is full playlist link
            url = e.get("url") or e.get("webpage_url") or f"https://www.youtube.com/playlist?list={pid}"
            if not url.startswith("http"):
                url = f"https://www.youtube.com/playlist?list={pid}"

            playlists.append(
                PlaylistItem(
                    id=pid,
                    title=e.get("title") or "Unknown Playlist",
                    url=url,
                    uploader=e.get("uploader") or e.get("channel") or "Unknown",
                    thumbnail=e.get("thumbnail") or "",
                    description=e.get("description") or "",
                    count=e.get("playlist_count") or 0,
                )
            )
            if len(playlists) >= limit:
                break

        self.event_bus.publish(
            "search.completed", {"count": len(playlists), "type": "playlists"}
        )
        return playlists
