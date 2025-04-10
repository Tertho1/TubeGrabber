import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import subprocess
from yt_dlp import YoutubeDL
import threading
import time

class TubeGrabberApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TubeGrabber")
        self.root.geometry("900x600")
        self.root.minsize(800, 500)
        
        # Configure styles
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()
        
        # Create main containers
        self.create_main_containers()
        
        # Initialize variables
        self.current_option = tk.StringVar()
        self.download_progress = tk.DoubleVar()
        self.dark_mode = tk.BooleanVar(value=False)
        self.max_retries = tk.IntVar(value=3)
        self.video_formats = []
        self.download_dir = tk.StringVar(value=os.path.join(os.getcwd(), "downloads"))
        
        # Build UI components
        self.create_option_buttons()
        self.create_input_area()
        self.create_progress_area()
        self.create_menu()
        
        # Set default option
        self.current_option.set("single_video")
        self.show_input_fields("single_video")
    
    def configure_styles(self):
        self.style.configure('TFrame', background='#f0f0f0')
        self.style.configure('TButton', font=('Segoe UI', 10), padding=6)
        self.style.configure('TLabel', background='#f0f0f0', font=('Segoe UI', 10))
        self.style.configure('Header.TLabel', font=('Segoe UI', 12, 'bold'))
        self.style.configure('TEntry', padding=5)
        self.style.configure('TCombobox', padding=5)
        self.style.map('TButton',
                      foreground=[('active', 'black'), ('!disabled', 'black')],
                      background=[('active', '#d9d9d9'), ('!disabled', '#f0f0f0')])
    
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
            ("Download Single Video", "single_video"),
            ("Download Audio Only", "audio_only"),
            ("Download Playlist", "playlist"),
            ("Playlist to Audio", "playlist_audio"),
            ("Convert Video to Audio", "convert_video")
        ]
        
        for text, value in options:
            btn = ttk.Radiobutton(
                options_frame,
                text=text,
                variable=self.current_option,
                value=value,
                command=lambda v=value: self.show_input_fields(v)
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
    
    def create_single_video_fields(self):
        self.single_video_frame = ttk.Frame(self.input_frame)
        
        ttk.Label(self.single_video_frame, text="YouTube Video URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.video_url_entry = ttk.Entry(self.single_video_frame, width=50)
        self.video_url_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Button(self.single_video_frame, 
                  text="Get Formats", 
                  command=self.fetch_video_formats).grid(row=0, column=2, padx=5)
        
        ttk.Label(self.single_video_frame, text="Select Format:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.format_combobox = ttk.Combobox(self.single_video_frame, state="readonly", width=50)
        self.format_combobox.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        ttk.Button(self.single_video_frame, 
                  text="Download", 
                  command=self.download_single_video).grid(row=2, column=1, pady=10, sticky=tk.E)
    
    def create_audio_only_fields(self):
        self.audio_only_frame = ttk.Frame(self.input_frame)
        
        ttk.Label(self.audio_only_frame, text="YouTube Video URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.audio_url_entry = ttk.Entry(self.audio_only_frame, width=50)
        self.audio_url_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Button(self.audio_only_frame, 
                  text="Download Audio", 
                  command=self.download_audio).grid(row=1, column=1, pady=10, sticky=tk.E)
    
    def create_playlist_fields(self):
        self.playlist_frame = ttk.Frame(self.input_frame)
        
        ttk.Label(self.playlist_frame, text="YouTube Playlist URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.playlist_url_entry = ttk.Entry(self.playlist_frame, width=50)
        self.playlist_url_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(self.playlist_frame, text="Quality:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.playlist_quality_combobox = ttk.Combobox(self.playlist_frame, 
                                                    values=["Best", "Medium", "Low"],
                                                    state="readonly")
        self.playlist_quality_combobox.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        self.playlist_quality_combobox.set("Best")
        
        ttk.Button(self.playlist_frame, 
                  text="Download Playlist", 
                  command=self.download_playlist).grid(row=2, column=1, pady=10, sticky=tk.E)
    
    def create_playlist_audio_fields(self):
        self.playlist_audio_frame = ttk.Frame(self.input_frame)
        
        ttk.Label(self.playlist_audio_frame, text="YouTube Playlist URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.playlist_audio_url_entry = ttk.Entry(self.playlist_audio_frame, width=50)
        self.playlist_audio_url_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Button(self.playlist_audio_frame, 
                  text="Download Playlist as Audio", 
                  command=self.download_playlist_audio).grid(row=1, column=1, pady=10, sticky=tk.E)
    
    def create_convert_video_fields(self):
        self.convert_video_frame = ttk.Frame(self.input_frame)
        
        ttk.Label(self.convert_video_frame, text="Video File:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.video_file_entry = ttk.Entry(self.convert_video_frame, width=50)
        self.video_file_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Button(self.convert_video_frame, 
                  text="Browse", 
                  command=self.browse_video_file).grid(row=0, column=2, padx=5)
        
        ttk.Button(self.convert_video_frame, 
                  text="Convert to Audio", 
                  command=self.convert_video).grid(row=1, column=1, pady=10, sticky=tk.E)
    
    def create_progress_area(self):
        ttk.Label(self.progress_frame, text="Progress:").pack(anchor=tk.W)
        self.progress_bar = ttk.Progressbar(self.progress_frame, 
                                          orient=tk.HORIZONTAL,
                                          length=400,
                                          mode='determinate',
                                          variable=self.download_progress)
        self.progress_bar.pack(fill=tk.X, pady=5)
        self.status_label = ttk.Label(self.progress_frame, text="Ready")
        self.status_label.pack(fill=tk.X)
    
    def create_menu(self):
        menubar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Set Download Directory", command=self.select_download_directory)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_checkbutton(label="Dark Mode", 
                                    variable=self.dark_mode,
                                    command=self.toggle_dark_mode)
        settings_menu.add_separator()
        settings_menu.add_command(label="Retry Settings", command=self.show_retry_settings)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=menubar)
    
    def select_download_directory(self):
        directory = filedialog.askdirectory(title="Select Download Directory")
        if directory:
            self.download_dir.set(directory)
            messagebox.showinfo("Info", f"Download directory set to:\n{directory}")
    
    def show_retry_settings(self):
        retry_window = tk.Toplevel(self.root)
        retry_window.title("Retry Settings")
        
        ttk.Label(retry_window, text="Max Retry Attempts:").grid(row=0, column=0, padx=5, pady=5)
        retry_spin = ttk.Spinbox(retry_window, from_=1, to=10, textvariable=self.max_retries)
        retry_spin.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(retry_window, text="Save", command=retry_window.destroy).grid(row=1, columnspan=2, pady=5)
    
    def show_input_fields(self, option):
        for frame in [self.single_video_frame, self.audio_only_frame, 
                     self.playlist_frame, self.playlist_audio_frame,
                     self.convert_video_frame]:
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
    
    def toggle_dark_mode(self):
        if self.dark_mode.get():
            self.style.theme_use('alt')
            self.style.configure('TFrame', background='#333333')
            self.style.configure('TLabel', background='#333333', foreground='white')
        else:
            self.style.theme_use('clam')
            self.style.configure('TFrame', background='#f0f0f0')
            self.style.configure('TLabel', background='#f0f0f0', foreground='black')
    
    def browse_video_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video Files", "*.mp4 *.avi *.mkv *.mov"), ("All Files", "*.*")]
        )
        if file_path:
            self.video_file_entry.delete(0, tk.END)
            self.video_file_entry.insert(0, file_path)
    
    def show_about(self):
        messagebox.showinfo(
            "About TubeGrabber",
            "TubeGrabber v2.0\n\n"
            "A YouTube video and audio downloader with playlist support.\n"
            "Developed with Python and Tkinter."
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
                    messagebox.showerror("Error", "No video formats available for this URL.")
                    return
                
                self.video_formats = video_formats
                options = [
                    f"{fmt['format_id']}: {fmt.get('format_note', 'Unknown')} "
                    f"({fmt.get('ext', 'Unknown')}) - {fmt.get('resolution', 'N/A')}"
                    for fmt in video_formats
                ]
                self.format_combobox['values'] = options
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
                if attempt < retries:
                    self.update_progress(text=f"Retrying ({attempt}/{retries})...")
                    time.sleep(2 ** attempt)  # Exponential backoff
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
        
        threading.Thread(target=self._download_single_video_thread, args=(url, format_id), daemon=True).start()
    
    def _download_single_video_thread(self, url, format_id):
        try:
            def progress_hook(d):
                if d['status'] == 'downloading':
                    # Skip audio stream download progress
                    if d.get('info_dict', {}).get('_type') == 'audio':
                        return
                    
                    total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
                    downloaded_bytes = d.get('downloaded_bytes')
                    speed = d.get('speed')
                    eta = d.get('eta')
                    
                    if total_bytes and downloaded_bytes and total_bytes > 0:
                        percent = (downloaded_bytes / total_bytes) * 100
                    else:
                        percent = 0
                    
                    # Format speed
                    speed_str = f"{speed/(1024**2):.2f} MB/s" if speed else "Unknown speed"
                    # Format ETA
                    eta_str = time.strftime("%M:%S", time.gmtime(eta)) if eta else "Unknown ETA"
                    
                    self.root.after(0, self.update_progress, 
                                percent, 
                                f"Downloading video: {percent:.1f}% | Speed: {speed_str} | ETA: {eta_str}")
                
                elif d['status'] == 'postprocessing':
                    self.root.after(0, self.update_progress, 
                                100, 
                                "Merging audio and video streams...")

            self.update_progress(0, "Starting video download...")
            filename = self.download_with_retry(
                download_video, 
                url, 
                format_id=format_id,
                output_path=self.download_dir.get(),
                progress_hook=progress_hook
            )
            self.update_progress(100, "Download complete!")
            messagebox.showinfo("Success", f"Video downloaded:\n{filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download video:\n{str(e)}")
        finally:
            self.update_progress(0, "Ready")

   

    def _download_playlist_thread(self, url, quality, audio_only):
        try:
            # 1. Pre-fetch playlist information
            try:
                with YoutubeDL({'quiet': True, 'extract_flat': 'in_playlist'}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    total_items = len(info.get('entries', []))
            except Exception as e:
                total_items = 1  # Fallback if extraction fails

            # 2. Initialize progress tracking
            percent_per_item = 100.0 / total_items if total_items > 0 else 100
            current_item = 0
            fragment_tracker = {}  # {item_index: (current_fragment, total_fragments)}

            def progress_hook(d):
                nonlocal current_item

                if d['status'] == 'downloading':
                    # 3. Track playlist item changes
                    new_item = d.get('info_dict', {}).get('playlist_index', 0)
                    if new_item != current_item:
                        current_item = new_item
                        fragment_tracker[current_item] = (0, 0)

                    # 4. Handle fragment-based progress
                    frag_index = d.get('fragment_index')
                    frag_count = d.get('fragment_count')
                    
                    # Update fragment tracking for current item
                    if frag_count and frag_index is not None:
                        if frag_index > fragment_tracker.get(current_item, (0, 0))[0]:
                            fragment_tracker[current_item] = (frag_index, frag_count)

                    # 5. Calculate progress
                    base_progress = (current_item - 1) * percent_per_item
                    item_progress = 0

                    # Fragment-based calculation
                    if frag_count and frag_index > 0:
                        item_progress = (frag_index / frag_count) * percent_per_item
                    else:
                        # Bytes-based fallback
                        downloaded = d.get('downloaded_bytes', 0)
                        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                        if total > 0:
                            item_progress = (downloaded / total) * percent_per_item

                    total_progress = base_progress + item_progress
                    total_progress = min(total_progress, 100)  # Cap at 100%

                    # 6. Get display metrics
                    speed = d.get('speed', 0)
                    eta = d.get('eta', 0)
                    filename = os.path.basename(d.get('filename', 'item'))

                    # 7. Update UI
                    self.root.after(0, self.update_progress,
                                total_progress,
                                f"Item {current_item}/{total_items} ({filename})\n"
                                f"Progress: {total_progress:.1f}% | "
                                f"Speed: {speed/(1024**2):.2f}MB/s | "
                                f"ETA: {time.strftime('%M:%S', time.gmtime(eta)) if eta else 'N/A'}")

                elif d['status'] == 'finished':
                    # Update progress when item completes
                    self.root.after(0, self.update_progress,
                                min(100, current_item * percent_per_item),
                                f"Completed item {current_item}/{total_items}")

            # 8. Start the download
            self.update_progress(0, "Starting playlist download...")
            self.download_with_retry(
                download_playlist,
                url,
                quality=quality,
                audio_only=audio_only,
                output_path=self.download_dir.get(),
                progress_hook=progress_hook
            )
            self.update_progress(100, "Playlist download complete!")
            messagebox.showinfo("Success", "Playlist downloaded successfully")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download playlist: {str(e)}")
        finally:
            self.update_progress(0, "Ready")

    def download_audio(self):
        url = self.audio_url_entry.get().strip()
        threading.Thread(target=self._download_audio_thread, args=(url,), daemon=True).start()
    
    def _download_audio_thread(self, url):
        try:
            def progress_hook(d):
                if d['status'] == 'downloading':
                    total_bytes = d.get('total_bytes')
                    downloaded_bytes = d.get('downloaded_bytes')
                    speed = d.get('speed')
                    eta = d.get('eta')
                    
                    if total_bytes and downloaded_bytes and total_bytes > 0:
                        percent = (downloaded_bytes / total_bytes) * 100
                    else:
                        percent = 0
                    
                    speed_str = "Unknown speed"
                    if speed:
                        speed_str = f"{speed/(1024**2):.2f} MB/s" if speed > 1024 else f"{speed/1024:.2f} KB/s"
                    
                    eta_str = time.strftime("%M:%S", time.gmtime(eta)) if eta else "Unknown ETA"
                    
                    self.root.after(0, self.update_progress, 
                                  percent, 
                                  f"Downloading: {percent:.1f}% | Speed: {speed_str} | ETA: {eta_str}")

            self.update_progress(0, "Starting audio download...")
            filename = self.download_with_retry(
                download_audio, 
                url,
                output_path=self.download_dir.get(),
                progress_hook=progress_hook
            )
            self.update_progress(100, "Audio download complete!")
            messagebox.showinfo("Success", f"Audio downloaded:\n{filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download audio:\n{str(e)}")
        finally:
            self.update_progress(0, "Ready")
    
    def download_playlist(self):
        url = self.playlist_url_entry.get().strip()
        quality = self.playlist_quality_combobox.get().lower()
        threading.Thread(target=self._download_playlist_thread, args=(url, quality, False), daemon=True).start()
    
    def download_playlist_audio(self):
        url = self.playlist_audio_url_entry.get().strip()
        threading.Thread(target=self._download_playlist_thread, args=(url, "best", True), daemon=True).start()
    
    # def _download_playlist_thread(self, url, quality, audio_only):
        try:
            def progress_hook(d):
                if d['status'] == 'downloading':
                    total_bytes = d.get('total_bytes')
                    downloaded_bytes = d.get('downloaded_bytes')
                    print(f"Downloaded bytes: {downloaded_bytes}, Total bytes: {total_bytes}")
                    speed = d.get('speed')
                    eta = d.get('eta')
                    
                    if total_bytes and downloaded_bytes and total_bytes > 0:
                        percent = (downloaded_bytes / total_bytes) * 100
                    else:
                        percent = 0
                    
                    speed_str = f"{speed/(1024**2):.2f} MB/s" if speed else "Unknown speed"
                    eta_str = time.strftime("%M:%S", time.gmtime(eta)) if eta else "Unknown ETA"
                    
                    self.root.after(0, self.update_progress, 
                                  percent, 
                                  f"Downloading playlist: {percent:.1f}% | Speed: {speed_str} | ETA: {eta_str}")

            self.update_progress(0, "Starting playlist download...")
            self.download_with_retry(
                download_playlist, 
                url, 
                quality=quality, 
                audio_only=audio_only,
                output_path=self.download_dir.get(),
                progress_hook=progress_hook
            )
            self.update_progress(100, "Playlist download complete!")
            messagebox.showinfo("Success", "Playlist downloaded successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download playlist:\n{str(e)}")
        finally:
            self.update_progress(0, "Ready")
    
    

    def convert_video(self):
        video_path = self.video_file_entry.get().strip()
        threading.Thread(target=self._convert_video_thread, args=(video_path,), daemon=True).start()
    
    def _convert_video_thread(self, path):
        try:
            self.update_progress(0, "Starting conversion...")
            filename = self.download_with_retry(
                convert_video_to_audio, 
                path,
                output_path=self.download_dir.get()
            )
            self.update_progress(100, "Conversion complete!")
            messagebox.showinfo("Success", f"Converted to audio:\n{filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Conversion failed:\n{str(e)}")
        finally:
            self.update_progress(0, "Ready")

# ===============================
# Download/Conversion Functions
# ===============================

def download_video(url, output_path="downloads", format_id=None, progress_hook=None):
    try:
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        ydl_opts = {
            "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
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
            return ydl.prepare_filename(info)
    except Exception as e:
        raise RuntimeError(f"Video download failed: {str(e)}")

def download_audio(url, output_path="downloads", progress_hook=None):
    try:
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        ydl_opts = {
            "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
            "format": "bestaudio/best",
            "progress_hooks": [progress_hook] if progress_hook else [],
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "retries": 3,
            "fragment_retries": 3,
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")
    except Exception as e:
        raise RuntimeError(f"Audio download failed: {str(e)}")

def download_playlist(url, output_path="downloads", quality="best", audio_only=False, progress_hook=None):
    try:
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        ydl_opts = {
            "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
            "progress_hooks": [progress_hook] if progress_hook else [],
            "retries": 3,
            "fragment_retries": 3,
            "skip_unavailable_fragments": True,
            "ignoreerrors": True,
            # "hls_prefer_native": False,
        }
        
        if audio_only:
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        else:
            ydl_opts["format"] = f"bestvideo[height<={get_quality_height(quality)}]+bestaudio/best"
        
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        raise RuntimeError(f"Playlist download failed: {str(e)}")

def convert_video_to_audio(video_path, output_path="downloads"):
    try:
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        video_filename = os.path.basename(video_path)
        audio_filename = os.path.splitext(video_filename)[0] + ".mp3"
        audio_path = os.path.join(output_path, audio_filename)
        
        command = [
            "ffmpeg",
            "-i", video_path,
            "-q:a", "2",
            "-vn",
            audio_path,
        ]
        subprocess.run(command, check=True, stderr=subprocess.DEVNULL)
        return audio_path
    except Exception as e:
        raise RuntimeError(f"Conversion failed: {str(e)}")

def get_quality_height(quality):
    return {
        "best": 4320,
        "medium": 720,
        "low": 480
    }.get(quality.lower(), 720)

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