"""Configuration management for TubeGrabber.

Provides a ConfigManager with simple load/save and defaults handling.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

_DEFAULTS: Dict[str, Any] = {
    "download_path": "downloads",
    "audio_format": "mp3",
    "max_concurrent_downloads": 2,
    "theme": "default",
}


class ConfigManager:
    def __init__(self, config_file: Path) -> None:
        self.config_file = config_file
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if self.config_file.exists():
            try:
                self.data = json.loads(self.config_file.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}
        # apply defaults for missing keys
        for k, v in _DEFAULTS.items():
            self.data.setdefault(k, v)

    def save(self) -> None:
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def ensure(self) -> None:
        """Persist current config to disk."""
        self.save()
