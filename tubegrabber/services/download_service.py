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
        speed_limit_kbps: int = 0,
    ) -> None:
        self.ytdlp = ytdlp
        self.ffmpeg = ffmpeg
        self.event_bus = event_bus
        self.output_dir = output_dir
        self.logger = logger
        self.temp_base = temp_base or (output_dir / "temp")
        self.speed_limit_kbps = speed_limit_kbps  # 0 = unlimited, Phase 1.4
        self.cancelled = False

    def set_speed_limit(self, kbps: int) -> None:
        """Update per-job speed limit (KB/s), 0 = unlimited."""
        self.speed_limit_kbps = max(0, kbps)

    def _get_speed_opts(self) -> Dict[str, Any]:
        """Return yt-dlp ratelimit opts if limit set."""
        if self.speed_limit_kbps > 0:
            bps = self.speed_limit_kbps * 1024
            return {"ratelimit": bps, "throttledratelimit": bps}
        return {}

    def cancel(self) -> None:
        self.cancelled = True
        self.event_bus.publish("download.cancelled")

    def _progress_hook(self, data: Dict[str, Any]) -> None:
        if self.cancelled:
            raise DownloadCancelled("User cancelled")
        self.event_bus.publish("download.progress", data)

    def _get_job_temp_dir(self, url: Optional[str] = None) -> Path:
        """Create per-job temp directory for isolated staging (D1).

        Phase 1.3: deterministic per-URL for resume (keeps .part), fallback to uuid.
        """
        if url:
            import hashlib

            job_id = hashlib.md5(url.encode("utf-8")).hexdigest()[:12]
        else:
            job_id = uuid.uuid4().hex[:8]
        job_temp = self.temp_base / job_id
        job_temp.mkdir(parents=True, exist_ok=True)
        return job_temp

    def cleanup_stale_temp(self, max_age_hours: int = 24) -> int:
        """Remove job temp dirs older than max_age_hours. Returns count removed."""
        import time

        if not self.temp_base.exists():
            return 0
        now = time.time()
        removed = 0
        for child in self.temp_base.iterdir():
            if not child.is_dir():
                continue
            try:
                age = now - child.stat().st_mtime
                if age > max_age_hours * 3600:
                    shutil.rmtree(child, ignore_errors=True)
                    removed += 1
            except Exception:
                continue
        return removed

    def download_audio(self, url: str, quality: str = "bestaudio/best") -> Path:
        """Download audio with per-job staging."""
        self.cancelled = False
        info = self.ytdlp.extract_info(url, download=False)
        if self.cancelled:
            raise DownloadCancelled("User cancelled")

        filename = self.ytdlp.build_filename(info)
        job_temp = self._get_job_temp_dir(url)  # deterministic for resume (1.3)

        opts = {
            "format": quality,
            "paths": {"home": str(job_temp)},  # Download to per-job temp (D1)
            "outtmpl": {"default": filename},
            "concurrent_fragment_downloads": 5,  # Phase 1.1: 5-8, cap 16 per AGENTS.md:101
            "http_chunk_size": 10 * 1024 * 1024,  # 10M
            "retries": 10,
            "fragment_retries": 10,
            "extractor_retries": 3,
            "retry_sleep_functions": {"http": lambda n: 1 + n * 0.5},  # exp backoff for 429
            "continuedl": True,  # 1.3: explicit resume
            "continue_dl": True,  # alias for compat
            "nopart": False,  # keep .part for resume
            "overwrites": False,  # atomic dedup via move_to_final_location
            "nooverwrites": True,
        }
        opts.update(self._get_speed_opts())  # 1.4: ratelimit

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
        job_temp = self._get_job_temp_dir(url)  # deterministic for resume

        fmt = format_id or "best"
        # Check if format has audio using pre-fetched info (D4)
        if format_id and not format_has_audio(format_id, info):
            fmt = fmt + "+bestaudio/best"

        opts = {
            "format": fmt,
            "paths": {"home": str(job_temp)},  # Download to per-job temp (D1)
            "outtmpl": {"default": filename},
            "merge_output_format": "mp4" if "+" in fmt else None,
            "concurrent_fragment_downloads": 5,
            "http_chunk_size": 10 * 1024 * 1024,
            "retries": 10,
            "fragment_retries": 10,
            "extractor_retries": 3,
            "retry_sleep_functions": {"http": lambda n: 1 + n * 0.5},
            "continuedl": True,
            "continue_dl": True,
            "nopart": False,
            "overwrites": False,
            "nooverwrites": True,
        }
        # Remove None options
        opts = {k: v for k, v in opts.items() if v is not None}
        opts.update(self._get_speed_opts())  # 1.4: ratelimit

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
        """Convert a video/audio file to MP3 with passthrough check (1.5)."""
        target = source.with_suffix(".mp3")
        # Passthrough: if already mp3, just copy (avoid double transcode)
        if source.suffix.lower() == ".mp3" and source.resolve() != target.resolve():
            # Use atomic dedup for target
            from ..utils import move_to_final_location

            # Copy then move atomically to handle cross-device
            tmp_copy = target.with_suffix(".tmp.mp3")
            shutil.copy2(source, tmp_copy)
            # If source and target are same file, just return
            if source.resolve() == target.resolve():
                tmp_copy.unlink(missing_ok=True)
                self.event_bus.publish("conversion.completed", str(target))
                return target
            final = move_to_final_location(tmp_copy, target.parent)
            self.event_bus.publish("conversion.completed", str(final))
            return final
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
        job_temp = self._get_job_temp_dir(url)  # deterministic for resume

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
            "concurrent_fragment_downloads": 5,
            "http_chunk_size": 10 * 1024 * 1024,
            "retries": 10,
            "fragment_retries": 10,
            "extractor_retries": 3,
            "retry_sleep_functions": {"http": lambda n: 1 + n * 0.5},
            "continuedl": True,
            "continue_dl": True,
            "nopart": False,
            "overwrites": False,
            "ignoreerrors": True,
            "skip_unavailable_fragments": True,
            "nooverwrites": True,
        }
        if postprocessors:
            opts["postprocessors"] = postprocessors
            opts["postprocessor_args"] = post_args
        opts.update(self._get_speed_opts())  # 1.4: ratelimit

        # Execute download — keep .part on cancel/failure for resume (1.3)
        self.event_bus.publish("download.playlist.start", url)
        try:
            self.ytdlp.extract_info(url, download=True, **opts)
        except DownloadCancelled:
            self.event_bus.publish("download.playlist.cancelled", url)
            # keep job_temp/.part for resume, not deleted
            raise
        except Exception as e:
            self.event_bus.publish("download.playlist.error", str(e))
            # keep .part for resume
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
