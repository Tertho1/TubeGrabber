"""Unit tests for the unified ConfigManager and TubeGrabberSettings."""

import json
from pathlib import Path
from tubegrabber.config import ConfigManager, TubeGrabberSettings


def test_default_settings(tmp_path: Path):
    """Test that default settings are correctly initialized."""
    config_file = tmp_path / "settings.json"
    manager = ConfigManager(config_path=config_file)
    # Isolate from real home legacy file
    manager.legacy_config = tmp_path / "nonexistent_legacy.json"
    manager.settings = manager._load()
    settings = manager.settings

    assert settings.max_concurrent_downloads == 3
    assert settings.concurrent_fragments == 5
    assert settings.max_retries == 10  # Phase 1.1: tuned to 10 for 429 resilience
    assert settings.fragment_retries == 10
    assert settings.speed_limit_kbps == 0
    assert settings.theme == "system"
    assert not settings.clipboard_monitor


def test_save_and_load(tmp_path: Path):
    """Test saving and re-loading settings."""
    config_file = tmp_path / "settings.json"
    manager = ConfigManager(config_path=config_file)

    manager.settings.max_concurrent_downloads = 5
    manager.settings.speed_limit_kbps = 1024
    manager.settings.theme = "dark"
    manager.save()

    assert config_file.exists()

    # Re-open in a fresh manager
    manager2 = ConfigManager(config_path=config_file)
    assert manager2.settings.max_concurrent_downloads == 5
    assert manager2.settings.speed_limit_kbps == 1024
    assert manager2.settings.theme == "dark"


def test_legacy_migration(tmp_path: Path, monkeypatch):
    """Test automatic migration from legacy ~/.tubegrabber/settings.json."""
    legacy_file = tmp_path / "legacy_settings.json"
    legacy_data = {
        "download_dir": "D:/Custom/Downloads",
        "temp_dir": "D:/Custom/Temp",
        "dark_mode": True,
        "max_retries": 5
    }
    legacy_file.write_text(json.dumps(legacy_data), encoding="utf-8")

    config_file = tmp_path / "new_settings.json"
    manager = ConfigManager(config_path=config_file)
    manager.legacy_config = legacy_file

    # Trigger re-load with mocked legacy
    settings = manager._load()
    assert str(settings.download_dir).replace("\\", "/") == "D:/Custom/Downloads"
    assert str(settings.temp_dir).replace("\\", "/") == "D:/Custom/Temp"
    assert settings.dark_mode is True
    assert settings.theme == "dark"
    assert settings.max_retries == 5
