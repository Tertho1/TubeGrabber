# TODO — TubeGrabber Universal Downloader (Faster than IDM)

> **Execution order:** Phase 0 → 1 → 2 → 3 → 4. Do not start a later phase until its predecessor's DoD passes.
> Mark `- [x] Item (YYYY-MM-DD, PR #)` when done. Add new debt to Phase 0.
> All paths relative to repo root unless noted `path:line`.

---

## Phase 0 — Stabilise & Audit [P0 — STOP-SHIP]

**Goal:** Single codebase, one config, one spec, green CI. No feature until this passes.

- [x] **0.1 Archive legacy** (2026-09-02, commit `e027a7b`) — moved `main2.py` → `legacy/main2.py`, added `legacy/README.md` "frozen". Kept `main.py:1` → `tubegrabber/app.py:36` as entry. Verified `python main.py` still runs.
- [x] **0.2 Deduplicate modules** (2026-09-02, commit `7657988`) — deleted `tubegrabber/search.py` & `tubegrabber/downloaders.py` after ensuring `services/*` cover all calls. Core `tubegrabber/` tracked in git.
- [x] **0.3 Fix config split** (2026-09-02, commit `016f563`) — refactored `tubegrabber/config.py` + `tubegrabber/app.py` into one manager using `platformdirs` + `pydantic-settings`. Preserved `~/.tubegrabber/settings.json` migration. Stored resolved `download_dir`, `temp_dir`, `max_concurrent`, `theme`, `chunk_size`, `speed_limit`. Added unit tests (3/3 pass). Fixes D5.
- [x] **0.4 Fix download path bug** (2026-09-02, commit `bc3153a`) — `services/download_service.py` uses per-job `TEMP_DIR/<job_id>/` staging; `move_to_final_location` handles cross-device (`shutil.move`) + dedup `title (1).mp4` (no silent overwrite per AGENTS.md §1.6) + sanitization. Removed `os.listdir` leak and added missing `import os, shutil, uuid`. Fixes D1, D2, D8.
- [x] **0.5 Fix `format_has_audio`** (2026-09-02, commit `bc3153a`) — `utils.py` accepts pre-fetched `info:dict` param, deprecated network-per-call. Updated `download_service.py` call sites. Fixes D4.
- [x] **0.6 Fix playlist search** (2026-09-02, commit `9c462fe`) — `services/search_service.py` implements YouTube playlist search via `sp=EgIQAw%253D%253D` and `extract_flat=True`. Added unit tests for video and playlist search. Fixes D3.
- [x] **0.7 Consolidate specs** (2026-09-03, commit `8575c16`) — kept `TubeGrabber.spec` canonical (91 LoC), deleted `main.spec`/`TubeGrabber1.spec:20` (`E:\...`), removed `*.spec` from `.gitignore:34` so spec tracked, untracked `build/`/`dist/` binaries (+ `ffmpeg_bundle/`), CI smoke `build-spec-smoke` added. Fixes D7.
- [x] **0.8 Pin & prune deps** (2026-09-03, commit `13a4be5`) — pinned `yt-dlp==2026.8.19`, `requests==2.34.2`, `platformdirs==4.11.7`, `pydantic==2.13.5`, `pydantic-settings==2.15.0`, `Pillow==12.3.0`, `keyring==25.7.0` → `requirements.txt` + `requirements.lock` (curated `pip freeze`). Removed `ffmpeg-python`/`pydub` (unused, `FFmpegAdapter` via subprocess).
- [x] **0.9 CI & quality gates** (2026-09-03, commit `8b717b2`) — added `.github/workflows/ci.yml` (`ruff check/format`, `mypy --strict`, `pytest`, `bandit`, `pip-audit`, `pyinstaller TubeGrabber.spec --clean`) + `.pre-commit-config.yaml` (ruff/mypy). Scaffold `tests/` mocked.
- [x] **0.10 Logging/event fix** (2026-09-03, commit `8575c16`) — `events.py:16` now logs via `logging`, `ffmpeg_adapter.py:22` uses `get_startup_info()`, `app.py:350` `fetch_video_formats` off UI thread via `YtDlpAdapter` + `root.after`, `ytdlp_adapter.py:55` removed naive `.replace`. Fixes D9-D12.
- [x] **0.11 Inventory & decisions** (2026-09-03, commit `docs/DECISIONS.md`) — wrote `docs/DECISIONS.md` ADR-001…006 (config `platformdirs`, UI `CustomTkinter P1/Qt P2`, chunk native/`aria2` optional, per-job `TEMP_DIR/<job_id>`, single spec, push guardrail). Noted open decisions for Phase 1.

