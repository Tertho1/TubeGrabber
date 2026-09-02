"""Unit tests for SearchService mocking YtDlpAdapter (D3)."""

from unittest.mock import MagicMock
from tubegrabber.events import EventBus
from tubegrabber.services.search_service import SearchService


def test_search_videos_mocked():
    """Test searching for videos and mapping to VideoItem models."""
    adapter = MagicMock()
    adapter.extract_info.return_value = {
        "entries": [
            {
                "id": "vid123",
                "title": "Amazing Video",
                "uploader": "Cool Channel",
                "duration": 300,
                "thumbnail": "https://example.com/thumb.jpg",
                "description": "A great video",
            }
        ]
    }
    bus = EventBus()
    service = SearchService(adapter, bus)

    results = service.search_videos("python tutorial", limit=5)
    assert len(results) == 1
    assert results[0].id == "vid123"
    assert results[0].title == "Amazing Video"
    assert results[0].uploader == "Cool Channel"
    assert results[0].duration == 300


def test_search_playlists_mocked():
    """Test searching for playlists and mapping to PlaylistItem models (D3)."""
    adapter = MagicMock()
    adapter.extract_info.return_value = {
        "entries": [
            {
                "id": "PL123456789",
                "title": "Python Full Course Playlist",
                "uploader": "Programming Hub",
                "thumbnail": "https://example.com/plist_thumb.jpg",
                "playlist_count": 25,
            }
        ]
    }
    bus = EventBus()
    service = SearchService(adapter, bus)

    results = service.search_playlists("python course", limit=5)
    assert len(results) == 1
    assert results[0].id == "PL123456789"
    assert results[0].title == "Python Full Course Playlist"
    assert results[0].count == 25
    assert "list=PL123456789" in results[0].url
