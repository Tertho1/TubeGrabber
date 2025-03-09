import customtkinter as ctk
from tkinter import messagebox, filedialog
import os
import subprocess
from yt_dlp import YoutubeDL
import threading

# Set appearance and theme
ctk.set_appearance_mode("System")  # "Light" or "Dark"
ctk.set_default_color_theme("blue")  # Themes: blue, green, dark-blue

# Main Application Class
class YouTubeDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configure window
        self.title("YouTube Downloader")
        self.geometry("800x600")
        self.resizable(True, True)

        # Create UI
        self.create_widgets()

    def create_widgets(self):
        # URL Input
        self.url_label = ctk.CTkLabel(self, text="YouTube URL:", font=("Segoe UI", 14))
        self.url_label.grid(row=0, column=0, padx=20, pady=10, sticky="w")

        self.url_entry = ctk.CTkEntry(self, width=400, font=("Segoe UI", 14))
        self.url_entry.grid(row=0, column=1, padx=20, pady=10, sticky="ew")

        # Format Selection
        self.format_label = ctk.CTkLabel(self, text="Format:", font=("Segoe UI", 14))
        self.format_label.grid(row=1, column=0, padx=20, pady=10, sticky="w")

        self.format_var = ctk.StringVar(value="video")
        self.format_combo = ctk.CTkComboBox(
            self, values=["Video", "Audio"], variable=self.format_var, font=("Segoe UI", 14)
        )
        self.format_combo.grid(row=1, column=1, padx=20, pady=10, sticky="ew")

        # Quality Selection
        self.quality_label = ctk.CTkLabel(self, text="Quality:", font=("Segoe UI", 14))
        self.quality_label.grid(row=2, column=0, padx=20, pady=10, sticky="w")

        self.quality_var = ctk.StringVar(value="best")
        self.quality_combo = ctk.CTkComboBox(
            self, values=["Best", "Medium", "Low"], variable=self.quality_var, font=("Segoe UI", 14)
        )
        self.quality_combo.grid(row=2, column=1, padx=20, pady=10, sticky="ew")

        # Output Path
        self.output_label = ctk.CTkLabel(self, text="Output Folder:", font=("Segoe UI", 14))
        self.output_label.grid(row=3, column=0, padx=20, pady=10, sticky="w")

        self.output_var = ctk.StringVar(value=os.path.join(os.getcwd(), "downloads"))
        self.output_entry = ctk.CTkEntry(self, textvariable=self.output_var, width=400, font=("Segoe UI", 14))
        self.output_entry.grid(row=3, column=1, padx=20, pady=10, sticky="ew")

        self.browse_button = ctk.CTkButton(self, text="Browse", command=self.browse_output_path)
        self.browse_button.grid(row=3, column=2, padx=20, pady=10)

        # Download Button
        self.download_button = ctk.CTkButton(self, text="Download", command=self.start_download)
        self.download_button.grid(row=4, column=1, padx=20, pady=20)

        # Log Area
        self.log_label = ctk.CTkLabel(self, text="Logs:", font=("Segoe UI", 14))
        self.log_label.grid(row=5, column=0, padx=20, pady=10, sticky="w")

        self.log_text = ctk.CTkTextbox(self, width=600, height=200, font=("Consolas", 12))
        self.log_text.grid(row=6, column=0, columnspan=3, padx=20, pady=10, sticky="nsew")

        # Progress Bar
        self.progress = ctk.CTkProgressBar(self, orientation="horizontal", width=600)
        self.progress.grid(row=7, column=0, columnspan=3, padx=20, pady=10, sticky="ew")
        self.progress.set(0)

        # Configure grid weights
        self.columnconfigure(1, weight=1)
        self.rowconfigure(6, weight=1)

    def browse_output_path(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_var.set(folder)

    def start_download(self):
        url = self.url_entry.get()
        format_type = self.format_var.get().lower()
        quality = self.quality_var.get().lower()
        output_path = self.output_var.get()

        if not url:
            messagebox.showwarning("Error", "Please enter a valid YouTube URL.")
            return

        # Create output directory if it doesn't exist
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        # Start download in a separate thread
        download_thread = threading.Thread(
            target=self.download, args=(url, output_path, format_type, quality), daemon=True
        )
        download_thread.start()

    def download(self, url, output_path, format_type, quality):
        try:
            if format_type == "video":
                self.log("Downloading video...")
                filename = self.download_video(url, output_path, quality)
            else:
                self.log("Downloading audio...")
                filename = self.download_audio(url, output_path)
            self.log(f"Download complete: {filename}")
        except Exception as e:
            self.log(f"Error: {e}")

    def download_video(self, url, output_path, quality):
        try:
            format_id = self.get_quality_format(url, quality)
            if format_has_audio(format_id, url):
                ydl_opts = {
                    "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
                    "format": format_id,
                }
            else:
                ydl_opts = {
                    "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
                    "format": f"{format_id}+bestaudio",
                    "merge_output_format": "mp4",
                }
            with YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                filename = os.path.basename(ydl.prepare_filename(info_dict))
                self.log(f"Video downloaded: {filename}")
                return filename
        except Exception as e:
            self.log(f"Error downloading video: {e}")
            return None

    def download_audio(self, url, output_path):
        try:
            ydl_opts = {
                "quiet": True,
            }
            with YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                formats = info_dict.get("formats", [])
                audio_formats = [fmt for fmt in formats if fmt.get("acodec") != "none" and fmt.get("vcodec") == "none"]
                if audio_formats:
                    format_id = audio_formats[-1]["format_id"]
                else:
                    format_id = "best"
            ydl_opts = {
                "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
                "format": format_id,
                "extract_audio": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",
                }],
            }
            with YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                filename = os.path.basename(ydl.prepare_filename(info_dict))
                self.log(f"Audio downloaded: {filename}")
                return filename
        except Exception as e:
            self.log(f"Error downloading audio: {e}")
            return None

    def get_quality_format(self, url, quality="best"):
        ydl_opts = {
            "quiet": True,
        }
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            formats = info_dict.get("formats", [])
            video_formats = [
                {"format_id": fmt["format_id"], "height": fmt.get("height", 0)}
                for fmt in formats
                if fmt.get("vcodec") != "none"
            ]
            video_formats.sort(key=lambda x: (x["height"], x["format_id"]))
            if not video_formats:
                return "best"
            if quality == "best":
                return video_formats[-1]["format_id"]
            elif quality == "medium":
                best_height = video_formats[-1]["height"]
                for fmt in reversed(video_formats[:-1]):
                    if fmt["height"] < best_height:
                        return fmt["format_id"]
                return video_formats[-1]["format_id"]
            elif quality == "low":
                best_height = video_formats[-1]["height"]
                medium_height = None
                for fmt in reversed(video_formats[:-1]):
                    if fmt["height"] < best_height:
                        medium_height = fmt["height"]
                        break
                if medium_height is not None:
                    for fmt in reversed(video_formats[:-1]):
                        if fmt["height"] < medium_height:
                            return fmt["format_id"]
                return video_formats[-1]["format_id"]
            else:
                return "best"

    def log(self, message):
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

# Run the application
if __name__ == "__main__":
    app = YouTubeDownloaderApp()
    app.mainloop()