**DoD Phase 0:** `python main.py` launches, one video + audio download works staged via per-job temp, search videos + playlists returns results, `pytest` passes, CI green, only one spec remains.

---

## Phase 1 — Speed Core: Faster than IDM [P1]

**Goal:** Saturate link; queue >1 job; resume; speed control.

- [x] **1.1 Segmented fragments** (2026-09-03, commit `a983add`) — `concurrent_fragments=5` (cap 16 `config.py:34`), `http_chunk_size=10M`, `retries=10`, `fragment_retries=10`, `extractor_retries=3` + exp backoff for `429` in `services/download_service.py:66,104,181`; `config.py:36` `max_retries 3→10`.
- [x] **1.2 Concurrent queue** (2026-09-03, commit `dfd2f7e`) — replaced `app.py:53 active_download:bool` with `services/queue_service.py` `DownloadQueue` (`ThreadPoolExecutor` 3 workers, cap 10) + `Job{id,url,kind,status,progress,speed,eta}`. Routes `download_*` via `queue.submit`, `active_download` now property `queue.has_active`, `on_closing` shutdown, `tests/test_queue.py` 3/3 pass. SQLite `jobs.db` persistence deferred to 1.3.
- [x] **1.3 Resume & atomic IO** (2026-09-03, commit `9219ad9`) — per-job deterministic `TEMP_DIR/<md5(url)>/` for resume, explicit `continuedl`/`continue_dl` + `nopart:false` + `overwrites:false`/`nooverwrites:true`, keep `.part` on cancel/failure, atomic `shutil.move` dedup retained, `cleanup_stale_temp(24h)` added.
- [x] **1.4 Speed limiter** (2026-09-03, commit `40101d7`) — per-job `ratelimit`/`throttledratelimit` (`speed_limit_kbps` `config.py:39` → `services/download_service.py:32` `set_speed_limit`/`_get_speed_opts`), wired via `app.py:76` `DownloadService(speed_limit_kbps)`, `0=unlimited`.
- [x] **1.5 ffmpeg passthrough** (2026-09-03, commit `bf826d5`) — `convert_to_mp3` passthrough via `shutil.copy` + `move_to_final_location` if source already `mp3`, else `ffmpeg -ab 192k`; yt-dlp merge already `-c copy` when codecs compatible.
- [x] **1.6 Cancellation robustness** (2026-09-03, verified) — `DownloadService:40 cancel()` propagates via `progress_hook:44` `DownloadCancelled` + `app.py:683` `download_queue.cancel_all()`; `on_closing:763` shutdown, no orphan `ffmpeg` (yt-dlp kills child, `FFmpegAdapter` uses `subprocess.run` short-lived, `DownloadService` keeps `.part` for resume).
- [x] **1.7 Benchmark harness** (2026-09-03, commit `bench`) — `tests/bench_speed.py` (argparse, queue bench) + `docs/BENCH.md` (method, `speed.hetzner.de/100MB.bin`, IDM `~22s` vs target `≤20s`, results TODO).

**DoD Phase 1:** 3 parallel downloads saturate link; pause/resume survives app kill; speed limiter respected; no `active_download` global.

---

## Phase 2 — Universal: Download Anything [P2]

**Goal:** Any URL, clipboard, auth, bulk.

- [ ] **2.1 Generic URL entry** — remove YouTube-only labels in `app.py:156 create_option_buttons`. Accept any URL; adapter auto-detects extractor; show `✓ supported` badge from `yt_dlp` extractor list. Fallback to GenericHttp.
- [ ] **2.2 GenericHttp downloader** — `adapters/http_adapter.py`: `httpx` HEAD → `Range` 8-way chunk + merge OR delegate to bundled `aria2c` (`aria2_adapter.py`). Follow redirects, handle `Content-Disposition`, `content-length` absent fallback.
- [ ] **2.3 HLS/DASH** — reuse yt-dlp fragment logic or delegate; expose `m3u8`/`mpd` parsing via adapter (yt-dlp handles most; ensure `hls_use_mpegts`).
- [ ] **2.4 Clipboard monitor + bulk** — opt-in clipboard polling every 1s (or `pyperclip` + `Win32Clipboard`), toast "URL detected → Add to queue?". Bulk paste box (multi-line URLs). Drag-drop onto window.
- [ ] **2.5 Auth vault** — `cookies.txt` import UI, `cookies-from-browser` (chrome/firefox/edge via yt-dlp `cookiesfrombrowser`), OS `keyring` storage. No plaintext tokens in logs. `security.md` doc. Test with age-restricted + private playlist (mock).
- [ ] ** 2.6 Browser extension stub** — optional manifest v3 `extension/` that sends current page URL to local `http://127.0.0.1:8765/add` (native messaging fallback documented).
- [ ] **2.7 Gallery-dl opt-in** — `adapters/gallery_adapter.py` if `gallery-dl` installed; otherwise hint.

