from yt_dlp import YoutubeDL
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

# Function to list available formats and let the user choose
def list_and_choose_format(url, format_type="video"):
    ydl_opts = {
        "quiet": True,  # Suppress yt-dlp output
    }
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        formats = info_dict.get("formats", [])
        
        # Filter formats based on type (video or audio)
        if format_type == "video":
            formats = [fmt for fmt in formats if fmt.get("vcodec") != "none"]
        elif format_type == "audio":
            formats = [fmt for fmt in formats if fmt.get("acodec") != "none" and fmt.get("vcodec") == "none"]
        
        print(f"\nAvailable {format_type} formats for {url}:")
        for i, fmt in enumerate(formats):
            print(f"{i + 1}. {fmt['format']} - {fmt.get('resolution', 'N/A')} - {fmt.get('ext', 'N/A')}")
        
        choice = input(f"\nEnter the number of the {format_type} format you want to download: ")
        try:
            choice = int(choice) - 1
            if 0 <= choice < len(formats):
                return formats[choice]["format_id"]
            else:
                print(f"Invalid choice. Downloading the best {format_type} format by default.")
                return "best"
        except ValueError:
            print(f"Invalid input. Downloading the best {format_type} format by default.")
            return "best"

# Function to check if a format includes audio
def format_has_audio(format_id, url):
    ydl_opts = {
        "quiet": True,  # Suppress yt-dlp output
    }
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        for fmt in info_dict.get("formats", []):
            if fmt["format_id"] == format_id:
                return fmt.get("acodec") != "none"
    return False

# Function to merge video and audio streams using FFmpeg
def merge_video_audio(video_path, audio_path, output_path):
    try:
        command = [
            "ffmpeg",
            "-i", video_path,  # Input video file
            "-i", audio_path,  # Input audio file
            "-c:v", "copy",    # Copy video stream without re-encoding
            "-c:a", "copy",    # Copy audio stream without re-encoding
            output_path,       # Output file
        ]
        subprocess.run(command, check=True)
        print(f"Merged video and audio: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Error merging video and audio: {e}")
        return None

# Function to download a single YouTube video using yt-dlp
def download_video(url, output_path="downloads", format_id=None):
    try:
        # If format_id is not provided, let the user choose the format
        if format_id is None:
            format_id = list_and_choose_format(url, format_type="video")
        
        # Check if the selected video format includes audio
        if format_has_audio(format_id, url):
            # Download the video directly (no need to merge)
            ydl_opts = {
                "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
                "format": format_id,  # Download the selected video format
            }
        else:
            # Automatically use the best audio format
            ydl_opts = {
                "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
                "format": f"{format_id}+bestaudio",  # Download selected video and best audio
                "merge_output_format": "mp4",        # Merge into mp4
            }
        
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = os.path.basename(ydl.prepare_filename(info_dict))  # Get only the filename
            print(f"Video downloaded: {filename}")
            return filename
    except Exception as e:
        print(f"Error downloading video: {e}")
        return None

# Function to download only audio from a YouTube video
def download_audio(url, output_path="downloads", format_id=None):
    try:
        # If format_id is not provided, let the user choose the format
        if format_id is None:
            format_id = list_and_choose_format(url, format_type="audio")
        
        # Download the audio
        ydl_opts = {
            "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
            "format": format_id,  # Download the selected audio format
            "extract_audio": True,      # Extract audio only
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",  # Convert to mp3
                "preferredquality": "0",  # Best quality
            }],
        }
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = os.path.basename(ydl.prepare_filename(info_dict))  # Get only the filename
            print(f"Audio downloaded: {filename}")
            return filename
    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None

# Function to download a YouTube playlist using yt-dlp
def download_playlist(url, output_path="downloads", audio_only=False):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,  # Extract playlist metadata without downloading
        }
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            if "entries" not in info_dict:
                print("This is not a playlist. Please provide a valid playlist URL.")
                return
            
            # Extract individual video URLs from the playlist
            video_urls = [entry["url"] for entry in info_dict["entries"]]
            print(f"Found {len(video_urls)} videos in the playlist.")
            
            # Collect preferred formats for each video
            format_queue = []
            for video_url in video_urls:
                print(f"\nSelecting format for video: {video_url}")
                if audio_only:
                    format_id = list_and_choose_format(video_url, format_type="audio")
                else:
                    format_id = list_and_choose_format(video_url, format_type="video")
                format_queue.append((video_url, format_id))
            
            # Use ThreadPoolExecutor for parallel downloads
            with ThreadPoolExecutor(max_workers=5) as executor:  # Adjust max_workers as needed
                futures = []
                for video_url, format_id in format_queue:
                    if audio_only:
                        futures.append(executor.submit(download_audio, video_url, output_path, format_id))
                    else:
                        futures.append(executor.submit(download_video, video_url, output_path, format_id))
                
                # Wait for all downloads to complete
                for future in futures:
                    future.result()  # Raise exceptions if any
        
        print(f"Playlist downloaded to: {output_path}")
    except Exception as e:
        print(f"Error downloading playlist: {e}")

# Function to convert a video file to audio using FFmpeg
def convert_video_to_audio(video_path, output_path="downloads"):
    try:
        # Ensure the video file exists
        if not os.path.exists(video_path):
            print(f"Video file not found: {video_path}")
            return None
        
        # Extract the filename and create the output audio filename
        video_filename = os.path.basename(video_path)
        audio_filename = video_filename.replace(".mp4", ".mp3")
        audio_path = os.path.join(output_path, audio_filename)
        
        # Use FFmpeg to extract audio with high quality
        command = [
            "ffmpeg",
            "-i", video_path,       # Input video file
            "-q:a", "0",            # Best audio quality (variable bitrate)
            "-map", "a",            # Extract only the audio stream
            audio_path,             # Output audio file
        ]
        subprocess.run(command, check=True)
        
        print(f"Audio saved: {audio_filename}")
        return audio_filename
    except subprocess.CalledProcessError as e:
        print(f"Error converting video to audio: {e}")
        return None

# Main function to handle user interaction
def main():
    while True:
        print("\n1. Download a single video")
        print("2. Download only audio")
        print("3. Download a playlist")
        print("4. Download a Full Playlist as Audio")
        print("5. Convert a local video to audio")
        print("6. Exit")
        choice = input("Enter your choice: ")
        
        if choice == "1":
            url = input("Enter the YouTube video URL: ")
            filename = download_video(url)
            if filename:
                convert = input("Do you want to convert this video to audio? (y/n): ").lower()
                if convert == "y":
                    convert_video_to_audio(os.path.join("downloads", filename))
        
        elif choice == "2":
            url = input("Enter the YouTube video URL: ")
            download_audio(url)
        
        elif choice == "3":
            url = input("Enter the YouTube playlist URL: ")
            download_playlist(url)

        elif choice == "4":
            url = input("Enter the YouTube playlist URL: ")
            download_playlist(url, audio_only=True)  # Directly download as audio
        
        elif choice == "5":
            video_path = input("Enter the path to the local video file: ")
            convert_video_to_audio(video_path)
        
        elif choice == "6":
            print("Exiting...")
            break
        
        else:
            print("Invalid choice. Please try again.")

# Run the program
if __name__ == "__main__":
    main()