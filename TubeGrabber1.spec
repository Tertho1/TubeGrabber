# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_all

# Get the SPEC path and use it to build absolute paths
SPECs = os.path.abspath(SPEC)
specpath = os.path.dirname(SPECs)
icon_file = os.path.join(specpath, 'icon.ico')

# Include yt-dlp and its dependencies
ytdlp_data = collect_all('yt_dlp')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        # Add yt-dlp.exe from your virtual environment
        (os.path.join(sys.prefix, 'Scripts', 'yt-dlp.exe'), '.'),
        ('E:\\Projects\\ffmpeg\\bin\\ffmpeg.exe', '.'),
        ('E:\\Projects\\ffmpeg\\bin\\ffprobe.exe', '.'),
    ],
    datas=[
        (os.path.join(specpath, 'icon.ico'), '.'),
        *ytdlp_data[0],  # Include yt-dlp data files
    ],
    hiddenimports=ytdlp_data[1],  # Include yt-dlp hidden imports
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TubeGrabber',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Keep this as False for GUI application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)