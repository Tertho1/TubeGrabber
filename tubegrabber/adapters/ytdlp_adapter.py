"""Adapter around yt_dlp to isolate direct dependency usage."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional
import yt_dlp

from ..errors import ExtractionError

ProgressHook = Callable[[Dict[str, Any]], None]


class YtDlpAdapter:
    def __init__(self, logger=None) -> None:
        self.logger = logger

    def _make_opts(
        self, progress_hook: Optional[ProgressHook] = None, **overrides: Any
    ) -> Dict[str, Any]:
        hooks = []
        if progress_hook:
            hooks.append(progress_hook)
        opts: Dict[str, Any] = {
            "ignoreerrors": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": hooks,
        }
        opts.update(overrides)
        return opts

    def extract_info(
        self,
        url: str,
        download: bool = False,
        progress_hook: Optional[ProgressHook] = None,
        **overrides: Any,
    ) -> Dict[str, Any]:
        opts = self._make_opts(progress_hook=progress_hook, **overrides)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=download)
            if self.logger:
                self.logger.debug("Extracted info for %s", url)
            return info
        except Exception as e:  # broad to convert to domain error
            if self.logger:
                self.logger.exception("yt_dlp extraction failed for %s", url)
            raise ExtractionError(str(e)) from e

    def build_filename(
        self, info: Dict[str, Any], template: str = "%(title)s.%(ext)s"
    ) -> str:
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            name = ydl.prepare_filename(info)
            # Only adjust known yt-dlp webm passthrough quirk: keep extension
            # as-is, but normalize leading/trailing spaces and illegal chars
            # handled downstream in utils.sanitize_filename
            return name
