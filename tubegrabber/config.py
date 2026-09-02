"""Unified configuration management using pydantic-settings and platformdirs.

Fixes D5: Single source of truth for all app settings with OS-appropriate paths.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from platformdirs import user_config_dir, user_data_dir, user_cache_dir


class TubeGrabberSettings(BaseSettings):
    """Application settings with validation and defaults."""

    model_config = SettingsConfigDict(
        env_prefix="TUBEGRABBER_",
        case_sensitive=False,
        validate_default=True,
    )

    # Paths
    download_dir: Path = Field(
        default_factory=lambda: Path.home() / "Downloads" / "TubeGrabber"
    )
    temp_dir: Optional[Path] = None  # Auto-computed if None

    # Performance
    max_concurrent_downloads: int = Field(default=3, ge=1, le=10)
    concurrent_fragments: int = Field(default=5, ge=1, le=16)
    http_chunk_size: str = "10M"
    max_retries: int = Field(default=3, ge=0, le=20)

    # Speed limiting (0 = unlimited, in KB/s)
    speed_limit_kbps: int = Field(default=0, ge=0)

    # UI
    theme: str = Field(default="system")  # "light", "dark", "system"
    dark_mode: bool = False  # Legacy compat

    # Quality
    default_video_format: str = "best"
    default_audio_format: str = "bestaudio"
    audio_bitrate: str = "192k"

    # Privacy
    clipboard_monitor: bool = False

    def get_temp_dir(self) -> Path:
        """Get temp directory, auto-computed if not set."""
        if self.temp_dir:
            return self.temp_dir
        return self.download_dir / "temp"


class ConfigManager:
    """Manages persistent configuration with backward compatibility."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize config manager.

        Args:
            config_path: Custom config file path. If None, uses platformdirs.
        """
        if config_path:
            self.config_file = Path(config_path)
        else:
            config_dir = Path(user_config_dir("TubeGrabber", appauthor=False))
            config_dir.mkdir(parents=True, exist_ok=True)
            self.config_file = config_dir / "settings.json"

        # Also check legacy location for migration
        self.legacy_config = Path.home() / ".tubegrabber" / "settings.json"

        self.settings = self._load()

    def _migrate_legacy(self) -> Dict[str, Any]:
        """Migrate from legacy ~/.tubegrabber/settings.json if it exists."""
        if not self.legacy_config.exists():
            return {}

        try:
            data = json.loads(self.legacy_config.read_text(encoding="utf-8"))
            # Map old keys to new keys
            migrated = {}
            if "download_dir" in data:
                migrated["download_dir"] = data["download_dir"]
            if "temp_dir" in data:
                migrated["temp_dir"] = data["temp_dir"]
            if "dark_mode" in data:
                migrated["dark_mode"] = data["dark_mode"]
                migrated["theme"] = "dark" if data["dark_mode"] else "light"
            if "max_retries" in data:
                migrated["max_retries"] = data["max_retries"]

            return migrated
        except Exception:
            return {}

    def _load(self) -> TubeGrabberSettings:
        """Load settings from disk with migration support."""
        # Start with defaults
        overrides = {}

        # Try migration first
        legacy_data = self._migrate_legacy()
        if legacy_data:
            overrides.update(legacy_data)

        # Load current config (overrides migration)
        if self.config_file.exists():
            try:
                data = json.loads(self.config_file.read_text(encoding="utf-8"))
                overrides.update(data)
            except Exception:
                pass

        # Create settings with overrides
        return TubeGrabberSettings(**overrides)

    def save(self) -> None:
        """Persist current settings to disk."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict, handling Path objects
        data = self.settings.model_dump(mode="json")

        self.config_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value (backward compat helper)."""
        return getattr(self.settings, key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value (backward compat helper)."""
        setattr(self.settings, key, value)

    def ensure(self) -> None:
        """Ensure directories exist."""
        self.settings.download_dir.mkdir(parents=True, exist_ok=True)
        self.settings.get_temp_dir().mkdir(parents=True, exist_ok=True)


# Convenience functions for common paths
def get_config_dir() -> Path:
    """Get the app config directory."""
    return Path(user_config_dir("TubeGrabber", "TubeGrabber"))


def get_data_dir() -> Path:
    """Get the app data directory."""
    return Path(user_data_dir("TubeGrabber", "TubeGrabber"))


def get_cache_dir() -> Path:
    """Get the app cache directory (for thumbnails, etc)."""
    return Path(user_cache_dir("TubeGrabber", "TubeGrabber"))
