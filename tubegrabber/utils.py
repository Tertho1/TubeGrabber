"""Utility helpers for TubeGrabber.

Includes atomic move with cross-device support (D8), collision deduplication,
filename sanitization, and format inspection without network re-fetching (D4).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any


def sanitize_filename(name: str, max_length: int = 255) -> str:
    """Sanitize a filename by removing illegal characters and trimming length.

    Removes Windows/Unix invalid characters: < > : " / \\ | ? *
    """
    # Replace illegal characters with underscore
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # Strip leading/trailing dots and whitespace
    clean = clean.strip(". ")
    if not clean:
        clean = "download"

    # Truncate to max_length while preserving extension
    if len(clean) > max_length:
        path = Path(clean)
        ext = path.suffix
        stem = path.stem[: max_length - len(ext)]
        clean = f"{stem}{ext}"

    return clean


def get_unique_path(target_path: Path) -> Path:
    """Get a unique path by appending (1), (2), etc. if the file already exists."""
    if not target_path.exists():
        return target_path

    parent = target_path.parent
    stem = target_path.stem
    suffix = target_path.suffix

    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def move_to_final_location(temp_path: Path | str, final_dir: Path | str) -> Path:
    """Move a file from temp path into final directory atomically with dedup.

    Fixes D8:
    - Uses shutil.move for cross-device support (e.g., C: to D: drive)
    - Appends (1), (2) on filename collisions to avoid silent data loss
    - Sanitizes filename for OS safety
    """
    temp_path = Path(temp_path)
    final_dir = Path(final_dir)
    final_dir.mkdir(parents=True, exist_ok=True)

    if not temp_path.exists():
        raise FileNotFoundError(f"Source file not found: {temp_path}")

    # Sanitize filename
    clean_name = sanitize_filename(temp_path.name)
    target_path = final_dir / clean_name

    # Deduplicate if file exists
    final_path = get_unique_path(target_path)

    # Cross-device move with fallback
    shutil.move(str(temp_path), str(final_path))
    return final_path


def get_quality_height(quality: str) -> int:
    """Map quality keyword to a maximum vertical resolution."""
    return {"best": 4320, "medium": 720, "low": 480}.get(quality.lower(), 720)


def format_has_audio(format_id: str, info: dict[str, Any] | None = None) -> bool:
    """Check if the specified format contains an audio codec from pre-fetched info dict.

    Fixes D4: Accepts already-fetched info dict to eliminate redundant network queries.
    """
    if not info:
        return True  # Fallback assumption if no info provided

    for fmt in info.get("formats", []):
        if str(fmt.get("format_id")) == str(format_id):
            return fmt.get("acodec") != "none" and fmt.get("acodec") is not None
    return False
