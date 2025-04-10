# TubeGrabber

A versatile YouTube downloader application built with Python and Tkinter that allows you to download videos, audio, and playlists with an easy-to-use graphical interface.

## Features

- **Single Video Download**: Download YouTube videos in various formats and qualities
- **Audio Extraction**: Extract audio from YouTube videos directly as MP3
- **Playlist Support**: Download entire YouTube playlists with progress tracking
- **Audio Playlist**: Convert all videos in a playlist to MP3 format
- **Local Video Conversion**: Convert local video files to MP3 audio
- **Format Selection**: Choose from available video formats and qualities
- **Multi-threaded Downloads**: Fast playlist downloads with concurrent processing
- **Progress Tracking**: Real-time progress display with speed and ETA information
- **Dark Mode**: Toggle between light and dark interface themes
- **Configurable Settings**: Customize retry attempts and download directory

## Screenshots

![TubeGrabber Main Interface](screenshots/main_interface.png)
![Playlist Download Progress](screenshots/playlist_download.png)

## Requirements

- Python 3.6+
- FFmpeg (for audio extraction and video conversion)
- Required Python packages (see requirements.txt):
  - ffmpeg-python
  - pydub
  - yt-dlp
  - tkinter (included with Python)

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/TubeGrabber.git
   cd TubeGrabber
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install FFmpeg:
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg` or equivalent for your distro

4. Run the application:
   ```bash
   python trydp7.py
   ```

## Usage

### Downloading a Single Video

1. Select "Download Single Video" from the options panel
2. Enter the YouTube video URL
3. Click "Get Formats" to retrieve available formats
4. Select your preferred format from the dropdown
5. Click "Download" to start the download process

### Downloading Audio Only

1. Select "Download Audio Only" from the options panel
2. Enter the YouTube video URL
3. Click "Download Audio" to extract and save the audio as MP3

### Downloading a Playlist

1. Select "Download Playlist" from the options panel
2. Enter the YouTube playlist URL
3. Select your preferred quality (Best, Medium, Low)
4. Click "Download Playlist" to start downloading all videos

### Converting Local Video to Audio

1. Select "Convert Video to Audio" from the options panel
2. Click "Browse" to select a local video file
3. Click "Convert to Audio" to extract the audio track as MP3

## Customization

- **Download Directory**: Change the default download location under File → Set Download Directory
- **Retry Settings**: Configure maximum retry attempts under Settings → Retry Settings
- **Theme**: Toggle Dark Mode under Settings → Dark Mode

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - The core library used for downloading YouTube content
- [FFmpeg](https://ffmpeg.org/) - Used for audio extraction and video processing
- [Tkinter](https://docs.python.org/3/library/tkinter.html) - Python's standard GUI package

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.