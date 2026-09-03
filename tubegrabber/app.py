"""Tkinter application layer composing managers and UI.

Now integrates modular services, adapters, config manager, logging, and event bus.
"""

import os
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from yt_dlp import YoutubeDL

from .adapters.ffmpeg_adapter import FFmpegAdapter
from .adapters.ytdlp_adapter import YtDlpAdapter
from .config import ConfigManager, get_config_dir
from .environment import setup_environment
from .errors import (
    ConversionError,
    DownloadCancelled,
    ExtractionError,
    TubeGrabberError,
)
from .events import EventBus
from .logging_utils import setup_logging

# Conversion handled via DownloadService
from .models import PlaylistItem, VideoItem
from .services.download_service import DownloadService
from .services.queue_service import DownloadQueue
from .services.search_service import SearchService


class TubeGrabberApp:
    def __init__(self, root: tk.Tk):
        setup_environment()
        self.root = root
        self.root.title("TubeGrabber")
        self.root.geometry("900x600")
        self.root.minsize(800, 500)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Config & Logging (load first)
        self.config = ConfigManager()
        self.logger = setup_logging(get_config_dir())

        # State
        self.current_option = tk.StringVar()
        self.download_progress = tk.DoubleVar()
        self.dark_mode = tk.BooleanVar(value=self.config.settings.dark_mode)
        self.max_retries = tk.IntVar(value=self.config.settings.max_retries)
        self.video_formats = []
        self.download_dir = tk.StringVar(value=str(self.config.settings.download_dir))
        self.temp_dir = tk.StringVar(value=str(self.config.settings.get_temp_dir()))
        self.cancel_requested = False
        # active_download is now a property (see below) delegating to download_queue

        # Event bus
        self.event_bus = EventBus()

        # Concurrent queue (Phase 1.2: replaces single active_download gate)
        self.download_queue = DownloadQueue(
            max_workers=self.config.settings.max_concurrent_downloads,
            event_bus=self.event_bus,
            logger=self.logger,
        )
        # Keep legacy flag for UI state; queue is source of truth
        self._queue_legacy_active = False

        # Adapters & Services
        ffmpeg_exe = self._discover_ffmpeg()
        self.ytdlp_adapter = YtDlpAdapter(logger=self.logger)
        self.ffmpeg_adapter = FFmpegAdapter(ffmpeg_exe, logger=self.logger)
        self.download_service = DownloadService(
            self.ytdlp_adapter,
            self.ffmpeg_adapter,
            self.event_bus,
            Path(self.download_dir.get()),
            logger=self.logger,
            temp_base=Path(self.temp_dir.get()),
            speed_limit_kbps=self.config.settings.speed_limit_kbps,
        )
        self.search_service = SearchService(self.ytdlp_adapter, self.event_bus, logger=self.logger)

        # Search state (replaces legacy SearchManager)
        self.search_results = []  # list[VideoItem|PlaylistItem]
        self.results_per_page = 20
        self.current_page = 1

        self._wire_event_subscriptions()
        # Schedule asynchronous health check so UI is responsive immediately
        self.root.after(500, self._health_check_async)

        # Style
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.configure_styles()

        # Layout
        self.create_main_containers()
        self.create_option_buttons()
        self.create_input_area()
        self.create_progress_area()
        self.create_menu()

        self.load_settings()
        if self.dark_mode.get():
            self.toggle_dark_mode()

        self.current_option.set("search_videos")
        self.show_input_fields("search_videos")
        self.create_directory_structure()

    @property
    def active_download(self) -> bool:  # Phase 1.2: queue is source of truth
        return getattr(self, "download_queue", None) is not None and self.download_queue.has_active

    @active_download.setter
    def active_download(self, value: bool) -> None:
        # Legacy compatibility — ignore, queue tracks state
        pass

    # ----------------- Persistence -----------------
    def load_settings(self):
        """Load settings from ConfigManager (already loaded in __init__)."""
        # Settings already loaded during ConfigManager init
        # Just ensure UI reflects them (already done in __init__)

    def save_settings(self):
        """Save current UI state back to config."""
        try:
            self.config.settings.download_dir = Path(self.download_dir.get())
            self.config.settings.temp_dir = Path(self.temp_dir.get())
            self.config.settings.dark_mode = self.dark_mode.get()
            self.config.settings.theme = "dark" if self.dark_mode.get() else "light"
            self.config.settings.max_retries = self.max_retries.get()
            self.config.save()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    # ----------------- Environment -----------------
    def create_directory_structure(self):
        os.makedirs(self.download_dir.get(), exist_ok=True)
        os.makedirs(self.temp_dir.get(), exist_ok=True)

    # ----------------- UI Builders -----------------
    def configure_styles(self):
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("TLabel", background="#f0f0f0")

    def create_main_containers(self):
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.left_panel = ttk.Frame(self.main_frame, width=200)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.right_panel = ttk.Frame(self.main_frame)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.progress_frame = ttk.Frame(self.root)
        self.progress_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

    def create_option_buttons(self):
        frame = ttk.LabelFrame(self.left_panel, text="Options", padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        options = [
            ("Search", "search_videos"),
            ("Single Video", "single_video"),
            ("Audio Only", "audio_only"),
            ("Playlist", "playlist"),
            ("Playlist Audio", "playlist_audio"),
            ("Convert Video", "convert_video"),
        ]
        for text, value in options:
            ttk.Radiobutton(
                frame,
                text=text,
                variable=self.current_option,
                value=value,
                command=lambda v=value: self.show_input_fields(v),
            ).pack(anchor=tk.W, pady=4)

    def create_input_area(self):
        self.input_frame = ttk.Frame(self.right_panel)
        self.input_frame.pack(fill=tk.BOTH, expand=True)
        # Frames
        self.single_video_frame = ttk.Frame(self.input_frame)
        self.audio_only_frame = ttk.Frame(self.input_frame)
        self.playlist_frame = ttk.Frame(self.input_frame)
        self.playlist_audio_frame = ttk.Frame(self.input_frame)
        self.convert_video_frame = ttk.Frame(self.input_frame)
        self.search_video_frame = ttk.Frame(self.input_frame)
        # Single video
        ttk.Label(self.single_video_frame, text="Video URL:").grid(row=0, column=0, sticky=tk.W)
        self.video_url_entry = ttk.Entry(self.single_video_frame, width=50)
        self.video_url_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(
            self.single_video_frame,
            text="Get Formats",
            command=self.fetch_video_formats,
        ).grid(row=0, column=2, padx=5)
        ttk.Label(self.single_video_frame, text="Format:").grid(row=1, column=0, sticky=tk.W)
        self.format_combobox = ttk.Combobox(self.single_video_frame, state="readonly", width=50)
        self.format_combobox.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(
            self.single_video_frame, text="Download", command=self.download_single_video
        ).grid(row=2, column=1, pady=10, sticky=tk.E)
        # Audio only
        ttk.Label(self.audio_only_frame, text="Video URL:").grid(row=0, column=0, sticky=tk.W)
        self.audio_url_entry = ttk.Entry(self.audio_only_frame, width=50)
        self.audio_url_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(self.audio_only_frame, text="Download Audio", command=self.download_audio).grid(
            row=1, column=1, pady=10, sticky=tk.E
        )
        # Playlist
        ttk.Label(self.playlist_frame, text="Playlist URL:").grid(row=0, column=0, sticky=tk.W)
        self.playlist_url_entry = ttk.Entry(self.playlist_frame, width=50)
        self.playlist_url_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(self.playlist_frame, text="Quality:").grid(row=1, column=0, sticky=tk.W)
        self.playlist_quality_combobox = ttk.Combobox(
            self.playlist_frame, values=["Best", "Medium", "Low"], state="readonly"
        )
        self.playlist_quality_combobox.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        self.playlist_quality_combobox.set("Best")
        ttk.Button(
            self.playlist_frame,
            text="Download Playlist",
            command=self.download_playlist,
        ).grid(row=2, column=1, pady=10, sticky=tk.E)
        # Playlist audio
        ttk.Label(self.playlist_audio_frame, text="Playlist URL:").grid(
            row=0, column=0, sticky=tk.W
        )
        self.playlist_audio_url_entry = ttk.Entry(self.playlist_audio_frame, width=50)
        self.playlist_audio_url_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(
            self.playlist_audio_frame,
            text="Download Playlist Audio",
            command=self.download_playlist_audio,
        ).grid(row=1, column=1, pady=10, sticky=tk.E)
        # Convert video
        ttk.Label(self.convert_video_frame, text="Video File:").grid(row=0, column=0, sticky=tk.W)
        self.video_file_entry = ttk.Entry(self.convert_video_frame, width=50)
        self.video_file_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(self.convert_video_frame, text="Browse", command=self.browse_video_file).grid(
            row=0, column=2, padx=5
        )
        ttk.Button(self.convert_video_frame, text="Convert", command=self.convert_video).grid(
            row=1, column=1, pady=10, sticky=tk.E
        )
        # Search
        sframe = ttk.Frame(self.search_video_frame)
        sframe.pack(fill=tk.X, pady=5)
        self.search_type = tk.StringVar(value="videos")
        ttk.Radiobutton(sframe, text="Videos", variable=self.search_type, value="videos").grid(
            row=0, column=0, padx=5
        )
        ttk.Radiobutton(
            sframe, text="Playlists", variable=self.search_type, value="playlists"
        ).grid(row=0, column=1, padx=5)
        ttk.Label(sframe, text="Query:").grid(row=0, column=2, padx=5)
        self.search_entry = ttk.Entry(sframe, width=40)
        self.search_entry.grid(row=0, column=3, padx=5)
        self.search_entry.bind("<Return>", lambda e: self.search_videos())
        ttk.Button(sframe, text="Search", command=self.search_videos).grid(row=0, column=4, padx=5)
        self.results_container = ttk.LabelFrame(self.search_video_frame, text="Results")
        self.results_container.pack(fill=tk.BOTH, expand=True)
        self.results_frame = ttk.Frame(self.results_container)
        self.results_frame.pack(fill=tk.BOTH, expand=True)
        pagef = ttk.Frame(self.search_video_frame)
        pagef.pack(fill=tk.X)
        self.prev_page_btn = ttk.Button(
            pagef, text="←", width=3, command=self.prev_page, state="disabled"
        )
        self.prev_page_btn.pack(side=tk.LEFT)
        self.page_buttons_frame = ttk.Frame(pagef)
        self.page_buttons_frame.pack(side=tk.LEFT, padx=5)
        self.next_page_btn = ttk.Button(
            pagef, text="→", width=3, command=self.next_page, state="disabled"
        )
        self.next_page_btn.pack(side=tk.LEFT)
        self.search_status_label = ttk.Label(self.search_video_frame, text="Ready")
        self.search_status_label.pack(fill=tk.X, pady=4)

    def create_progress_area(self):
        pf = ttk.Frame(self.progress_frame)
        pf.pack(fill=tk.X)
        ttk.Label(pf, text="Progress:").pack(side=tk.LEFT)
        self.cancel_button = ttk.Button(
            pf, text="Cancel", command=self.cancel_download, state="disabled"
        )
        self.cancel_button.pack(side=tk.RIGHT)
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            orient=tk.HORIZONTAL,
            length=400,
            mode="determinate",
            variable=self.download_progress,
        )
        self.progress_bar.pack(fill=tk.X, pady=5)
        self.status_label = ttk.Label(self.progress_frame, text="Ready")
        self.status_label.pack(fill=tk.X)

    def create_menu(self):
        m = tk.Menu(self.root)
        file_m = tk.Menu(m, tearoff=0)
        file_m.add_command(label="Set Download Dir", command=self.select_download_directory)
        file_m.add_command(label="Set Temp Dir", command=self.select_temp_directory)
        file_m.add_separator()
        file_m.add_command(label="Exit", command=self.root.quit)
        m.add_cascade(label="File", menu=file_m)
        settings_m = tk.Menu(m, tearoff=0)
        settings_m.add_checkbutton(
            label="Dark Mode", variable=self.dark_mode, command=self.toggle_dark_mode
        )
        settings_m.add_command(label="Retry Settings", command=self.show_retry_settings)
        m.add_cascade(label="Settings", menu=settings_m)
        help_m = tk.Menu(m, tearoff=0)
        help_m.add_command(label="About", command=self.show_about)
        m.add_cascade(label="Help", menu=help_m)
        self.root.config(menu=m)

    # ----------------- Navigation -----------------
    def show_input_fields(self, option):
        for f in [
            self.single_video_frame,
            self.audio_only_frame,
            self.playlist_frame,
            self.playlist_audio_frame,
            self.convert_video_frame,
            self.search_video_frame,
        ]:
            f.pack_forget()
        mapping = {
            "single_video": self.single_video_frame,
            "audio_only": self.audio_only_frame,
            "playlist": self.playlist_frame,
            "playlist_audio": self.playlist_audio_frame,
            "convert_video": self.convert_video_frame,
            "search_videos": self.search_video_frame,
        }
        frame = mapping.get(option)
        if frame:
            frame.pack(fill=tk.BOTH, expand=True)

    # ----------------- Actions -----------------
    def fetch_video_formats(self):
        url = self.video_url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Enter a URL")
            return
        self.update_progress(text="Fetching formats...")
        # Disable combo while fetching
        self.format_combobox["values"] = ["Loading..."]

        def worker():
            try:
                info = self.ytdlp_adapter.extract_info(url, download=False)
                formats = [f for f in info.get("formats", []) if f.get("vcodec") != "none"]

                def on_done():
                    if not formats:
                        messagebox.showerror("Error", "No video formats")
                        self.format_combobox["values"] = []
                        self.update_progress(text="Ready")
                        return
                    self.video_formats = formats
                    self.format_combobox["values"] = [
                        f"{f['format_id']}: {f.get('format_note', '')} ({f.get('ext')}) - {f.get('resolution', 'N/A')}"
                        for f in formats
                    ]
                    self.format_combobox.current(0)
                    self.update_progress(text="Formats ready")

                self.root.after(0, on_done)
            except Exception as e:
                self.logger.exception("Format fetch failed for %s", url)

                def on_error(e=e):  # capture e for closure
                    messagebox.showerror("Error", f"Format fetch failed: {e}")
                    self.update_progress(text="Ready")

                self.root.after(0, on_error)

        threading.Thread(target=worker, daemon=True).start()

    def download_single_video(self):
        url = self.video_url_entry.get().strip()
        if not url:
            return
        try:
            idx = self.format_combobox.current()
            fmt_id = self.video_formats[idx]["format_id"] if idx >= 0 else None
        except Exception:
            fmt_id = None
        # Phase 1.2: via queue (3-5 workers) instead of single thread
        self.download_queue.submit(lambda: self._video_thread(url, fmt_id), url=url, kind="video")

    def _video_thread(self, url, fmt_id):
        try:
            self._begin_download()
            path = self.download_service.download_video(url, format_id=fmt_id)
            self.root.after(0, self.update_progress, 100, "Download complete")
            messagebox.showinfo("Success", f"Saved: {os.path.basename(path)}")
        except Exception as e:
            self._handle_error(e, context="Video download")
        finally:
            self._end_download()

    def download_audio(self):
        url = self.audio_url_entry.get().strip()
        if not url:
            return
        self.download_queue.submit(lambda: self._audio_thread(url), url=url, kind="audio")

    def _audio_thread(self, url):
        try:
            self._begin_download()
            path = self.download_service.download_audio(url)
            self.root.after(0, self.update_progress, 100, "Audio complete")
            messagebox.showinfo("Success", f"Saved: {os.path.basename(path)}")
        except Exception as e:
            self._handle_error(e, context="Audio download")
        finally:
            self._end_download()

    def download_playlist(self):
        url = self.playlist_url_entry.get().strip()
        if not url:
            return
        quality = self.playlist_quality_combobox.get().lower()
        self.download_queue.submit(
            lambda: self._playlist_thread(url, quality, False),
            url=url,
            kind="playlist",
        )

    def download_playlist_audio(self):
        url = self.playlist_audio_url_entry.get().strip()
        if not url:
            return
        self.download_queue.submit(
            lambda: self._playlist_thread(url, "best", True),
            url=url,
            kind="playlist_audio",
        )

    def _playlist_thread(self, url, quality, audio_only):
        try:
            self._begin_download()
            self.update_progress(0, "Starting playlist...")
            self.download_service.download_playlist(url, quality=quality, audio_only=audio_only)
            self.root.after(0, self.update_progress, 100, "Playlist complete")
            messagebox.showinfo("Success", "Playlist finished")
        except Exception as e:
            self._handle_error(e, context="Playlist download")
        finally:
            self._end_download()

    def convert_video(self):
        path = self.video_file_entry.get().strip()
        if not path:
            return
        self.download_queue.submit(lambda: self._convert_thread(path), url=path, kind="convert")

    def _convert_thread(self, path):
        try:
            self._begin_download()
            self.update_progress(0, "Converting...")
            final = self.download_service.convert_to_mp3(Path(path))
            self.root.after(0, self.update_progress, 100, "Conversion done")
            messagebox.showinfo("Success", f"Saved: {os.path.basename(final)}")
        except Exception as e:
            self._handle_error(e, context="Conversion")
        finally:
            self._end_download()

    # ----------------- Search -----------------
    def search_videos(self):
        q = self.search_entry.get().strip()
        kind = self.search_type.get()
        if not q:
            return
        self.search_status_label.config(text="Searching...")
        self.current_page = 1

        def worker():
            try:
                if kind == "playlists":
                    results = self.search_service.search_playlists(q, limit=50)
                else:
                    results = self.search_service.search_videos(q, limit=50)
                self.search_results = results
                self.root.after(0, self._show_page)
            except Exception as e:
                self.root.after(
                    0,
                    lambda: self.search_status_label.config(text=f"Search error: {e}"),
                )
                self._handle_error(e, context="Search")

        threading.Thread(target=worker, daemon=True).start()

    def display_search_results(self, results):
        for w in self.results_frame.winfo_children():
            w.destroy()
        if not results:
            ttk.Label(self.results_frame, text="No results").pack()
            return
        for item in results:
            fr = ttk.Frame(self.results_frame, padding=4)
            fr.pack(fill=tk.X, pady=2)
            if isinstance(item, PlaylistItem):
                title_prefix = "[PLAYLIST] "
                duration_text = ""
            else:
                title_prefix = ""
                mins = item.duration // 60
                secs = item.duration % 60
                duration_text = f" | Duration: {mins}:{secs:02d}"
            ttk.Label(fr, text=title_prefix + item.title, font=("TkDefaultFont", 10, "bold")).pack(
                anchor=tk.W
            )
            meta = f"By: {item.uploader}{duration_text}"
            ttk.Label(fr, text=meta).pack(anchor=tk.W)
            btnf = ttk.Frame(fr)
            btnf.pack(anchor=tk.W, pady=2)
            if isinstance(item, VideoItem):
                ttk.Button(btnf, text="Video", command=lambda u=item.url: self._send_video(u)).pack(
                    side=tk.LEFT, padx=2
                )
                ttk.Button(btnf, text="Audio", command=lambda u=item.url: self._send_audio(u)).pack(
                    side=tk.LEFT, padx=2
                )
            else:
                ttk.Button(
                    btnf,
                    text="Playlist",
                    command=lambda u=item.url: self._send_playlist(u),
                ).pack(side=tk.LEFT, padx=2)
                ttk.Button(
                    btnf,
                    text="Pl. Audio",
                    command=lambda u=item.url: self._send_playlist_audio(u),
                ).pack(side=tk.LEFT, padx=2)

    def update_pagination(self, total_pages, current_page, total_results, start_idx, end_idx):
        for w in self.page_buttons_frame.winfo_children():
            w.destroy()

        def make_btn(p):
            style = "TButton" if p != current_page else "Active.TButton"
            b = ttk.Button(
                self.page_buttons_frame,
                text=str(p),
                command=lambda pg=p: self._goto_page(pg),
            )
            b.pack(side=tk.LEFT, padx=2)

        if total_pages <= 7:
            for p in range(1, total_pages + 1):
                make_btn(p)
        else:
            if current_page <= 3:
                for p in range(1, 6):
                    make_btn(p)
                    ttk.Label(self.page_buttons_frame, text="...").pack(side=tk.LEFT)
                    make_btn(total_pages)
            elif current_page >= total_pages - 2:
                make_btn(1)
                ttk.Label(self.page_buttons_frame, text="...").pack(side=tk.LEFT)
                for p in range(total_pages - 4, total_pages + 1):
                    make_btn(p)
            else:
                make_btn(1)
                ttk.Label(self.page_buttons_frame, text="...").pack(side=tk.LEFT)
                for p in range(current_page - 1, current_page + 2):
                    make_btn(p)
                ttk.Label(self.page_buttons_frame, text="...").pack(side=tk.LEFT)
                make_btn(total_pages)
        self.prev_page_btn.config(state="normal" if current_page > 1 else "disabled")
        self.next_page_btn.config(state="normal" if current_page < total_pages else "disabled")
        self.search_status_label.config(
            text=f"Showing {start_idx + 1}-{min(end_idx, total_results)} of {total_results}"
        )

    def _goto_page(self, page):
        self.current_page = page
        self._show_page()

    def next_page(self):
        total_pages = max(
            1,
            (len(self.search_results) + self.results_per_page - 1) // self.results_per_page,
        )
        if self.current_page < total_pages:
            self.current_page += 1
            self._show_page()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._show_page()

    def _show_page(self):
        start = (self.current_page - 1) * self.results_per_page
        end = start + self.results_per_page
        subset = self.search_results[start:end]
        self.display_search_results(subset)
        total = len(self.search_results)
        total_pages = max(1, (total + self.results_per_page - 1) // self.results_per_page)
        self.update_pagination(total_pages, self.current_page, total, start, end)
        self.search_status_label.config(text=f"Showing {start + 1}-{min(end, total)} of {total}")

    def _send_video(self, url):
        self.current_option.set("single_video")
        self.show_input_fields("single_video")
        self.video_url_entry.delete(0, tk.END)
        self.video_url_entry.insert(0, url)
        self.fetch_video_formats()

    def _send_audio(self, url):
        self.current_option.set("audio_only")
        self.show_input_fields("audio_only")
        self.audio_url_entry.delete(0, tk.END)
        self.audio_url_entry.insert(0, url)

    def _send_playlist(self, url):
        self.current_option.set("playlist")
        self.show_input_fields("playlist")
        self.playlist_url_entry.delete(0, tk.END)
        self.playlist_url_entry.insert(0, url)

    def _send_playlist_audio(self, url):
        self.current_option.set("playlist_audio")
        self.show_input_fields("playlist_audio")
        self.playlist_audio_url_entry.delete(0, tk.END)
        self.playlist_audio_url_entry.insert(0, url)

    # ----------------- Progress / Cancellation -----------------
    def update_progress(self, value=None, text=None):
        if value is not None:
            self.download_progress.set(value)
        if text is not None:
            self.status_label.config(text=text)
        self.root.update_idletasks()

    def _begin_download(self):
        self.cancel_requested = False
        self.cancel_button.config(state="normal")

    def _end_download(self):
        self.cancel_requested = False
        # Queue is source of truth — only clear UI when idle
        if not self.download_queue.has_active:
            self.cancel_button.config(state="disabled")
            self.update_progress(0, "Ready")
        else:
            self.update_progress(
                text=f"Queue: {self.download_queue.active_count} active, {self.download_queue.queued_count} queued"
            )

    def cancel_download(self):
        # Cancel via queue + service (Phase 1.2: concurrent)
        if self.download_queue.has_active:
            self.cancel_requested = True
            self.download_service.cancel()
            self.download_queue.cancel_all()
            self.update_progress(text="Cancelling...")

    # ----------------- Misc -----------------
    def browse_video_file(self):
        path = filedialog.askopenfilename(
            title="Select Video",
            filetypes=[("Video", "*.mp4 *.avi *.mkv *.mov"), ("All", "*.*")],
        )
        if path:
            self.video_file_entry.delete(0, tk.END)
            self.video_file_entry.insert(0, path)

    def toggle_dark_mode(self):
        if self.dark_mode.get():
            self.style.configure("TFrame", background="#333333")
            self.style.configure("TLabel", background="#333333", foreground="white")
        else:
            self.style.configure("TFrame", background="#f0f0f0")
            self.style.configure("TLabel", background="#f0f0f0", foreground="black")
        self.save_settings()

    def show_retry_settings(self):
        w = tk.Toplevel(self.root)
        w.title("Retry Settings")
        ttk.Label(w, text="Max Retries:").grid(row=0, column=0, padx=5, pady=5)
        spin = ttk.Spinbox(w, from_=1, to=10, textvariable=self.max_retries)
        spin.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(w, text="Save", command=lambda: (self.save_settings(), w.destroy())).grid(
            row=1, columnspan=2, pady=5
        )

    def select_download_directory(self):
        d = filedialog.askdirectory(
            title="Select Download Directory", initialdir=self.download_dir.get()
        )
        if d:
            self.download_dir.set(d)
            self.save_settings()
            messagebox.showinfo("Info", f"Download directory set to:\n{d}")

    def select_temp_directory(self):
        d = filedialog.askdirectory(title="Select Temp Directory", initialdir=self.temp_dir.get())
        if d:
            self.temp_dir.set(d)
            os.makedirs(d, exist_ok=True)
            self.save_settings()
            messagebox.showinfo("Info", f"Temporary directory set to:\n{d}")

    def show_about(self):
        messagebox.showinfo("About", "TubeGrabber\nYouTube downloader & converter.")

    def on_closing(self):
        self.save_settings()
        try:
            if hasattr(self, "download_queue"):
                self.download_queue.shutdown(wait=False)
        except Exception:
            pass
        self.root.destroy()

    # ----------------- Internal wiring -----------------
    def _wire_event_subscriptions(self):
        def on_progress(payload):
            if payload.get("status") == "downloading":
                total = payload.get("total_bytes") or payload.get("total_bytes_estimate")
                done = payload.get("downloaded_bytes", 0)
                percent = (done / total) * 100 if total else 0
                speed = payload.get("speed") or 0
                eta = payload.get("eta") or 0
                sp = (
                    f"{speed / 1024:.1f} KB/s"
                    if speed < 1024 * 1024
                    else f"{speed / (1024 * 1024):.2f} MB/s"
                )
                et = time.strftime("%M:%S", time.gmtime(eta)) if eta else "--:--"
                self.root.after(
                    0,
                    self.update_progress,
                    percent,
                    f"Downloading... {percent:.1f}% | {sp} | ETA {et}",
                )
            elif payload.get("status") == "postprocessing":
                self.root.after(0, self.update_progress, 100, "Post-processing...")

        def on_download_complete(path_str):
            self.root.after(0, self.update_progress, 100, "Completed")

        def on_conversion_complete(path_str):
            self.root.after(0, self.update_progress, 100, "Conversion completed")

        self.event_bus.subscribe("download.progress", on_progress)
        self.event_bus.subscribe("download.completed", on_download_complete)
        self.event_bus.subscribe("conversion.completed", on_conversion_complete)

    def _discover_ffmpeg(self) -> Path:
        """Attempt to locate an ffmpeg executable, fallback to 'ffmpeg'."""
        candidate_paths = [
            Path("ffmpeg_bundle/bin/ffmpeg.exe"),
            Path("ffmpeg/bin/ffmpeg.exe"),
            Path("ffmpeg.exe"),
        ]
        for p in candidate_paths:
            if p.exists():
                return p
        return Path("ffmpeg")  # rely on PATH

    def _health_check_async(self) -> None:
        """Run health check in a background thread to avoid UI freeze."""
        threading.Thread(target=self._health_check_worker, daemon=True).start()

    def _health_check_worker(self) -> None:
        ffmpeg_ok = True
        ffmpeg_path = self.ffmpeg_adapter.ffmpeg_bin
        if ffmpeg_path.is_absolute() and not ffmpeg_path.exists():
            ffmpeg_ok = False
        # Quick yt-dlp check: instantiate and list version, avoid network extraction
        ytdlp_ok = True
        try:
            with YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
                _ = ydl.params.get("progress_hooks", [])
        except Exception:
            ytdlp_ok = False
        if not ffmpeg_ok or not ytdlp_ok:
            msg = []
            if not ffmpeg_ok:
                msg.append("FFmpeg not found or inaccessible.")
            if not ytdlp_ok:
                msg.append("yt-dlp failed to initialize.")
            combined = "\n".join(msg)
            self.logger.warning("Health check warnings: %s", combined)
            self.root.after(0, lambda: messagebox.showwarning("Health Check", combined))

    def _handle_error(self, e: Exception, context: str = "") -> None:
        """Central mapping of exceptions to user-friendly messages."""
        self.logger.exception("%s error: %s", context or "Operation", e)
        if isinstance(e, DownloadCancelled):
            self.update_progress(0, "Cancelled")
            return
        if isinstance(e, ConversionError):
            message = "Conversion failed. Please verify FFmpeg is available."
        elif isinstance(e, ExtractionError):
            message = "Unable to fetch video info. Check the URL or network."
        elif isinstance(e, TubeGrabberError):
            message = str(e)
        else:
            message = f"{context} failed: {e}" if context else f"Operation failed: {e}"
        messagebox.showerror("Error", message)


__all__ = ["TubeGrabberApp"]
