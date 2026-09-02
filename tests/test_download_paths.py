"""Unit tests for atomic moves, path isolation, and format checks (D1, D2, D4, D8)."""

from pathlib import Path
from tubegrabber.utils import (
    sanitize_filename,
    get_unique_path,
    move_to_final_location,
    format_has_audio,
)


def test_sanitize_filename():
    """Test removing illegal characters from filenames."""
    dirty = 'My: Video/With? Illegal* "Chars"| <test>'
    clean = sanitize_filename(dirty)
    assert ":" not in clean
    assert "/" not in clean
    assert "?" not in clean
    assert "*" not in clean
    assert '"' not in clean
    assert "|" not in clean
    assert "<" not in clean
    assert ">" not in clean


def test_unique_path_deduplication(tmp_path: Path):
    """Test get_unique_path generates (1), (2) collision suffixes."""
    file1 = tmp_path / "song.mp3"
    file1.touch()

    file2 = get_unique_path(file1)
    assert file2.name == "song (1).mp3"
    file2.touch()

    file3 = get_unique_path(file1)
    assert file3.name == "song (2).mp3"


def test_move_to_final_location_atomic_and_dedup(tmp_path: Path):
    """Test moving a file from temp to final destination with collision handling."""
    temp_dir = tmp_path / "temp" / "job123"
    temp_dir.mkdir(parents=True)
    source = temp_dir / "video.mp4"
    source.write_text("dummy video content")

    final_dir = tmp_path / "downloads"
    final_dir.mkdir(parents=True)

    # First move
    res1 = move_to_final_location(source, final_dir)
    assert res1.name == "video.mp4"
    assert res1.exists()
    assert not source.exists()

    # Create another source with same name
    source2 = temp_dir / "video.mp4"
    source2.write_text("another video content")

    # Second move should dedup to video (1).mp4
    res2 = move_to_final_location(source2, final_dir)
    assert res2.name == "video (1).mp4"
    assert res2.exists()
    assert res1.exists()


def test_format_has_audio_offline():
    """Test format_has_audio checks pre-fetched info dict without network queries (D4)."""
    mock_info = {
        "formats": [
            {"format_id": "137", "vcodec": "avc1", "acodec": "none"},  # Video only
            {"format_id": "140", "vcodec": "none", "acodec": "mp4a.40.2"},  # Audio only
            {"format_id": "22", "vcodec": "avc1", "acodec": "mp4a.40.2"},  # Combined
        ]
    }

    assert not format_has_audio("137", mock_info)
    assert format_has_audio("140", mock_info)
    assert format_has_audio("22", mock_info)
    assert format_has_audio("unknown", None)  # Fallback
