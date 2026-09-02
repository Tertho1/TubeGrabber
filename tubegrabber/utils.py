"""Utility helpers for TubeGrabber."""

from yt_dlp import YoutubeDL
import os


def move_to_final_location(temp_path, final_dir):
    """Move a file from temp path into final directory atomically."""
    filename = os.path.basename(temp_path)
    final_path = os.path.join(final_dir, filename)
    os.replace(temp_path, final_path)
    return final_path


def get_quality_height(quality: str) -> int:
    """Map quality keyword to a maximum vertical resolution."""
    return {"best": 4320, "medium": 720, "low": 480}.get(quality.lower(), 720)


def format_has_audio(format_id: str, url: str) -> bool:
    """Check if the specified format contains an audio codec."""
    with YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(url, download=False)
        for fmt in info.get("formats", []):
            if fmt.get("format_id") == format_id:
                return fmt.get("acodec") != "none"
    return False
