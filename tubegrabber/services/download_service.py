"""High-level download orchestration service using adapters.

This service emits events through an EventBus instead of directly interacting with UI.
Fixes D1, D2: Per-job staging in TEMP_DIR/<job_id>/ with atomic move to output_dir.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..events import EventBus
from ..adapters.ytdlp_adapter import YtDlpAdapter
from ..adapters.ffmpeg_adapter import FFmpegAdapter
from ..errors import DownloadCancelled
from ..utils import move_to_final_location, format_has_audio


class DownloadService:
    def __init__(
        self,
        ytdlp: YtDlpAdapter,
        ffmpeg: FFmpegAdapter,
        event_bus: EventBus,
        output_dir: Path,
        logger=None,
        temp_base: Optional[Path] = None,
    ) -> None:
        self.ytdlp = ytdlp
        self.ffmpeg = ffmpeg
        self.event_bus = event_bus
        self.output_dir = output_dir
        self.logger = logger
        self.temp_base = temp_base or (output_dir / "temp")
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True
        self.event_bus.publish("download.cancelled")

    def _progress_hook(self, data: Dict[str, Any]) -> None:
        if self.cancelled:
            raise DownloadCancelled("User cancelled")
        self.event_bus.publish("download.progress", data)

    def _get_job_temp_dir(self) -> Path:
        """Create per-job temp directory for isolated staging (D1)."""
        job_id = uuid.uuid4().hex[:8]
        job_temp = self.temp_base / job_id
        job_temp.mkdir(parents=True, exist_ok=True)
        return job_temp

    def download_audio(self, url: str, quality: str = "bestaudio/best") -> Path:
        """Download audio with per-job staging."""
        self.cancelled = False
        info = self.ytdlp.extract_info(url, download=False)
        if self.cancelled:
            raise DownloadCancelled("User cancelled")

        filename = self.ytdlp.build_filename(info)
        job_temp = self._get_job_temp_dir()

        opts = {
            "format": quality,
            "paths": {"home": str(job_temp)},  # Download to per-job temp (D1)
            "outtmpl": {"default": filename},
        }

        self.ytdlp.extract_info(
            url, download=True, progress_hook=self._progress_hook, **opts
        )

        # Move from temp to final output with atomic dedup (D1, D8)
        temp_path = job_temp / filename
        final_path = move_to_final_location(temp_path, self.output_dir)

        # Clean up job temp dir
        shutil.rmtree(job_temp, ignore_errors=True)

        self.event_bus.publish("download.completed", str(final_path))
        return final_path

    def download_video(self, url: str, format_id: Optional[str] = None) -> Path:
        """Download a video with per-job staging, merging audio if required.

        If a specific format_id is provided and it lacks audio, append bestaudio.
        """
        self.cancelled = False
        info = self.ytdlp.extract_info(url, download=False)
        if self.cancelled:
            raise DownloadCancelled("User cancelled")

        filename = self.ytdlp.build_filename(info)
        job_temp = self._get_job_temp_dir()

        fmt = format_id or "best"
        # Check if format has audio using pre-fetched info (D4)
        if format_id and not format_has_audio(format_id, info):
            fmt = fmt + "+bestaudio/best"

        opts = {
            "format": fmt,
            "paths": {"home": str(job_temp)},  # Download to per-job temp (D1)
            "outtmpl": {"default": filename},
            "merge_output_format": "mp4" if "+" in fmt else None,
        }
        # Remove None options
        opts = {k: v for k, v in opts.items() if v is not None}

        self.ytdlp.extract_info(
            url, download=True, progress_hook=self._progress_hook, **opts
        )

        # Move from temp to final output with atomic dedup (D1, D8)
        temp_path = job_temp / filename
        final_path = move_to_final_location(temp_path, self.output_dir)

        # Clean up job temp dir
        shutil.rmtree(job_temp, ignore_errors=True)

        self.event_bus.publish("download.completed", str(final_path))
        return final_path

    def convert_to_mp3(self, source: Path, bitrate: str = "192k") -> Path:
        """Convert a video/audio file to MP3."""
        target = source.with_suffix(".mp3")
        args = [
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ab",
            bitrate,
            "-ar",
            "44100",
            "-f",
            "mp3",
            str(target),
        ]
        self.ffmpeg.run(args)
        self.event_bus.publish("conversion.completed", str(target))
        return target

    # ---------------- Playlist Downloads -----------------
    def download_playlist(
        self, url: str, quality: str = "best", audio_only: bool = False
    ) -> List[Path]:
        """Download a playlist as video or audio items with per-job staging.

        Returns list of final file paths.
        Fixes D2: Scopes file enumeration to job's temp dir, not entire output_dir.
        """
        self.cancelled = False
        job_temp = self._get_job_temp_dir()

        # Determine format string and postprocessors
        if audio_only:
            fmt = "bestaudio/best"
            postprocessors = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
            post_args = ["-write_xing", "0"]
        else:
            # map quality keyword to resolution cap
            height_map = {"best": 4320, "medium": 720, "low": 480}
            height = height_map.get(quality.lower(), 720)
            fmt = f"bestvideo[height<={height}]+bestaudio/best"
            postprocessors = []
            post_args = []

        def hook(d: Dict[str, Any]):
            self._progress_hook(d)

        opts: Dict[str, Any] = {
            "format": fmt,
            "paths": {"home": str(job_temp)},  # Download to per-job temp (D1, D2)
            "outtmpl": {"default": "%(title)s.%(ext)s"},
            "progress_hooks": [hook],
            "retries": 3,
            "fragment_retries": 3,
            "ignoreerrors": True,
            "skip_unavailable_fragments": True,
            "continue_dl": True,
            "nooverwrites": True,
        }
        if postprocessors:
            opts["postprocessors"] = postprocessors
            opts["postprocessor_args"] = post_args

        # Execute download
        self.event_bus.publish("download.playlist.start", url)
        try:
            self.ytdlp.extract_info(url, download=True, **opts)
        except DownloadCancelled:
            self.event_bus.publish("download.playlist.cancelled", url)
            shutil.rmtree(job_temp, ignore_errors=True)
            raise
        except Exception as e:
            self.event_bus.publish("download.playlist.error", str(e))
            shutil.rmtree(job_temp, ignore_errors=True)
            raise

        # Collect resulting files from job's temp dir (D2 fix: scope to job_temp)
        final_files: List[Path] = []
        for entry in os.listdir(job_temp):
            temp_file = job_temp / entry
            if temp_file.is_file():
                # Move each file to final output with atomic dedup
                final_path = move_to_final_location(temp_file, self.output_dir)
                final_files.append(final_path)

        # Clean up job temp dir
        shutil.rmtree(job_temp, ignore_errors=True)

        self.event_bus.publish("download.playlist.completed", [str(f) for f in final_files])
        return final_files
