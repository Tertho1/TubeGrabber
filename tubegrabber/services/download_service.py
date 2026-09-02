"""High-level download orchestration service using adapters.

This service emits events through an EventBus instead of directly interacting with UI.
"""

from __future__ import annotations

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
    ) -> None:
        self.ytdlp = ytdlp
        self.ffmpeg = ffmpeg
        self.event_bus = event_bus
        self.output_dir = output_dir
        self.logger = logger
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True
        self.event_bus.publish("download.cancelled")

    def _progress_hook(self, data: Dict[str, Any]) -> None:
        if self.cancelled:
            raise DownloadCancelled("User cancelled")
        self.event_bus.publish("download.progress", data)

    def download_audio(self, url: str, quality: str = "bestaudio/best") -> Path:
        self.cancelled = False
        info = self.ytdlp.extract_info(url, download=False)
        if self.cancelled:
            raise DownloadCancelled("User cancelled")
        filename = self.ytdlp.build_filename(info)
        opts = {
            "format": quality,
            "paths": {"home": str(self.output_dir)},
            "outtmpl": {"default": filename},
        }
        info = self.ytdlp.extract_info(
            url, download=True, progress_hook=self._progress_hook, **opts
        )
        temp_path = Path(self.output_dir) / filename
        final_path = move_to_final_location(temp_path, self.output_dir)
        self.event_bus.publish("download.completed", str(final_path))
        return final_path

    def download_video(self, url: str, format_id: Optional[str] = None) -> Path:
        """Download a video, merging audio if required.

        If a specific format_id is provided and it lacks audio, append bestaudio.
        """
        self.cancelled = False
        info = self.ytdlp.extract_info(url, download=False)
        filename = self.ytdlp.build_filename(info)
        fmt = format_id or "best"
        if format_id and not format_has_audio(format_id, url):
            fmt = fmt + "+bestaudio/best"
        opts = {
            "format": fmt,
            "paths": {"home": str(self.output_dir)},
            "outtmpl": {"default": filename},
            "merge_output_format": "mp4" if "+" in fmt else None,
        }
        # Remove None options (merge_output_format maybe None)
        opts = {k: v for k, v in opts.items() if v is not None}
        self.ytdlp.extract_info(
            url, download=True, progress_hook=self._progress_hook, **opts
        )
        temp_path = Path(self.output_dir) / filename
        final_path = move_to_final_location(temp_path, self.output_dir)
        self.event_bus.publish("download.completed", str(final_path))
        return final_path

    def convert_to_mp3(self, source: Path, bitrate: str = "192k") -> Path:
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
        """Download a playlist as video or audio items.

        Returns list of final file paths.
        """
        self.cancelled = False
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
            "paths": {"home": str(self.output_dir)},
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
            raise
        except Exception as e:
            self.event_bus.publish("download.playlist.error", str(e))
            raise
        # Collect resulting files (they are directly in output_dir)
        files: List[Path] = []
        for entry in os.listdir(self.output_dir):  # type: ignore[arg-type]
            p = Path(self.output_dir) / entry
            if p.is_file():
                files.append(p)
        self.event_bus.publish("download.playlist.completed", [str(f) for f in files])
        return files
