"""FFmpeg adapter to encapsulate invocation details."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..environment import get_startup_info
from ..errors import ConversionError


class FFmpegAdapter:
    def __init__(self, ffmpeg_bin: Path, logger=None) -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self.logger = logger

    def run(self, args: list[str]) -> None:
        cmd = [str(self.ffmpeg_bin)] + args
        if self.logger:
            self.logger.debug("Running ffmpeg: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                startupinfo=get_startup_info(),
                check=False,
            )
        except Exception as e:
            if self.logger:
                self.logger.exception("FFmpeg invocation failure")
            raise ConversionError(str(e)) from e
        if result.returncode != 0:
            if self.logger:
                self.logger.error("FFmpeg error: %s", result.stderr[:500])
            raise ConversionError(result.stderr)
        if self.logger:
            self.logger.debug("FFmpeg completed successfully")
