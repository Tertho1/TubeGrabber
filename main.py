import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import subprocess
from yt_dlp import YoutubeDL
import threading
import time
import re
import json
import sys


def setup_environment():
    if getattr(sys, "frozen", False):
        base_path = os.path.dirname(sys.executable)
        os.environ["PATH"] = base_path + os.pathsep + os.environ["PATH"]
        temp_dir = os.path.join(base_path, "temp")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
        os.environ["TEMP"] = temp_dir
        os.environ["TMP"] = temp_dir
        log_file = os.path.join(base_path, "tubegrabber.log")


setup_environment()

DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "TubeGrabber")
TEMP_DIR = os.path.join(DEFAULT_DOWNLOAD_DIR, "temp")
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".tubegrabber")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")


def get_startup_info():
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        return startupinfo
    return None


class TubeGrabberApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TubeGrabber")
        try:
            if getattr(sys, "frozen", False):
                application_path = sys._MEIPASS
            else:
                application_path = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(application_path, "icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(default=icon_path)
                if os.name == "nt":
                    try:
                        import ctypes

                        myappid = "mycompany.tubegrabber.version1"
                        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                            myappid
                        )
                    except:
                        pass
            else:
                print("Icon not found at:", icon_path)
        except Exception as e:
            print(f"Could not set window icon: {e}")
        self.root.geometry("900x600")
        self.root.minsize(800, 500)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.configure_styles()
        self.create_main_containers()
        self.current_option = tk.StringVar()
        self.download_progress = tk.DoubleVar()
        self.dark_mode = tk.BooleanVar(value=False)
        self.max_retries = tk.IntVar(value=3)
        self.video_formats = []
        self.download_dir = tk.StringVar(value=DEFAULT_DOWNLOAD_DIR)
        self.temp_dir = tk.StringVar(value=TEMP_DIR)
        self.thumbnail_refs = []
        self.current_page = 1
        self.results_per_page = 20
        self.all_search_results = []
        self.current_search_query = ""
        self.active_download = False
        self.cancel_requested = False
        self.load_settings()
        self.create_option_buttons()
        self.create_input_area()
        self.create_progress_area()
        self.create_menu()
        self.current_option.set("search_videos")
        self.show_input_fields("search_videos")
        self.create_directory_structure()
        if self.dark_mode.get():
            self.toggle_dark_mode()

    def on_closing(self):
        self.save_settings()
        self.root.destroy()

    def create_directory_structure(self):
        os.makedirs(self.download_dir.get(), exist_ok=True)
        os.makedirs(self.temp_dir.get(), exist_ok=True)

    def configure_styles(self):
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("TButton", font=("Segoe UI", 10), padding=6)
        self.style.configure("TLabel", background="#f0f0f0", font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        self.style.configure("TEntry", padding=5)
        self.style.configure("TCombobox", padding=5)
        self.style.configure("Page.TButton", background="#4a7eff", foreground="white")
        self.style.map(
            "TButton",
            foreground=[("active", "black"), ("!disabled", "black")],
            background=[("active", "#d9d9d9"), ("!disabled", "#f0f0f0")],
        )
        self.style.map(
            "Page.TButton",
            foreground=[("active", "white"), ("!disabled", "white")],
            background=[("active", "#3a6eef"), ("!disabled", "#4a7eff")],
        )

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
        options_frame = ttk.LabelFrame(self.left_panel, text="Options", padding=10)
        options_frame.pack(fill=tk.BOTH, expand=True)
        options = [
            ("Search Videos", "search_videos"),
            ("Download Single Video", "single_video"),
            ("Download Audio Only", "audio_only"),
            ("Download Playlist", "playlist"),
            ("Playlist to Audio", "playlist_audio"),
            ("Convert Video to Audio", "convert_video"),
        ]
        for text, value in options:
            btn = ttk.Radiobutton(
                options_frame,
                text=text,
                variable=self.current_option,
                value=value,
                command=lambda v=value: self.show_input_fields(v),
            )
            btn.pack(anchor=tk.W, pady=5)

    def create_input_area(self):
        self.input_frame = ttk.Frame(self.right_panel)
        self.input_frame.pack(fill=tk.BOTH, expand=True)
        self.create_single_video_fields()
        self.create_audio_only_fields()
        self.create_playlist_fields()
        self.create_playlist_audio_fields()
        self.create_convert_video_fields()
        self.create_search_video_fields()

    def create_single_video_fields(self):
        self.single_video_frame = ttk.Frame(self.input_frame)
        ttk.Label(self.single_video_frame, text="YouTube Video URL:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.video_url_entry = ttk.Entry(self.single_video_frame, width=50)
        self.video_url_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(
            self.single_video_frame,
            text="Get Formats",
            command=self.fetch_video_formats,
        ).grid(row=0, column=2, padx=5)
        ttk.Label(self.single_video_frame, text="Select Format:").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        self.format_combobox = ttk.Combobox(
            self.single_video_frame, state="readonly", width=50
        )
        self.format_combobox.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Button(
            self.single_video_frame, text="Download", command=self.download_single_video
        ).grid(row=2, column=1, pady=10, sticky=tk.E)

    def create_audio_only_fields(self):
        self.audio_only_frame = ttk.Frame(self.input_frame)
        ttk.Label(self.audio_only_frame, text="YouTube Video URL:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.audio_url_entry = ttk.Entry(self.audio_only_frame, width=50)
        self.audio_url_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(
            self.audio_only_frame, text="Download Audio", command=self.download_audio
        ).grid(row=1, column=1, pady=10, sticky=tk.E)

    def create_playlist_fields(self):
        self.playlist_frame = ttk.Frame(self.input_frame)
        ttk.Label(self.playlist_frame, text="YouTube Playlist URL:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.playlist_url_entry = ttk.Entry(self.playlist_frame, width=50)
        self.playlist_url_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(self.playlist_frame, text="Quality:").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        self.playlist_quality_combobox = ttk.Combobox(
            self.playlist_frame, values=["Best", "Medium", "Low"], state="readonly"
        )
        self.playlist_quality_combobox.grid(
            row=1, column=1, padx=5, pady=5, sticky=tk.W
        )
        self.playlist_quality_combobox.set("Best")
        ttk.Button(
            self.playlist_frame,
            text="Download Playlist",
            command=self.download_playlist,
        ).grid(row=2, column=1, pady=10, sticky=tk.E)

    def create_playlist_audio_fields(self):
        self.playlist_audio_frame = ttk.Frame(self.input_frame)
        ttk.Label(self.playlist_audio_frame, text="YouTube Playlist URL:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.playlist_audio_url_entry = ttk.Entry(self.playlist_audio_frame, width=50)
        self.playlist_audio_url_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(
            self.playlist_audio_frame,
            text="Download Playlist as Audio",
            command=self.download_playlist_audio,
        ).grid(row=1, column=1, pady=10, sticky=tk.E)

    def create_convert_video_fields(self):
        self.convert_video_frame = ttk.Frame(self.input_frame)
        ttk.Label(self.convert_video_frame, text="Video File:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.video_file_entry = ttk.Entry(self.convert_video_frame, width=50)
        self.video_file_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(
            self.convert_video_frame, text="Browse", command=self.browse_video_file
        ).grid(row=0, column=2, padx=5)
        ttk.Button(
            self.convert_video_frame,
            text="Convert to Audio",
            command=self.convert_video,
        ).grid(row=1, column=1, pady=10, sticky=tk.E)

    def create_search_video_fields(self):
        self.search_video_frame = ttk.Frame(self.input_frame)
        search_input_frame = ttk.Frame(self.search_video_frame)
        search_input_frame.pack(fill=tk.X, pady=10)
        self.search_type = tk.StringVar(value="videos")
        search_type_frame = ttk.Frame(search_input_frame)
        search_type_frame.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Radiobutton(
            search_type_frame, text="Videos", variable=self.search_type, value="videos"
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Radiobutton(
            search_type_frame,
            text="Playlists",
            variable=self.search_type,
            value="playlists",
        ).pack(side=tk.LEFT)
        ttk.Label(search_input_frame, text="Search:").grid(
            row=0, column=1, sticky=tk.W, pady=5
        )
        self.search_entry = ttk.Entry(search_input_frame, width=50)
        self.search_entry.grid(row=0, column=2, padx=5, pady=5)
        self.search_entry.bind("<Return>", lambda event: self.search_videos())
        ttk.Button(search_input_frame, text="Search", command=self.search_videos).grid(
            row=0, column=3, padx=5
        )
        self.results_container = ttk.LabelFrame(
            self.search_video_frame, text="Search Results"
        )
        self.results_container.pack(fill=tk.BOTH, expand=True, pady=5)
        self.results_frame = ttk.Frame(self.results_container)
        self.results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.pagination_frame = ttk.Frame(self.search_video_frame)
        self.pagination_frame.pack(fill=tk.X, pady=5)
        pagination_center = ttk.Frame(self.pagination_frame)
        pagination_center.pack(anchor=tk.CENTER)
        self.prev_page_btn = ttk.Button(
            pagination_center,
            text="←",
            width=3,
            command=self.show_previous_page,
            state="disabled",
        )
        self.prev_page_btn.pack(side=tk.LEFT, padx=(0, 2))
        self.page_buttons_frame = ttk.Frame(pagination_center)
        self.page_buttons_frame.pack(side=tk.LEFT)
        self.next_page_btn = ttk.Button(
            pagination_center,
            text="→",
            width=3,
            command=self.show_next_page,
            state="disabled",
        )
        self.next_page_btn.pack(side=tk.LEFT, padx=(2, 0))
        self.search_status_label = ttk.Label(self.search_video_frame, text="Ready")
        self.search_status_label.pack(fill=tk.X, pady=5)

    def create_progress_area(self):
        progress_frame = ttk.Frame(self.progress_frame)
        progress_frame.pack(fill=tk.X, anchor=tk.W)
        ttk.Label(progress_frame, text="Progress:").pack(side=tk.LEFT)
        buttons_frame = ttk.Frame(self.progress_frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 5), anchor=tk.E)
        self.cancel_button = ttk.Button(
            buttons_frame,
            text="Cancel Download",
            command=self.cancel_download,
            state="disabled",
        )
        self.cancel_button.pack(side=tk.RIGHT, padx=5)
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
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        downloads_menu = tk.Menu(file_menu, tearoff=0)
        downloads_menu.add_command(
            label="Set Download Directory", command=self.select_download_directory
        )
        downloads_menu.add_command(
            label="Set Temp Directory", command=self.select_temp_directory
        )
        file_menu.add_cascade(label="Downloads", menu=downloads_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_checkbutton(
            label="Dark Mode", variable=self.dark_mode, command=self.toggle_dark_mode
        )
        settings_menu.add_separator()
        settings_menu.add_command(
            label="Retry Settings", command=self.show_retry_settings
        )
        menubar.add_cascade(label="Settings", menu=settings_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def select_download_directory(self):
        directory = filedialog.askdirectory(
            title="Select Download Directory", initialdir=self.download_dir.get()
        )
        if directory:
            self.download_dir.set(directory)
            self.save_settings()
            messagebox.showinfo("Info", f"Download directory set to:\n{directory}")

    def select_temp_directory(self):
        directory = filedialog.askdirectory(
            title="Select Temporary Directory", initialdir=self.temp_dir.get()
        )
        if directory:
            self.temp_dir.set(directory)
            os.makedirs(directory, exist_ok=True)
            self.save_settings()
            messagebox.showinfo("Info", f"Temporary directory set to:\n{directory}")

    def show_retry_settings(self):
        retry_window = tk.Toplevel(self.root)
        retry_window.title("Retry Settings")
        ttk.Label(retry_window, text="Max Retry Attempts:").grid(
            row=0, column=0, padx=5, pady=5
        )
        retry_spin = ttk.Spinbox(
            retry_window, from_=1, to=10, textvariable=self.max_retries
        )
        retry_spin.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(
            retry_window,
            text="Save",
            command=lambda: [self.save_settings(), retry_window.destroy()],
        ).grid(row=1, columnspan=2, pady=5)

    def show_input_fields(self, option):
        for frame in [
            self.single_video_frame,
            self.audio_only_frame,
            self.playlist_frame,
            self.playlist_audio_frame,
            self.convert_video_frame,
            self.search_video_frame,
        ]:
            frame.pack_forget()
        if option == "single_video":
            self.single_video_frame.pack(fill=tk.BOTH, expand=True)
        elif option == "audio_only":
            self.audio_only_frame.pack(fill=tk.BOTH, expand=True)
        elif option == "playlist":
            self.playlist_frame.pack(fill=tk.BOTH, expand=True)
        elif option == "playlist_audio":
            self.playlist_audio_frame.pack(fill=tk.BOTH, expand=True)
        elif option == "convert_video":
            self.convert_video_frame.pack(fill=tk.BOTH, expand=True)
        elif option == "search_videos":
            self.search_video_frame.pack(fill=tk.BOTH, expand=True)

    def toggle_dark_mode(self):
        if self.dark_mode.get():
            self.style.theme_use("alt")
            self.style.configure("TFrame", background="#333333")
            self.style.configure("TLabel", background="#333333", foreground="white")
        else:
            self.style.theme_use("clam")
            self.style.configure("TFrame", background="#f0f0f0")
            self.style.configure("TLabel", background="#f0f0f0", foreground="black")
        self.save_settings()

    def browse_video_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[
                ("Video Files", "*.mp4 *.avi *.mkv *.mov"),
                ("All Files", "*.*"),
            ],
        )
        if file_path:
            self.video_file_entry.delete(0, tk.END)
            self.video_file_entry.insert(0, file_path)

    def show_about(self):
        messagebox.showinfo(
            "About TubeGrabber",
            "TubeGrabber v2.0\n\n"
            "A YouTube video and audio downloader with playlist support.\n"
            "Developed with Python and Tkinter.",
        )

    def update_progress(self, value=None, text=None):
        if value is not None:
            self.download_progress.set(value)
        if text is not None:
            self.status_label.config(text=text)
        self.root.update_idletasks()

    def fetch_video_formats(self):
        url = self.video_url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a valid YouTube URL.")
            return
        try:
            self.update_progress(text="Fetching available formats...")
            ydl_opts = {"quiet": True}
            with YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                formats = info_dict.get("formats", [])
                video_formats = [fmt for fmt in formats if fmt.get("vcodec") != "none"]
                if not video_formats:
                    messagebox.showerror(
                        "Error", "No video formats available for this URL."
                    )
                    return
                self.video_formats = video_formats
                options = [
                    f"{fmt['format_id']}: {fmt.get('format_note', 'Unknown')} "
                    f"({fmt.get('ext', 'Unknown')}) - {fmt.get('resolution', 'N/A')}"
                    for fmt in video_formats
                ]
                self.format_combobox["values"] = options
                self.format_combobox.current(0)
                self.update_progress(text="Formats fetched successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch formats: {str(e)}")
            self.update_progress(text="Ready")

    def download_with_retry(self, func, *args, **kwargs):
        retries = self.max_retries.get()
        for attempt in range(1, retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if str(e) == "Download cancelled by user":
                    raise e
                if attempt < retries:
                    self.update_progress(text=f"Retrying ({attempt}/{retries})...")
                    time.sleep(2**attempt)
                else:
                    raise e

    def download_single_video(self):
        url = self.video_url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL")
            return
        try:
            index = self.format_combobox.current()
            if index < 0:
                format_id = None
            else:
                format_id = self.video_formats[index]["format_id"]
        except (AttributeError, IndexError):
            format_id = None
        threading.Thread(
            target=self._download_single_video_thread,
            args=(url, format_id),
            daemon=True,
        ).start()

    def _download_single_video_thread(self, url, format_id):
        try:
            self.active_download = True
            self.cancel_requested = False
            self.root.after(0, lambda: self.cancel_button.config(state="normal"))

            def progress_hook(d):
                if self.cancel_requested:
                    raise Exception("Download cancelled by user")
                if d["status"] == "downloading":
                    if d.get("info_dict", {}).get("_type") == "audio":
                        return
                    total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
                    downloaded_bytes = d.get("downloaded_bytes")
                    speed = d.get("speed")
                    eta = d.get("eta")
                    if total_bytes and downloaded_bytes and total_bytes > 0:
                        percent = (downloaded_bytes / total_bytes) * 100
                    else:
                        percent = 0
                    speed_str = "N/A"
                    if speed:
                        if speed > 1024 * 1024:
                            speed_str = f"{speed/(1024*1024):.2f} MB/s"
                        else:
                            speed_str = f"{speed/1024:.2f} KB/s"
                    eta_str = (
                        time.strftime("%M:%S", time.gmtime(eta))
                        if eta
                        else "Unknown ETA"
                    )
                    filename = os.path.basename(d.get("filename", "item"))
                    self.root.after(
                        0,
                        self.update_progress,
                        percent,
                        f"Downloading Video: {filename}\n"
                        f"Completion: {percent:.1f}% | Speed: {speed_str} | ETA: {eta_str}",
                    )
                elif d["status"] == "postprocessing":
                    self.root.after(
                        0,
                        self.update_progress,
                        100,
                        "Merging audio and video streams...",
                    )

            self.update_progress(0, "Starting video download...")
            filename = self.download_with_retry(
                self.download_video,
                url,
                format_id=format_id,
                progress_hook=progress_hook,
            )
            self.update_progress(100, "Download complete!")
            messagebox.showinfo("Success", f"Video downloaded:\n{filename}")
        except Exception as e:
            if str(e) == "Download cancelled by user":
                self.update_progress(0, "Download cancelled")
            else:
                messagebox.showerror("Error", f"Failed to download video:\n{str(e)}")
        finally:
            self.active_download = False
            self.cancel_requested = False
            self.root.after(0, lambda: self.cancel_button.config(state="disabled"))
            self.update_progress(0, "Ready")

    def _download_playlist_thread(self, url, quality, audio_only):
        try:
            self.active_download = True
            self.cancel_requested = False
            self.root.after(0, lambda: self.cancel_button.config(state="normal"))
            self.update_progress(0, "Analyzing playlist...")
            try:
                with YoutubeDL(
                    {"quiet": True, "extract_flat": True, "ignoreerrors": True}
                ) as ydl:
                    info = ydl.extract_info(url, download=False)
                    playlist_title = info.get("title", "Unknown Playlist")
                    total_items = len([e for e in info.get("entries", []) if e])
                    self.update_progress(
                        0, f"Found {total_items} videos in '{playlist_title}'"
                    )
            except Exception as e:
                self.update_progress(0, "Couldn't determine playlist size: " + str(e))
                total_items = 0
                playlist_title = "Unknown Playlist"
            current_state = {
                "total_items": total_items,
                "current_item": 0,
                "current_item_title": "",
                "completed_items": 0,
                "failed_items": 0,
                "item_progress": 0,
            }

            def progress_hook(d):
                if self.cancel_requested:
                    raise Exception("Download cancelled by user")
                status = d.get("status")
                filename = os.path.basename(d.get("filename", "Unknown"))
                info_dict = d.get("info_dict", {})
                is_main_file = True
                if (
                    info_dict.get("_type") == "thumbnail"
                    or info_dict.get("ext") == "jpg"
                ):
                    is_main_file = False
                if not audio_only:
                    if (
                        info_dict.get("acodec") != "none"
                        and info_dict.get("vcodec") == "none"
                    ) or "audio only" in info_dict.get("format", "").lower():
                        is_main_file = False
                if status == "downloading" and is_main_file:
                    playlist_index = info_dict.get("playlist_index", 0)
                    if playlist_index > 1 and current_state["current_item"] == 0:
                        display_index = 1
                    else:
                        display_index = playlist_index
                    if playlist_index != current_state["current_item"]:
                        current_state["current_item"] = playlist_index
                        current_state["item_progress"] = 0
                        current_state["current_item_title"] = info_dict.get(
                            "title", filename
                        )
                    total_bytes = d.get("total_bytes") or d.get(
                        "total_bytes_estimate", 0
                    )
                    downloaded_bytes = d.get("downloaded_bytes", 0)
                    fragment_index = d.get("fragment_index", 0)
                    fragment_count = d.get("fragment_count", 0)
                    if total_bytes and downloaded_bytes:
                        current_state["item_progress"] = (
                            downloaded_bytes / total_bytes
                        ) * 100
                    elif fragment_count and fragment_index:
                        current_state["item_progress"] = (
                            fragment_index / fragment_count
                        ) * 100
                    if current_state["total_items"] > 0:
                        overall_progress = (
                            current_state["completed_items"]
                            / current_state["total_items"]
                        ) * 100 + (
                            current_state["item_progress"]
                            / current_state["total_items"]
                        )
                    else:
                        overall_progress = current_state["item_progress"]
                    overall_progress = min(max(overall_progress, 0), 100)
                    speed = d.get("speed", 0)
                    eta = d.get("eta", 0)
                    speed_str = "N/A"
                    if speed:
                        if speed > 1024 * 1024:
                            speed_str = f"{speed/(1024*1024):.2f} MB/s"
                        else:
                            speed_str = f"{speed/1024:.2f} KB/s"
                    eta_str = "N/A"
                    if eta:
                        eta_str = (
                            time.strftime("%H:%M:%S", time.gmtime(eta))
                            if eta > 3600
                            else time.strftime("%M:%S", time.gmtime(eta))
                        )
                    status_text = (
                        f"Downloading {audio_only and 'Audio' or 'Video'} {display_index} of {current_state['total_items'] or '?'}: "
                        f"{current_state['current_item_title']}\n"
                        f"Completion: {overall_progress:.1f}% | Speed: {speed_str} | ETA: {eta_str}"
                    )
                    self.root.after(
                        0, self.update_progress, overall_progress, status_text
                    )
                elif status == "finished" and is_main_file:
                    current_state["completed_items"] += 1
                    if current_state["total_items"] > 0:
                        progress = (
                            current_state["completed_items"]
                            / current_state["total_items"]
                        ) * 100
                    else:
                        progress = 0
                    self.root.after(
                        0,
                        self.update_progress,
                        progress,
                        f"Completed {current_state['completed_items']} items"
                        + (
                            f" of {current_state['total_items']}"
                            if current_state["total_items"]
                            else ""
                        ),
                    )
                elif status == "error":
                    if is_main_file:
                        current_state["failed_items"] += 1
                        error_msg = d.get("error", "Unknown error")
                        print(f"Error downloading {filename}: {error_msg}")

            self.update_progress(0, "Starting playlist download...")
            self.download_with_retry(
                download_playlist,
                url,
                quality=quality,
                audio_only=audio_only,
                output_path=self.download_dir.get(),
                progress_hook=progress_hook,
                cancel_check=lambda: self.cancel_requested,
            )
            self.update_progress(100, "Playlist download complete!")
            completed = current_state["completed_items"]
            failed = current_state["failed_items"]
            total = current_state["total_items"] or (completed + failed)
            messagebox.showinfo(
                "Download Complete",
                f"Playlist {playlist_title} download finished\n"
                f"Successfully downloaded: {completed}\n"
                f"Failed: {total-completed}\n"
                f"Total items: {total}",
            )
        except Exception as e:
            if str(e) == "Download cancelled by user":
                self.update_progress(0, "Download cancelled")
            else:
                messagebox.showerror("Error", f"Failed to download playlist:\n{str(e)}")
        finally:
            self.active_download = False
            self.cancel_requested = False
            self.root.after(0, lambda: self.cancel_button.config(state="disabled"))
            self.update_progress(0, "Ready")

    def download_audio(self):
        url = self.audio_url_entry.get().strip()
        threading.Thread(
            target=self._download_audio_thread, args=(url,), daemon=True
        ).start()

    def _download_audio_thread(self, url):
        try:
            self.active_download = True
            self.cancel_requested = False
            self.root.after(0, lambda: self.cancel_button.config(state="normal"))

            def progress_hook(d):
                if self.cancel_requested:
                    raise Exception("Download cancelled by user")
                if d["status"] == "downloading":
                    total_bytes = d.get("total_bytes") or d.get(
                        "total_bytes_estimate", 0
                    )
                    downloaded_bytes = d.get("downloaded_bytes", 0)
                    speed = d.get("speed", 0)
                    eta = d.get("eta", 0)
                    filename = os.path.basename(d.get("filename", "Unknown"))
                    title = d.get("info_dict", {}).get("title", filename)
                    if total_bytes and downloaded_bytes and total_bytes > 0:
                        percent = (downloaded_bytes / total_bytes) * 100
                    else:
                        percent = 0
                    speed_str = "Unknown speed"
                    if speed:
                        if speed > 1024 * 1024:
                            speed_str = f"{speed/(1024**2):.2f} MB/s"
                        else:
                            speed_str = f"{speed/1024:.2f} KB/s"
                    eta_str = (
                        time.strftime("%M:%S", time.gmtime(eta))
                        if eta
                        else "Unknown ETA"
                    )
                    self.root.after(
                        0,
                        self.update_progress,
                        percent,
                        f"Downloading Audio: {title}\n"
                        f"Completion: {percent:.1f}% | Speed: {speed_str} | ETA: {eta_str}",
                    )
                elif d["status"] == "postprocessing":
                    self.root.after(
                        0,
                        self.update_progress,
                        95,
                        f"Extracting audio and converting to mp3...",
                    )

            self.update_progress(0, "Starting audio download...")
            filename = self.download_with_retry(
                download_audio,
                url,
                output_path=self.download_dir.get(),
                progress_hook=progress_hook,
            )
            self.update_progress(100, "Audio download complete!")
            messagebox.showinfo("Success", f"Audio downloaded:\n{filename}")
        except Exception as e:
            if str(e) == "Download cancelled by user":
                self.update_progress(0, "Download cancelled")
            else:
                messagebox.showerror("Error", f"Failed to download audio:\n{str(e)}")
        finally:
            self.active_download = False
            self.cancel_requested = False
            self.root.after(0, lambda: self.cancel_button.config(state="disabled"))
            self.update_progress(0, "Ready")

    def download_playlist(self):
        url = self.playlist_url_entry.get().strip()
        quality = self.playlist_quality_combobox.get().lower()
        threading.Thread(
            target=self._download_playlist_thread,
            args=(url, quality, False),
            daemon=True,
        ).start()

    def download_playlist_audio(self):
        url = self.playlist_audio_url_entry.get().strip()
        threading.Thread(
            target=self._download_playlist_thread, args=(url, "best", True), daemon=True
        ).start()

    def convert_video(self):
        video_path = self.video_file_entry.get().strip()
        threading.Thread(
            target=self._convert_video_thread, args=(video_path,), daemon=True
        ).start()

    def _convert_video_thread(self, path):
        try:

            def progress_hook(progress, text):
                self.root.after(0, self.update_progress, progress, text)

            self.update_progress(0, "Starting conversion...")
            filename = self.download_with_retry(
                convert_video_to_audio,
                path,
                output_path=self.download_dir.get(),
                progress_hook=progress_hook,
            )
            self.update_progress(100, "Conversion complete!")
            messagebox.showinfo("Success", f"Converted to audio:\n{filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Conversion failed:\n{str(e)}")
        finally:
            self.update_progress(0, "Ready")

    def get_temp_dir(self):
        return self.temp_dir.get()

    def download_video(self, url, output_path=None, format_id=None, progress_hook=None):
        try:
            if output_path is None:
                output_path = self.download_dir.get()
            temp_dir = self.get_temp_dir()
            ydl_opts = {
                "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
                "format": format_id or "best",
                "progress_hooks": [progress_hook] if progress_hook else [],
                "retries": 3,
                "fragment_retries": 3,
                "skip_unavailable_fragments": True,
            }
            if format_id and not format_has_audio(format_id, url):
                ydl_opts["format"] += "+bestaudio"
                ydl_opts["merge_output_format"] = "mp4"
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                temp_file = ydl.prepare_filename(info)
            final_file = move_to_final_location(temp_file, output_path)
            return final_file
        except Exception as e:
            if "temp_file" in locals() and os.path.exists(temp_file):
                os.remove(temp_file)
            if str(e) == "Download cancelled by user":
                self._cleanup_temp_files()
            raise RuntimeError(f"Video download failed: {str(e)}")

    def load_settings(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    settings = json.load(f)
                    if "download_dir" in settings:
                        self.download_dir.set(settings["download_dir"])
                    if "temp_dir" in settings:
                        self.temp_dir.set(settings["temp_dir"])
                    if "dark_mode" in settings:
                        self.dark_mode.set(settings["dark_mode"])
                    if "max_retries" in settings:
                        self.max_retries.set(settings["max_retries"])
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_settings(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            settings = {
                "download_dir": self.download_dir.get(),
                "temp_dir": self.temp_dir.get(),
                "dark_mode": self.dark_mode.get(),
                "max_retries": self.max_retries.get(),
            }
            with open(CONFIG_FILE, "w") as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings: {str(e)}")

    def search_videos(self):
        query = self.search_entry.get()
        if not query:
            messagebox.showerror("Error", "Please enter a search query.")
            return
        self.current_search_query = query
        self.current_page = 1
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        self.search_status_label.config(text="Searching...")
        self.root.update()
        search_count = 100
        search_type = self.search_type.get()
        threading.Thread(
            target=self._search_thread,
            args=(query, search_count, search_type),
            daemon=True,
        ).start()

    def _search_thread(self, query, search_count, search_type):
        try:
            from urllib.parse import quote_plus

            if getattr(sys, "frozen", False):
                ytdlp_path = os.path.join(sys._MEIPASS, "yt-dlp.exe")
            else:
                ytdlp_path = os.path.join(sys.prefix, "Scripts", "yt-dlp.exe")
            self.all_search_results = []
            if search_type == "playlists":
                search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp=EgIQAw%253D%253D"
                self.root.after(
                    0,
                    lambda: self.search_status_label.config(
                        text="Searching for playlists..."
                    ),
                )
            else:
                search_url = (
                    f"https://www.youtube.com/results?search_query={quote_plus(query)}"
                )
                self.root.after(
                    0,
                    lambda: self.search_status_label.config(
                        text="Searching for videos..."
                    ),
                )
            command = [
                ytdlp_path,
                "--dump-json",
                "--flat-playlist",
                search_url,
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                startupinfo=get_startup_info(),
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        try:
                            video_data = json.loads(line)
                            playlist_id = None
                            if search_type == "playlists":
                                is_playlist = True
                                playlist_id = video_data.get("id") or video_data.get(
                                    "playlist_id", ""
                                )
                                if not playlist_id and "url" in video_data:
                                    import re

                                    match = re.search(
                                        r"list=([^&]+)", video_data["url"]
                                    )
                                    if match:
                                        playlist_id = match.group(1)
                                if not playlist_id and "webpage_url" in video_data:
                                    import re

                                    match = re.search(
                                        r"list=([^&]+)", video_data["webpage_url"]
                                    )
                                    if match:
                                        playlist_id = match.group(1)
                                if playlist_id:
                                    thumbnail_url = video_data.get("thumbnail", "")
                                    if not thumbnail_url and "thumbnails" in video_data:
                                        if (
                                            isinstance(video_data["thumbnails"], list)
                                            and len(video_data["thumbnails"]) > 0
                                        ):
                                            thumbnail_url = video_data["thumbnails"][
                                                0
                                            ].get("url", "")
                                    self.all_search_results.append(
                                        {
                                            "type": "playlist",
                                            "title": video_data.get(
                                                "title", "Unknown Playlist"
                                            ),
                                            "id": playlist_id,
                                            "url": f"https://www.youtube.com/playlist?list={playlist_id}",
                                            "thumbnail": thumbnail_url,
                                            "uploader": video_data.get(
                                                "uploader", "Unknown"
                                            ),
                                            "description": (
                                                video_data.get("description", "")[:100]
                                                + "..."
                                                if video_data.get("description")
                                                else ""
                                            ),
                                        }
                                    )
                            elif search_type == "videos":
                                if video_data.get(
                                    "id"
                                ) and "watch?v=" in video_data.get("webpage_url", ""):
                                    thumbnail_url = video_data.get("thumbnail", "")
                                    if not thumbnail_url and "thumbnails" in video_data:
                                        if (
                                            isinstance(video_data["thumbnails"], list)
                                            and len(video_data["thumbnails"]) > 0
                                        ):
                                            thumbnail_url = video_data["thumbnails"][
                                                0
                                            ].get("url", "")
                                    self.all_search_results.append(
                                        {
                                            "type": "video",
                                            "title": video_data.get(
                                                "title", "Unknown Title"
                                            ),
                                            "id": video_data.get("id", ""),
                                            "url": f"https://www.youtube.com/watch?v={video_data.get('id', '')}",
                                            "thumbnail": thumbnail_url,
                                            "duration": video_data.get("duration", 0),
                                            "uploader": video_data.get(
                                                "uploader", "Unknown"
                                            ),
                                            "description": (
                                                video_data.get("description", "")[:100]
                                                + "..."
                                                if video_data.get("description")
                                                else ""
                                            ),
                                        }
                                    )
                        except json.JSONDecodeError:
                            continue
                self.root.after(0, self.show_search_page)
            else:
                self.root.after(
                    0,
                    lambda: self.search_status_label.config(
                        text="Search failed. Please try again."
                    ),
                )
        except Exception as e:
            print(f"Search error: {str(e)}")
            self.root.after(
                0,
                lambda: messagebox.showerror("Error", f"Failed to search: {str(e)}"),
            )
            self.root.after(0, lambda: self.search_status_label.config(text="Ready"))

    def _display_search_results(self, results):
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        if not results:
            self.search_status_label.config(text="No results found")
            return
        canvas = tk.Canvas(self.results_frame)
        scrollbar = ttk.Scrollbar(
            self.results_frame, orient="vertical", command=canvas.yview
        )
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas_window = canvas.create_window(
            (0, 0), window=scrollable_frame, anchor="nw"
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def configure_canvas(event):
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)

        canvas.bind("<Configure>", configure_canvas)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.thumbnail_refs = []
        self.style.configure("Video.TFrame", relief="solid", borderwidth=1)
        self.style.configure(
            "Playlist.TFrame", relief="solid", borderwidth=1, background="#e6e6ff"
        )
        for i, item in enumerate(results):
            if item["type"] == "video":
                item_frame = ttk.Frame(
                    scrollable_frame, padding=5, style="Video.TFrame"
                )
            else:
                item_frame = ttk.Frame(
                    scrollable_frame, padding=5, style="Playlist.TFrame"
                )
            item_frame.pack(fill="x", padx=5, pady=5)
            item_frame.item_data = item
            try:
                import requests
                from PIL import Image, ImageTk
                from io import BytesIO

                response = requests.get(item["thumbnail"])
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    img = img.resize((120, 68), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.thumbnail_refs.append(photo)
                    thumbnail_label = ttk.Label(item_frame, image=photo, cursor="hand2")
                    thumbnail_label.image = photo
                    thumbnail_label.pack(side="left", padx=5)
                    thumbnail_label.bind(
                        "<Button-1>", lambda e, i=item: self._handle_result_click(i)
                    )
                else:
                    placeholder = ttk.Label(
                        item_frame,
                        text="No Thumbnail",
                        width=15,
                        padding=10,
                        cursor="hand2",
                    )
                    placeholder.pack(side="left", padx=5)
                    placeholder.bind(
                        "<Button-1>", lambda e, i=item: self._handle_result_click(i)
                    )
            except Exception:
                placeholder = ttk.Label(
                    item_frame,
                    text="No Thumbnail",
                    width=15,
                    padding=10,
                    cursor="hand2",
                )
                placeholder.pack(side="left", padx=5)
                placeholder.bind(
                    "<Button-1>", lambda e, i=item: self._handle_result_click(i)
                )
            info_frame = ttk.Frame(item_frame)
            info_frame.pack(side="left", fill="both", expand=True, padx=5)
            info_frame.bind(
                "<Button-1>", lambda e, i=item: self._handle_result_click(i)
            )
            title_text = (
                f"{'[PLAYLIST] ' if item['type'] == 'playlist' else ''}{item['title']}"
            )
            title_label = ttk.Label(
                info_frame,
                text=title_text,
                wraplength=500,
                font=("TkDefaultFont", 10, "bold"),
                cursor="hand2",
            )
            title_label.pack(anchor="w")
            title_label.bind(
                "<Button-1>", lambda e, i=item: self._handle_result_click(i)
            )
            if item["type"] == "video":
                duration = item.get("duration", 0)
                if duration is None:
                    duration = 0
                try:
                    duration_mins = int(duration) // 60
                    duration_secs = int(duration) % 60
                    details_text = f"By: {item['uploader']} | Duration: {duration_mins}:{duration_secs:02d}"
                except (ValueError, TypeError):
                    details_text = f"By: {item['uploader']}"
            else:
                details_text = f"By: {item['uploader']}"
            details_label = ttk.Label(info_frame, text=details_text, cursor="hand2")
            details_label.pack(anchor="w")
            details_label.bind(
                "<Button-1>", lambda e, i=item: self._handle_result_click(i)
            )
            if item.get("description"):
                desc_label = ttk.Label(
                    info_frame, text=item["description"], wraplength=500
                )
                desc_label.pack(anchor="w", pady=(5, 0))
            buttons_frame = ttk.Frame(item_frame)
            buttons_frame.pack(side="right", padx=5)
            if item["type"] == "video":
                ttk.Button(
                    buttons_frame,
                    text="Download Video",
                    command=lambda i=item: self._send_to_video_download(i["url"]),
                ).pack(pady=2)
                ttk.Button(
                    buttons_frame,
                    text="Download Audio",
                    command=lambda i=item: self._send_to_audio_download(i["url"]),
                ).pack(pady=2)
            else:
                ttk.Button(
                    buttons_frame,
                    text="Download Playlist",
                    command=lambda i=item: self._send_to_playlist_download(i["url"]),
                ).pack(pady=2)
                ttk.Button(
                    buttons_frame,
                    text="Download as Audio",
                    command=lambda i=item: self._send_to_playlist_audio_download(
                        i["url"]
                    ),
                ).pack(pady=2)
        self.search_status_label.config(text=f"Found {len(results)} results")

    def _handle_result_click(self, item):
        if item["type"] == "video":
            self._send_to_video_download(item["url"])
        else:
            self._send_to_playlist_download(item["url"])

    def _send_to_video_download(self, url):
        self.current_option.set("single_video")
        self.show_input_fields("single_video")
        self.video_url_entry.delete(0, tk.END)
        self.video_url_entry.insert(0, url)
        self.fetch_video_formats()

    def _send_to_audio_download(self, url):
        self.current_option.set("audio_only")
        self.show_input_fields("audio_only")
        self.audio_url_entry.delete(0, tk.END)
        self.audio_url_entry.insert(0, url)

    def _send_to_playlist_download(self, url):
        self.current_option.set("playlist")
        self.show_input_fields("playlist")
        self.playlist_url_entry.delete(0, tk.END)
        self.playlist_url_entry.insert(0, url)

    def _send_to_playlist_audio_download(self, url):
        self.current_option.set("playlist_audio")
        self.show_input_fields("playlist_audio")
        self.playlist_audio_url_entry.delete(0, tk.END)
        self.playlist_audio_url_entry.insert(0, url)

    def _create_page_button(self, page_number):
        is_current = page_number == self.current_page
        style = "Page.TButton" if is_current else "TButton"
        width = 2 if page_number < 10 else 3
        btn = ttk.Button(
            self.page_buttons_frame,
            text=str(page_number),
            width=width,
            command=lambda: self._go_to_page(page_number),
            style=style,
        )
        btn.pack(side=tk.LEFT, padx=2)

    def _go_to_page(self, page_number):
        self.current_page = page_number
        self.show_search_page()

    def show_search_page(self):
        start_idx = (self.current_page - 1) * self.results_per_page
        end_idx = start_idx + self.results_per_page
        current_page_results = self.all_search_results[start_idx:end_idx]
        self._display_search_results(current_page_results)
        total_pages = max(
            1,
            (len(self.all_search_results) + self.results_per_page - 1)
            // self.results_per_page,
        )
        for widget in self.page_buttons_frame.winfo_children():
            widget.destroy()
        if total_pages <= 7:
            for i in range(1, total_pages + 1):
                self._create_page_button(i)
        else:
            if self.current_page <= 3:
                for i in range(1, 6):
                    self._create_page_button(i)
                ttk.Label(self.page_buttons_frame, text="...").pack(
                    side=tk.LEFT, padx=2
                )
                self._create_page_button(total_pages)
            elif self.current_page >= total_pages - 2:
                self._create_page_button(1)
                ttk.Label(self.page_buttons_frame, text="...").pack(
                    side=tk.LEFT, padx=2
                )
                for i in range(total_pages - 4, total_pages + 1):
                    self._create_page_button(i)
            else:
                self._create_page_button(1)
                ttk.Label(self.page_buttons_frame, text="...").pack(
                    side=tk.LEFT, padx=2
                )
                for i in range(self.current_page - 1, self.current_page + 2):
                    self._create_page_button(i)
                ttk.Label(self.page_buttons_frame, text="...").pack(
                    side=tk.LEFT, padx=2
                )
                self._create_page_button(total_pages)
        self.prev_page_btn.config(
            state="normal" if self.current_page > 1 else "disabled"
        )
        self.next_page_btn.config(
            state="normal" if self.current_page < total_pages else "disabled"
        )
        total_results = len(self.all_search_results)
        showing_start = start_idx + 1 if total_results > 0 else 0
        showing_end = min(end_idx, total_results)
        self.search_status_label.config(
            text=f"Showing {showing_start}-{showing_end} of {total_results} results"
        )

    def show_next_page(self):
        total_pages = (
            len(self.all_search_results) + self.results_per_page - 1
        ) // self.results_per_page
        if self.current_page < total_pages:
            self.current_page += 1
            self.show_search_page()

    def show_previous_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.show_search_page()

    def cancel_download(self):
        if self.active_download:
            self.cancel_requested = True
            self.update_progress(text="Cancelling download...")

    def _cleanup_temp_files(self):
        temp_dir = self.get_temp_dir()
        try:
            if os.path.exists(temp_dir):
                time.sleep(0.5)
                for filename in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, filename)
                    if os.path.isfile(file_path):
                        try:
                            max_attempts = 3
                            for attempt in range(max_attempts):
                                try:
                                    os.remove(file_path)
                                    break
                                except PermissionError:
                                    if attempt < max_attempts - 1:
                                        time.sleep(1)
                                    else:
                                        print(
                                            f"Could not delete file after {max_attempts} attempts: {file_path}"
                                        )
                        except Exception as e:
                            print(f"Error deleting temp file {file_path}: {str(e)}")
        except Exception as e:
            print(f"Error cleaning up temp directory: {str(e)}")


def move_to_final_location(temp_path, final_dir):
    filename = os.path.basename(temp_path)
    final_path = os.path.join(final_dir, filename)
    os.replace(temp_path, final_path)
    return final_path


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


# These paths ensure ffmpeg and ffprobe are bundled from ffmpeg/bin/ for PyInstaller portability
ffmpeg_path = resource_path(os.path.join("ffmpeg", "bin", "ffmpeg.exe"))
ffprobe_path = resource_path(os.path.join("ffmpeg", "bin", "ffprobe.exe"))


def download_audio(url, output_path=DEFAULT_DOWNLOAD_DIR, progress_hook=None):
    try:
        temp_dir = TEMP_DIR
        ydl_opts = {
            "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
            "format": "bestaudio/best",
            "progress_hooks": [progress_hook] if progress_hook else [],
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "retries": 3,
            "fragment_retries": 3,
            "postprocessor_args": [
                f"-ffmpeg_location",
                ffmpeg_path,
                "-write_xing",
                "0",
            ],
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            temp_file = ydl.prepare_filename(info)
            temp_audio = os.path.splitext(temp_file)[0] + ".mp3"
        final_file = move_to_final_location(temp_audio, output_path)
        return final_file
    except Exception as e:
        for f in [temp_file, temp_audio]:
            if "f" in locals() and os.path.exists(f):
                os.remove(f)
        raise RuntimeError(f"Audio download failed: {str(e)}")


def download_playlist(
    url,
    output_path=DEFAULT_DOWNLOAD_DIR,
    quality="best",
    audio_only=False,
    progress_hook=None,
    cancel_check=None,
):
    try:
        temp_dir = TEMP_DIR
        ydl_opts = {
            "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [progress_hook] if progress_hook else [],
            "retries": 3,
            "fragment_retries": 3,
            "skip_unavailable_fragments": True,
            "ignoreerrors": True,
            "continue_dl": True,
            "nooverwrites": True,
        }
        if audio_only:
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
            ydl_opts["postprocessor_args"] = [
                f"-ffmpeg_location",
                ffmpeg_path,
                "-write_xing",
                "0",
            ]
        else:
            ydl_opts["format"] = (
                f"bestvideo[height<={get_quality_height(quality)}]+bestaudio/best"
            )
            ydl_opts["merge_output_format"] = "mp4"
            ydl_opts["postprocessor_args"] = [f"-ffmpeg_location", ffmpeg_path]

        class CancellableYoutubeDL(YoutubeDL):
            def __init__(self, params, cancel_check_callback=None):
                super().__init__(params)
                self.cancel_check_callback = cancel_check_callback

            def extract_info(
                self,
                url,
                download=True,
                ie_key=None,
                extra_info=None,
                process=True,
                force_generic_extractor=False,
            ):
                if self.cancel_check_callback and self.cancel_check_callback():
                    raise Exception("Download cancelled by user")
                return super().extract_info(
                    url, download, ie_key, extra_info, process, force_generic_extractor
                )

        with CancellableYoutubeDL(ydl_opts, cancel_check) as ydl:
            ydl.download([url])
        for file in os.listdir(temp_dir):
            temp_path = os.path.join(temp_dir, file)
            final_path = os.path.join(output_path, file)
            os.replace(temp_path, final_path)
    except Exception as e:
        raise RuntimeError(f"Playlist download failed: {str(e)}")


def convert_video_to_audio(
    video_path, output_path=DEFAULT_DOWNLOAD_DIR, progress_hook=None
):
    try:
        temp_dir = TEMP_DIR
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        video_filename = os.path.basename(video_path)
        temp_audio = os.path.join(
            temp_dir, os.path.splitext(video_filename)[0] + ".mp3"
        )
        cmd = [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip())
        command = [
            ffmpeg_path,
            "-i",
            video_path,
            "-q:a",
            "2",
            "-vn",
            temp_audio,
        ]
        process = subprocess.Popen(
            command,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            universal_newlines=True,
            startupinfo=get_startup_info(),
        )
        time_re = re.compile(r"time=(\d+:\d+:\d+\.\d+)")
        while True:
            line = process.stderr.readline()
            if not line:
                break
            match = time_re.search(line)
            if match and duration > 0:
                current_time = match.group(1)
                parts = list(map(float, current_time.split(":")))
                seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
                progress = (seconds / duration) * 100
                if progress_hook:
                    progress_hook(
                        progress,
                        f"Converting video: {video_filename}\nCompletion: {progress:.1f}%",
                    )
        final_path = move_to_final_location(temp_audio, output_path)
        return final_path
    except Exception as e:
        if "temp_audio" in locals() and os.path.exists(temp_audio):
            os.remove(temp_audio)
        raise RuntimeError(f"Conversion failed: {str(e)}")


def get_quality_height(quality):
    return {"best": 4320, "medium": 720, "low": 480}.get(quality.lower(), 720)


def format_has_audio(format_id, url):
    with YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(url, download=False)
        for fmt in info.get("formats", []):
            if fmt["format_id"] == format_id:
                return fmt.get("acodec") != "none"
    return False


if __name__ == "__main__":
    root = tk.Tk()
    app = TubeGrabberApp(root)
    root.mainloop()
