# Legacy Codebase

This folder contains legacy code preserved for reference:

- `main2.py` — Monolithic single-file implementation (~1983 lines) from 3rd-year Python project.

## ⚠️ Status: FROZEN

**DO NOT EDIT** files in this directory. 

All modern business logic lives in `tubegrabber/`:
- `tubegrabber/services/` — High-level services (DownloadService, SearchService)
- `tubegrabber/adapters/` — Technology wrappers (YtDlpAdapter, FFmpegAdapter)
- `tubegrabber/app.py` — Application layer
- `main.py` — Entry point
