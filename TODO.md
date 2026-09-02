# TODO — TubeGrabber Universal Downloader (Faster than IDM)

> **Execution order:** Phase 0 → 1 → 2 → 3 → 4. Do not start a later phase until its predecessor's DoD passes.
> Mark `- [x] Item (YYYY-MM-DD, PR #)` when done. Add new debt to Phase 0.
> All paths relative to repo root unless noted `path:line`.

---

## Phase 0 — Stabilise & Audit [P0 — STOP-SHIP]

**Goal:** Single codebase, one config, one spec, green CI. No feature until this passes.

- [ ] **0.1 Archive legacy** — move `main2.py` → `legacy/main2.py`, add `legacy/README.md` "frozen". Keep `main.py:1` → `tubegrabber/app.py:36` as entry. Verify `python main.py` still runs.
- [ ] **0.2 Deduplicate modules** — delete `tubegrabber/search.py` & `tubegrabber/downloaders.py` after ensuring `services/*` cover all calls. Grep `from .downloaders import`, `SearchManager`.
- [ ] **0.3 Fix config split** — refactor `tubegrabber/config.py:12` + `tubegrabber/app.py:57` + `environment.py:8` into one manager using `platformdirs` + `pydantic-settings`. Preserve `~/.tubegrabber/settings.json:11` migration. Store resolved `download_dir`, `temp_dir`, `max_concurrent`, `theme`, `chunk_size`, `speed_limit`. Add test.
- [ ] **0.4 Fix download path bug** — `services/download_service.py:48-85` use per-job `TEMP_DIR/<job_id>/` staging; `move_to_final_location:58` must handle cross-device + dedup (no silent overwrite per AGENTS.md §1.6). Remove `os.listdir(output_dir):166` leak.
- [ ] **0.5 Fix `format_has_audio`** — `utils.py:20` merge into adapter: accept `info:dict` param, deprecate network-per-call. Update `download_service.py:71` & `downloaders.py:37` call sites.
- [ ] **0.6 Fix playlist search** — `services/search_service.py:46` currently `ytsearch` → always zero for playlists. Implement correct extractor: use `YtDlpAdapter` to query `ytsearch{limit}:query` + filter **and** introduce `search_playlists_via_api` using `YoutubeSearch` or `yt_dlp.extractor.youtube.YoutubeSearchIE`; add test with mocked info. Remove subprocess `yt-dlp.exe --dump-json --flat-playlist https://.../results?sp=` in `search.py:37`.
- [ ] **0.7 Consolidate specs** — keep only `TubeGrabber.spec:52` canonical; delete/archive `main.spec`, `TubeGrabber1.spec:20` (has `E:\...` hardcode). Remove `*.spec` from `.gitignore:34` so spec is tracked. Add `pyinstaller TubeGrabber.spec --clean` smoke job.
- [ ] **0.8 Pin & prune deps** — `requirements.txt` currently unpinned (`yt-dlp`, `ffmpeg-python`, `pydub`, `requests`). Pin with hashes → `requirements.lock`. Remove unused `ffmpeg-python`/`pydub` or justify. Add `platformdirs`, `keyring`, `httpx`, `Pillow` for next phases. Keep `yt-dlp`, `requests` (or `httpx` replacement).
- [ ] **0.9 CI & quality gates** — add `.github/workflows/ci.yml`: `ruff check`, `ruff format --check`, `mypy --strict tubegrabber`, `pytest`, `bandit -r`, `pip-audit`. Pre-commit hooks. Scaffold `tests/` with mocks for `YtDlpAdapter`/`FFmpegAdapter`.
- [ ] **0.10 Logging/event fix** — `events.py:16` swallowing → log via `logging_utils.py:12`. UI `app.py:721` `EventBus` wiring must use `root.after(0, ...)`.
- [ ] **0.11 Inventory & decisions** — write `docs/DECISIONS.md` entries for: UI toolkit choice (CustomTkinter vs Qt), chunk engine (native vs aria2), config dir (`platformdirs`).

**DoD Phase 0:** `python main.py` launches, one video + audio download works staged via per-job temp, search videos + playlists returns results, `pytest` passes, CI green, only one spec remains.

---

## Phase 1 — Speed Core: Faster than IDM [P1]

**Goal:** Saturate link; queue >1 job; resume; speed control.

- [ ] **1.1 Segmented fragments** — yt-dlp opts: `concurrent_fragments=5-8` (configurable cap 16), `http_chunk_size=10M`, `retries=10`, `fragment_retries=10`. Expose `app.py:256 _discover_ffmpeg` similarly for aria2 flag. Benchmark.
- [ ] **1.2 Concurrent queue** — replace `app.py:53 active_download:bool` with `DownloadQueue` (`ThreadPoolExecutor` 3-5 workers, default 3). Model `Job {id, url, type, status, progress, speed, eta, output}`. Persist to `jobs.db` (SQLite). UI shows queue len.
- [ ] **1.3 Resume & atomic IO** — per-job `.part` files, `continue_dl:true`, `nopart:false` explicit. On cancel/failure keep partial; on retry resume. Atomic move with dedup `title (1).mp4`, cross-device fallback. Cleanup task for stale `temp/`.
- [ ] **1.4 Speed limiter** — token bucket per-job + global caps (KB/s). UI slider; persist. `yt-dlp` `throttledratelimit` & `ratelimit` options + `aria2 --max-overall-download-limit`.
- [ ] **1.5 ffmpeg passthrough** — in `FFmpegAdapter:12` use `-c copy` when merging same codec; only re-encode for mp3. Avoid double transcode.
- [ ] **1.6 Cancellation robustness** — `DownloadService:34 cancel()` must propagate to `YoutubeDL` progress hook + aria2 RPC; verify no orphan `ffmpeg` child.
- [ ] **1.7 Benchmark harness** — `tests/bench_speed.py` + `docs/BENCH.md` IDM vs TubeGrabber (1 GB fixture, throttle to 100 Mbps).

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
