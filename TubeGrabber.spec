
# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

# Collect all dependencies
datas = []
binaries = []
hiddenimports = []

# Add FFmpeg binaries
ffmpeg_bin = os.path.join(os.getcwd(), 'ffmpeg_bundle', 'bin')
if os.path.exists(ffmpeg_bin):
    for file in os.listdir(ffmpeg_bin):
        if file.endswith(('.exe', '.dll')):
            binaries.append((os.path.join(ffmpeg_bin, file), 'ffmpeg'))

# Collect yt-dlp dependencies
tmp_ret = collect_all('yt_dlp')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Collect other dependencies
for module in ['pydub', 'ffmpeg', 'requests', 'urllib3', 'certifi']:
    try:
        tmp_ret = collect_all(module)
        datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
    except:
        pass

# Additional hidden imports
hiddenimports += [
    'yt_dlp.extractor.lazy_extractors',
    'yt_dlp.extractor.generic',
    'yt_dlp.extractor.youtube',
    'pydub.effects',
    'pydub.silence',
    'pydub.utils',
    # TubeGrabber modular components
    'tubegrabber.config',
    'tubegrabber.logging_utils',
    'tubegrabber.events',
    'tubegrabber.errors',
    'tubegrabber.adapters.ytdlp_adapter',
    'tubegrabber.adapters.ffmpeg_adapter',
    'tubegrabber.services.download_service',
    'tubegrabber.services.search_service',
    'tubegrabber.models',
]

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TubeGrabber',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    cofile=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
    version='version_info.txt' if os.path.exists('version_info.txt') else None,
)