**DoD Phase 2:** 10-site matrix passes; direct `https://speed.hetzner.de/100MB.bin` via GenericHttp; clipboard auto-capture works; cookies auth works; no new telemetry.

---

## Phase 3 — Experience: Quality & Design [P3]

**Goal:** Queue UI, tray, thumbnails, settings — feel premium not demo.

- [ ] **3.1 Queue UI** — replace single `Progressbar:304` with table/Treeview: `Name | Size | Speed | ETA | Status | Actions (Pause/Cancel/Open)`. Per-row progress + global stats. Keep `events.py:6` bus → `root.after`.
- [ ] **3.2 Notifications & tray** — remove blocking `messagebox` in `app.py:403/_handle_error:794`; use in-app toast + status history. Add `pystray` system tray (hide to tray toggle, balloon on done).
- [ ] **3.3 Modern theme** — migrate `app.py:142 configure_styles` → CustomTkinter (or PyQt6 if DECISIONS.md says so). Single theme source, dark/light auto, no per-widget hex.
- [ ] **3.4 Thumbnails & preview** — async load `Pillow` + `httpx` cache `~/.cache/TubeGrabber/thumbnails/`, lazy viewport. `models.py:8 VideoItem.thumbnail` already has URL — wire it.
- [ ] **3.5 Format picker** — `fetch_video_formats:360` upgrade: show `ext | res | vcodec/acodec | fps | tbr | filesize` table; sort best→worst; select → enqueues that format.
- [ ] **3.6 Settings & categories** — dialog: categories (`Video/Audio/Playlist/AudioPlay/Other` subfolders), concurrent limit, chunk count, speed limits, proxy, language, cleanup TTL. Persist via `config.py`.
- [ ] **3.7 History DB** — SQLite `history.db` + search; `DownloadService:170 download_playlist` writes per-entry rows; UI `History` tab with open/retry/delete.
- [ ] **3.8 A11y & polish** — HiDPI, keyboard nav (`Tab`, `Space` pause), contrast, empty states, error empty-search messaging from `app.py:468 search_videos`.

**DoD Phase 3:** Queue UI with tray works; theme consistent; thumbnails load without blocking; history searchable; no modal popups.

---

## Phase 4 — Polish & Release [P4]

**Goal:** Installer + auto-update + docs — ready to daily-drive.

- [ ] **4.1 Installer & portable** — Inno Setup `installer.iss` + portable ZIP via CI artifact. Code-sign if available; handle `upx` exclusion for AV.
- [ ] **4.2 Auto-update** — check `yt-dlp` version (`_health_check_worker:774`) + app semver from `GitHub Releases` via `httpx`; offer "Update yt-dlp" + "Update TubeGrabber". No silent background update.
- [ ] **4.3 Auto ffmpeg** — on `ffmpeg not found` at `_discover_ffmpeg:756` prompt download `ffmpeg-static` to `~/.tubegrabber/bin/` or `ffmpeg_bundle/` fallback.
- [ ] **4.4 Docs & site** — refresh `README.md:60 Screenshots`, add `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`. Update `requirements` pins ↔ `README`.
- [ ] **4.5 Release hardening** — smoke matrix: Win10/11 × `pip` vs bundled exe × 10-site downloads × resume × cancel; record in `RELEASE_CHECKLIST.md`. Tag `v2.0.0`.
- [ ] **4.6 Post-release** — i18n scaffold (`gettext`), issue templates, discussion board.

**DoD Phase 4:** Signed installer + portable ZIP in GitHub Release; 100-job soak <5% failure; yt-dlp auto-update works.

---

## Backlog / Nice-to-Have (not P0-4)

- [ ] Gallery-dl deep integration
- [ ] Scheduler (download at 02:00 with speed caps)
- [ ] SponsorBlock auto-skip
- [ ] Chapter split / trim UI (ffprobe chapters via `FFmpegAdapter`)
- [ ] Metadata embedding preset manager
- [ ] Tauri/Qt6 full rewrite evaluation (if CustomTkinter insufficient)

---

## How to Use This File

- Pick next unchecked item in current phase — don't jump.
- For each item: `TodoWrite` plan → `Read` targets → small `Edit` → `pytest`/`python main.py` smoke → tick checkbox with `YYYY-MM-DD` + PR link.
- If you discover new debt, insert under Phase 0 and note `Discovered: <date>`.

*Sync with `PROJECT_PLAN.md` (vision) and `AGENTS.md` (rules).*
