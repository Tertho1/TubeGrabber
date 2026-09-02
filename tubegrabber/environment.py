"""Runtime environment setup and configuration paths for TubeGrabber."""

import os
import sys

# Base user directories
USER_HOME = os.path.expanduser("~")
DEFAULT_DOWNLOAD_DIR = os.path.join(USER_HOME, "Downloads", "TubeGrabber")
TEMP_DIR = os.path.join(DEFAULT_DOWNLOAD_DIR, "temp")
CONFIG_DIR = os.path.join(USER_HOME, ".tubegrabber")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")


def setup_environment():
    """Prepare environment for development or frozen (PyInstaller) mode.

    - When frozen: prepend executable directory to PATH and create temp dir.
    - When not frozen: ensure default download/temp directories exist.
    """
    if getattr(sys, "frozen", False):
        base_path = os.path.dirname(sys.executable)
        os.environ["PATH"] = base_path + os.pathsep + os.environ.get("PATH", "")
        temp_dir = os.path.join(base_path, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        os.environ["TEMP"] = temp_dir
        os.environ["TMP"] = temp_dir
    else:
        os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
        os.makedirs(CONFIG_DIR, exist_ok=True)


def get_startup_info():
    """Return subprocess.STARTUPINFO to hide console windows on Windows."""
    if os.name == "nt":
        import subprocess

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        return startupinfo
    return None
