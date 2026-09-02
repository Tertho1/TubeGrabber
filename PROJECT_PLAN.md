# TubeGrabber — Project Plan: Private Universal Downloader (Faster than IDM)

> **Goal:** Evolve TubeGrabber from a 3rd-year YouTube Tkinter demo into a private, safe, zero-popup, **faster-than-IDM universal downloader** with modern UI/UX.
> **Non-goals (for v2):** Torrent DHT, cracking paywalls without credentials.
> **Sources merged:** `ANALYSIS_REPORT.md` (Claude tg-or, 2026-09-03) + prior `PROJECT_PLAN.md` (Muse Spark). Fact-checked against codebase 2026-09-03. This file is the canonical tie-breaker per `AGENTS.md:115`.

---

## 1) Vision & Success Criteria

| Pillar | Current (v1) — evidence | Target (v2) | How to measure (verifiable) |
|---|---|---|---|
| **Speed** | Single-thread `yt-dlp`, 1 job at a time (`tubegrabber/app.py:53` `active_download:bool`, `services/download_service.py:18` no `concurrent_fragments`) | 5–16 segmented connections + concurrent queue (3–5 jobs), saturate link | `tests/bench_speed.py` vs IDM: 1 GB file on 100 Mbps **target ≤20s** (IDM baseline ~22s — *target, not yet measured*); `concurrent_fragments >=5` persisted in config |
| **Versatility** | YouTube-only UI labels (`app.py:156 create_option_buttons`), `yt-dlp` supports 1800 extractors but not exposed | Any URL: yt-dlp extractors + generic HTTP (Range) + HLS/DASH + `m3u8`/`mpd` + optional `gallery-dl` | 10-site matrix (YT, Vimeo, Twitter, SoundCloud, Twitch, Insta, FB, direct MP4, m3u8, generic HTTP `speed.hetzner.de/100MB.bin`) all pass |
| **Privacy/Safety** | Local logging only (`tubegrabber/logging_utils.py:12` `RotatingFileHandler 1MB×3`) good, but `CONFIG_DIR=~/.tubegrabber/settings.json` (`environment.py:10`) in plaintext | No telemetry, OS keyring (`keyring`) for tokens, `cookies.txt` + `cookies-from-browser`, filename sanitisation, hash verify | Wireshark: zero non-yt-dlp/CDN egress; `bandit -r` 0 high; `pip-audit` 0 high; no `messagebox` modal on worker thread |
| **Quality** | Hardcoded `best/bestaudio 192k` (`tubegrabber/downloaders.py:17,22`) | User-choosable `ext/res/vcodec/acodec/fps/tbr/filesize`, lossless passthrough `-c copy` when possible | Format picker table sorted best→worst; `-c copy` verified via `ffprobe` |
| **Design** | Tk `clam` manual hex (`app.py:142 configure_styles`, `app.py:676 dark_mode` `#333333`), single global `Progressbar:304`, modal `messagebox` (`app.py:403,794`) | Queue table + per-item progress, system tray, CustomTkinter (P1) → Qt/Flet eval (P2), non-blocking toasts | SUS score >75; 0 blocking calls on UI thread; `ruff`+`mypy --strict` green |

**IDM parity matrix (Claude §2.1, fact-checked):**

| Feature | IDM | TubeGrabber v1 — evidence | Gap | Priority |
|---------|-----|---------------------------|-----|----------|
| Multi-connection (8–16 segs) | 8–16 | Single stream, no `concurrent_fragments` (`download_service.py:48`) | 🔴 Critical | P1 |
| Concurrent queue | Unlimited | 1 at a time `app.py:53` | 🔴 Critical | P1 |
| Resume/Pause | `.part` files | `continue_dl:true` only in `download_playlist:148`, not `download_video/audio` | 🔴 Critical | P1 |
| Speed limiter | Per-job + global | ❌ No | 🟡 Medium | P1 |
| Site support | 1000+ | YouTube-only UI; `yt-dlp` 1800 hidden | 🔴 Critical | P2 |
| Clipboard monitor | Auto-capture | ❌ Manual paste `app.py:187` entries | 🟡 Medium | P2 |
| Browser integration | Extension | ❌ No | 🟡 Medium | P2 |
| Categories/Folders | Auto-sort | ❌ Flat `output_dir` | 🟢 Nice | P3 |
| Queue management | Table view | ❌ Single `Progressbar` | 🔴 Critical | P3 |
| System tray | Minimize | ❌ No | 🟢 Nice | P3 |
| History/DB | SQLite | ❌ No persist | 🟡 Medium | P3 |
| Scheduler | Timed jobs | ❌ No | 🟢 Nice | Backlog |
| Auto-update | Built-in | ❌ Manual `app.py:772 _health_check_worker` check only | 🟡 Medium | P4 |

*Estimate `~30% IDM parity` (Claude) is directional, not measured — track via matrix pass rate.*

---

## 2) Current Architecture Map & Health

```
main.py:1 (14 LoC) → tubegrabber/__init__.py:3 → app.py:36 TubeGrabberApp (Tk, 811 LoC verified)
  ├─ environment.py:8  paths (DEFAULT_DOWNLOAD_DIR, TEMP_DIR, CONFIG_DIR, CONFIG_FILE)
  ├─ config.py:20      ConfigManager (bypassed by app.py:108 load_settings — see defect #5)
  ├─ adapters/ytdlp_adapter.py:13  YtDlpAdapter.extract_info / build_filename
  ├─ adapters/ffmpeg_adapter.py:12 FFmpegAdapter.run
  ├─ services/download_service.py:18  DownloadService (video/audio/playlist/convert)
  ├─ services/search_service.py:13    SearchService (ytsearch)
  ├─ models.py:8 (VideoItem/PlaylistItem), errors.py:4 (TubeGrabberError), events.py:6 (EventBus), logging_utils.py:12, utils.py:7
  └─ legacy/duplicates: main2.py:1 (1983 LoC, not ~1500), search.py:11 (SearchManager subprocess path), downloaders.py:11 (189 LoC), utils.py:20 format_has_audio
PyInstaller: TubeGrabber.spec (91 LoC, canonical) | main.spec (38 LoC) | TubeGrabber1.spec:20 (hardcoded E:\Projects\ffmpeg\bin\ffmpeg.exe)
Deps: requirements.txt:1-4 unpinned (requests, yt-dlp, ffmpeg-python, pydub) — no moviepy; no httpx/keyring/platformdirs
.gitignore:33 *.spec — hides canonical spec from git (must fix)
```

**Code health:** ~60% good (layered UI→Services→Adapters, EventBus, domain models, logging) / ~40% needs work (stop-ship defects below).

### Stop-Ship Defects (must fix before any feature — AGENTS.md §2 + fact-check extras)

| # | Location | Defect | Impact | Fix (single source of truth) |
|---|----------|--------|--------|------------------------------|
| D1 | `services/download_service.py:48-58` | Outputs directly to `output_dir` via `paths:home=output_dir`, then `move_to_final_location(temp_path=output_dir/filename, output_dir)` **no-ops**; no per-job staging | Cross-device `os.replace` fails, no atomic write, temp cleanup broken | Stage per-job `TEMP_DIR/<job_id>/` → atomic move with `shutil.move` fallback + dedup `title (1).mp4` (enforce `AGENTS.md §1.6` no silent overwrite) |
| D2 | `services/download_service.py:166` | `os.listdir(self.output_dir)` leaks all history; **also missing `import os` → NameError at runtime** | Wrong file counts, cross-contamination, crash on playlist complete | Scope to `TEMP_DIR/<job_id>/`; add `import os, shutil, uuid` |
| D3 | `services/search_service.py:46-49` | `ytsearch{limit}:query` only returns videos; filter `e["_type"]=="playlist"` → always `0` | Playlist search button → empty | Use `YtDlpAdapter` with `YoutubeTab`/`YoutubeSearchIE` or `yt_dlp.extractor.youtube`; remove `search.py:37,54` subprocess `yt-dlp --dump-json --flat-playlist https://.../results?sp=EgIQAw` path |
| D4 | `utils.py:20-27` | `format_has_audio(format_id, url)` does fresh `YoutubeDL.extract_info` per call (N+1) | Slow picker, wasted bandwidth | Accept `info:dict` param (`app.py:68-71` already fetched), deprecate network-per-call; update `services/download_service.py:71`, `downloaders.py:183` |
| D5 | `tubegrabber/config.py:12` vs `app.py:108-132` | `ConfigManager` exists but bypassed; manual `json.load(CONFIG_FILE)` with mismatched keys (`download_path` vs `download_dir`) | Inconsistent settings, migration risk | One manager: `pydantic-settings` + `platformdirs` (`%APPDATA%/TubeGrabber`, `~/Library/Application Support`, `~/.config`). Migrate `~/.tubegrabber/settings.json` with backward compat; store `download_dir,temp_dir,max_concurrent,theme,chunk_size,speed_limit` |
| D6 | `tubegrabber/app.py:53,647` | `self.active_download:bool` — only 1 download at a time | Cannot saturate bandwidth | Replace with `DownloadQueue` + `ThreadPoolExecutor(3-5)`; model `Job{id,url,type,status,progress,speed,eta,output_path}`; persist `jobs.db` (SQLite) |
| D7 | `TubeGrabber.spec / main.spec / TubeGrabber1.spec:20` + `.gitignore:33` | 3 specs, one hardcodes `E:\...`, `*.spec` gitignored so canonical not tracked | Build unreliable | Keep **1** canonical `TubeGrabber.spec`, delete/archive others, remove `*.spec` from `.gitignore` (track spec), CI smoke `pyinstaller TubeGrabber.spec --clean` |
| **D8** | `tubegrabber/utils.py:7-12` | `move_to_final_location` uses `os.replace` only — fails cross-device, no dedup | Data loss / crash on `C:`→`D:` | `shutil.move` fallback + `if exists: title (1).mp4` loop + 255-char/UTF-8 sanitise |
| **D9** | `tubegrabber/adapters/ffmpeg_adapter.py:22` | `subprocess.run` without `get_startup_info():33` on Windows | Console window flash | Add `startupinfo=get_startup_info()` per `AGENTS.md §6` |
| **D10** | `tubegrabber/events.py:16-18` | `except Exception: pass` swallows silently | Hidden failures | Log via `logging_utils.py:12` logger |
| **D11** | `tubegrabber/app.py:367` | `fetch_video_formats` does direct `YoutubeDL.extract_info` on UI thread (violates `AGENTS.md §5` layers) | UI freeze | Move to `YtDlpAdapter` + worker thread + `root.after` |
| **D12** | `adapters/ytdlp_adapter.py:55` | `.replace(".webm",".mp4")` rewrites any substring | Wrong filename | Use `info["ext"]` handling, not naive replace |

*D8–D12 were missed by both prior reports and are load-bearing.*

---

## 3) Scope of Improvements — 6 Pillars (merged)

### Pillar A — Core Engine: "Download Anything"
- **Universal URL entry:** remove YouTube-only labels `app.py:156`, accept any URL, auto-detect via `yt-dlp` `ie_key`, show badge `✓ YouTube / Vimeo / Twitter / ⚠ Generic HTTP`.
- **GenericHttp fallback:** `adapters/http_adapter.py` — `httpx` `HEAD` → `Content-Length`/`Content-Disposition`, 8–16 parallel `Range: bytes=` chunks → merge → atomic move; fallback to single stream if `Accept-Ranges: none`; bundled `aria2c` as opt-in sidecar for direct files (`aria2_adapter.py`).
- **HLS/DASH:** reuse yt-dlp fragment logic; expose `.m3u8`/`.mpd` inputs (`hls_use_mpegts`, `concurrent_fragments`).
- **Auth vault:** `cookies.txt` import UI (Netscape), `cookies-from-browser` (Chrome/Firefox/Edge via `cookiesfrombrowser`), OS `keyring` for tokens; never log URLs with tokens (`AGENTS.md §1.5`).
- **Optional `gallery-dl`:** `adapters/gallery_adapter.py` if installed, otherwise hint.
- **Metadata:** subtitles (`srt/vtt`), thumbnail embed, chapters, SponsorBlock trim (opt-in).

### Pillar B — Performance: Faster than IDM
- **Segmented fragments:** `concurrent_fragments=5–8` (cap 16 to avoid IP ban), `http_chunk_size=10M`, `retries=10` + exp backoff; `retries`/`fragment_retries` unified.
- **HTTP segmentation:** 8–16 `Range` chunks or delegate to `aria2c --split=16 --max-connection-per-server=16`.
- **Concurrent queue:** `ThreadPoolExecutor` 3–5 workers (default 3, configurable 1–10); `DownloadQueue` replaces `app.py:53`.
- **Resume & atomic I/O:** per-job `TEMP_DIR/<job_id>/`, `continue_dl:true`, `nopart:false` explicit, `.part` kept on cancel/failure, dedup + `shutil.move` cross-device; stale `temp/` cleanup task (`main2.py:1104` pattern).
- **Speed limiter:** token bucket per-job + global (KB/s), UI slider `0=unlimited → 10 MB/s`, mapped to `ratelimit`/`throttledratelimit` / `aria2 --max-download-limit`.
- **FFmpeg passthrough:** `-c copy` when merging same codecs; only re-encode for `mp3` (`FFmpegAdapter:12`).
- **Cancellation:** propagate `DownloadCancelled` via progress hook, kill orphan `ffmpeg`/`aria2` children, keep `.part` for resume.

### Pillar C — Architecture & Code Health
- **Archive legacy:** `main2.py → legacy/main2.py` frozen + `legacy/README.md`; delete `search.py`/`downloaders.py` after `Grep "from .downloaders|SearchManager"` clean; keep `main.py:1 → app.py:36`.
- **Unify config:** one `ConfigManager` with `pydantic-settings` + `platformdirs`; fix D5; add migration test for `~/.tubegrabber/settings.json`.
- **Fix D1–D4, D8–D12** (see table).
- **EventBus:** log at `events.py:16` via `logging_utils.py:12`; subscribers `app.py:721 _wire_event_subscriptions` must stay `root.after(0, ...)`.
- **History DB:** `SQLite` (`jobs.db`/`history.db`) tables `downloads(id,url,title,status,path,timestamp,extractor,retries)`; UI `History` tab search/retry/delete.
- **Auto-update health:** `app.py:774 _health_check_worker` + `app.py:756 _discover_ffmpeg` → ffmpeg auto-fetch to `~/.tubegrabber/bin/ffmpeg.exe` or `ffmpeg_bundle/`.

### Pillar D — UX/UI: Better Quality & Design
- **Toolkit:** Phase 1 CustomTkinter (drop-in, fast), Phase 2 evaluate PyQt6/Flet/Tauri — record in `docs/DECISIONS.md` (per `TODO.md 0.11`).
- **Queue table:** replace `Progressbar:304` with `Treeview` `Name | Size | Speed | ETA | Status | Actions [Pause][Cancel][Open]` + per-row progress + global stats via `events.py:6`.
- **Tray & notifications:** `pystray` tray icon, minimize-to-tray toggle, balloon toast on complete; remove blocking `messagebox` in `app.py:403,794` → in-app toast + status history + `app.py:756` health path.
- **Thumbnails:** async `httpx + Pillow`, cached `~/.cache/TubeGrabber/thumbnails/` or `thumbnails/`, lazy viewport, non-blocking (never `Pillow` on UI thread).
- **Format picker:** upgrade `app.py:360 fetch_video_formats` → table `Ext | Resolution | VCodec | ACodec | FPS | TBR | Filesize` sorted best→worst, size estimate.
- **Settings dialog:** tabs General/Performance/Categories/Privacy/Advanced; categories auto-sort `Video/ Audio/ Playlist/ Other/`; proxy/user-agent/custom yt-dlp args.
- **Polish:** `app.py:142,675` remove manual hex → theme system with OS auto-detect; HiDPI/Retina, keyboard `Ctrl+V` paste / `Space` pause / `Del` remove, WCAG 2.1 AA contrast, empty states, actionable error copy.
- *Claude metric to track:* `messagebox` instances `12 → 0`.

### Pillar E — Privacy / Safety / No Popups
- Zero telemetry: CI egress test (Wireshark capture 10 downloads → assert zero non-yt-dlp/CDN); local logs only `logging_utils.py:22` rotation.
- Secure creds: `keyring` + OS encryption, never log URLs with tokens.
- Filename safety: sanitise `../` `<>:"|?*` path traversal, max 255 chars, UTF-8 safe.
- Download safety: HTTPS-only warning, max file-size guard (default 10 GB), SHA256 verify when provided, VirusTotal opt-in (user API key).
- No popups/ads: replace all modals with toast + status label + history entry.

### Pillar F — Distribution & Quality
- One canonical `TubeGrabber.spec` (no `E:\` hardcode), tracked in git (fix `.gitignore:33`), test `pyinstaller TubeGrabber.spec --clean` + `pyinstaller --clean`.
- FFmpeg auto-download on first launch (`app.py:756`) or bundle `ffmpeg-static` with license notice.
- Installer: Inno Setup `installer.iss` → `TubeGrabber-Setup.exe` + portable `TubeGrabber-Portable.zip` (`config/` relative); code-sign to reduce SmartScreen.
- Pin deps: `requirements.txt` + `requirements.lock` with hashes; pin `yt-dlp`, `httpx>=0.27`, `Pillow>=10.0`, `platformdirs`, `keyring`; remove/unjustify `ffmpeg-python`/`pydub`; keep `python 3.11+`.
- CI `.github/workflows/ci.yml`: `ruff check` + `format --check`, `mypy --strict tubegrabber`, `pytest` (≥60% on `services/`+`adapters/` with mocked adapters), `bandit -r`, `pip-audit`, pre-commit.
- Release: GitHub Actions on `tag v2.x.x` → `.exe` + `.zip` + `CHANGELOG.md` from commits; auto-update check `yt-dlp --version` + app semver via `httpx` (prompt, never silent).

---

## 4) Phased Roadmap — 7–11 weeks (execution order is law per TODO.md)

### Phase 0 — Stabilise & Audit [1–2 wks] — **DO NOT SKIP**
- [ ] 0.1 Archive legacy `main2.py → legacy/` (TODO 0.1)
- [ ] 0.2 Dedup `search.py`/`downloaders.py` (0.2)
- [ ] 0.3 Unify config `platformdirs`+`pydantic-settings` (0.3, D5)
- [ ] 0.4 Fix D1/D2/D8 path & atomic I/O (0.4)
- [ ] 0.5 Fix `format_has_audio` D4 (0.5)
- [ ] 0.6 Fix playlist search D3 (0.6)
- [ ] 0.7 Consolidate specs `.gitignore:33` (0.7, D7)
- [ ] 0.8 Pin & prune deps (0.8)
- [ ] 0.9 CI + `tests/` scaffold mocks (0.9)
- [ ] 0.10 Fix `events.py:16` + `ffmpeg_adapter.py:22` + `app.py:367` (0.10, D9–D11)
- [ ] 0.11 `docs/DECISIONS.md` (toolkit/chunk engine/config dir) (0.11)

**DoD:** `python main.py` launches, 1 video+audio via per-job temp works, `search_videos`+`search_playlists` return results, `pytest` pass, CI green, **1 spec** only.

### Phase 1 — Speed Core [2–3 wks]
- [ ] 1.1 `concurrent_fragments 5-8`, `http_chunk_size 10M`, `retries 10` (1.1)
- [ ] 1.2 `DownloadQueue` `ThreadPoolExecutor 3-5` replaces `active_download` (1.2, D6)
- [ ] 1.3 Resume `.part`, atomic dedup, cross-device, stale cleanup (1.3)
- [ ] 1.4 Token-bucket speed limiter + UI slider (1.4)
- [ ] 1.5 FFmpeg `-c copy` passthrough (1.5)
- [ ] 1.6 Cancellation robust + no orphan `ffmpeg` (1.6)
- [ ] 1.7 `tests/bench_speed.py` + `docs/BENCH.md` IDM vs TubeGrabber (1.7)

**DoD:** 3 parallel downloads saturate link (target ≤20s/GB/100Mbps), pause/resume survives app kill, limiter respected, no `active_download` global.

### Phase 2 — Universal [2–3 wks]
- [ ] 2.1 Generic URL entry + extractor badge (2.1)
- [ ] 2.2 `GenericHttp` `httpx` Range 8-way + `aria2c` path (2.2)
- [ ] 2.3 HLS/DASH `m3u8`/`mpd` (2.3)
- [ ] 2.4 Clipboard monitor + bulk paste + drag-drop (2.4)
- [ ] 2.5 Auth vault `cookies.txt` + `keyring` + `cookies-from-browser` (2.5)
- [ ] 2.6 Browser extension stub `http://127.0.0.1:8765/add` (2.6)
- [ ] 2.7 `gallery-dl` opt-in adapter (2.7)

**DoD:** 10-site matrix passes; `https://speed.hetzner.de/100MB.bin` via GenericHttp; clipboard & cookies work; no new telemetry.

### Phase 3 — Experience [2–3 wks]
- [ ] 3.1 Queue `Treeview` (3.1)
- [ ] 3.2 Toast + `pystray` tray, remove `messagebox` (3.2)
- [ ] 3.3 CustomTkinter theme migration (3.3)
- [ ] 3.4 Async thumbnails + cache (3.4)
- [ ] 3.5 Format picker table (3.5)
- [ ] 3.6 Settings & categories (3.6)
- [ ] 3.7 History DB `history.db` (3.7)
- [ ] 3.8 A11y/HiDPI/keyboard polish (3.8)

**DoD:** Queue+tray works, theme consistent, thumbnails non-blocking, history searchable, **0 modal popups**.

### Phase 4 — Polish & Release [1–2 wks]
- [ ] 4.1 Inno Setup + portable ZIP (4.1)
- [ ] 4.2 Auto-update `yt-dlp` + app (4.2)
- [ ] 4.3 Auto ffmpeg fetch (4.3)
- [ ] 4.4 Docs `SECURITY.md`/`CONTRIBUTING.md`/`CHANGELOG.md` + README refresh (4.4)
- [ ] 4.5 `RELEASE_CHECKLIST.md` smoke matrix Win10/11 × pip/exe × 10-site × resume × cancel; tag `v2.0.0` (4.5)
- [ ] 4.6 i18n scaffold (4.6)

**DoD:** Signed installer + portable ZIP in GitHub Release; 100-job soak `<5%` failure; updater works.

---

## 5) Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| yt-dlp breakage (YouTube changes) | High | Medium | Pin + auto-update check, extractor health test in CI, fallback `yt-dlp nightly` |
| FFmpeg bundling bloat/licensing | Medium | Low | Download on first run **or** bundle `ffmpeg-static` + license notice; portable option |
| AV false positive (PyInstaller) | Medium | Medium | Code-sign, `upx=False`, MS Defender whitelist submission |
| Tk threading races (`root.after` vs threads) | High | Medium | Centralise `EventBus → root.after(0, ...)`, `queue.Queue` + `after(50,poll)`; never `messagebox` on worker |
| Scope creep to torrent/DRM | Low | Low | Explicit non-goals + `AGENTS.md §3` guardrail |
| Performance not beating IDM | Medium | Low | Benchmark early P1.7, tune `concurrent_fragments`/`chunks`, `aria2` fallback |

---

## 6) Out of Scope for v2
Torrents without user engine, DRM circumvention beyond credentialed access, cloud sync, mobile build, streaming proxy/local media server, video editor beyond SponsorBlock auto-skip.

---

## 7) Definition of Done for v2.0 (all must be green)
- [ ] 10-site matrix passes (YT, Vimeo, Twitter, SoundCloud, Twitch, Insta, FB, direct MP4, m3u8, generic HTTP)
- [ ] Speed: 3 concurrent jobs saturate 100 Mbps; **target** 1 GB ≤20s (measured in `docs/BENCH.md`)
- [ ] Resume: pause/cancel/kill → resume, no data loss, `.part` kept
- [ ] No popups/ads: 0 `messagebox` on worker thread, zero telemetry (CI egress check)
- [ ] Installer: signed `.exe` + portable `.zip`
- [ ] Stability: <5% crash on 100-job soak
- [ ] Tests: CI green `ruff`+`mypy --strict`+`pytest ≥60%` (`services/`+`adapters/`)+`bandit`+`pip-audit`
- [ ] Docs: README screenshots + `SECURITY.md` + `CHANGELOG.md` updated; `requirements.txt` ↔ README pins match

---

## 8) Technology Stack — Current → Target

| Layer | Current (v1) | Target (v2) | Rationale |
|-------|--------------|-------------|-----------|
| Language | Python 3.12 (dev) | Python 3.11+ | Back compat |
| UI | Tkinter `clam` (`app.py:142`) | CustomTkinter (P1), PyQt6/Flet eval (P2) | Modern, single theme |
| Downloader | `yt-dlp` only (`ytdlp_adapter.py:13`) | `yt-dlp` + `httpx` + `aria2c` opt-in | Universal + speed |
| Media | FFmpeg manual (`_discover_ffmpeg:756`) | Bundled or auto-download `~/.tubegrabber/bin/` | Standalone |
| Config | JSON manual (`app.py:108`) | `pydantic-settings` + `platformdirs` | Type-safe, OS paths |
| DB | None | SQLite `jobs.db`/`history.db` | Persistence |
| Auth | None | `keyring` + `cookies.txt` + `cookies-from-browser` | Secure vault |
| Concurrency | `threading.Thread daemon` | `ThreadPoolExecutor` + queue | Concurrency |
| Testing | None | `pytest` + `mypy` + `ruff` + `bandit` | Gates |
| Packaging | 3 specs, `*.spec` ignored | 1 spec tracked + Inno Setup | Installer |

---

## 9) Metrics & Success Criteria

**Speed (target, not yet measured):** `1 GB/100Mbps` IDM ~22s → v2 **≤20s** with `concurrent_fragments 8` + 3 jobs parallel; fallback single-thread ~80s baseline is **estimate** — replace with `tests/bench_speed.py` result.

**Code quality:** coverage `0% → ≥60%` (`services/`+`adapters/` mocked), `mypy --strict` 0 errors, `bandit` 0 high, duplication `~1983 LoC` (`main2.py`) → 0.

**UX:** modals `12 → 0`, all network/ffmpeg off UI thread, settings persisted via one manager, theme Light/Dark auto.

---

## 10) Appendix A — File Inventory (fact-checked)

```
TubeGrabber/
├── main.py (14 LoC) ✅
├── main2.py (1983 LoC) ⚠️ → legacy/
├── TubeGrabber.spec (91 LoC) ✅ canonical
├── main.spec (38 LoC) ⚠️ delete
├── TubeGrabber1.spec (58 LoC) ⚠️ hardcode E:\... delete
├── tubegrabber/
│   ├── app.py (811 LoC) ⚠️ D6/D11
│   ├── config.py (48 LoC) ⚠️ D5
│   ├── environment.py (42 LoC) ✅
│   ├── errors.py (21 LoC) ✅
│   ├── events.py (19 LoC) ⚠️ D10
│   ├── logging_utils.py (36 LoC) ✅
│   ├── models.py (26 LoC) ✅
│   ├── utils.py (27 LoC) ⚠️ D4/D8
│   ├── search.py (127 LoC) ⚠️ delete (superseded by search_service)
│   ├── downloaders.py (189 LoC) ⚠️ delete (superseded by download_service)
│   ├── adapters/ytdlp_adapter.py (55 LoC) ⚠️ D12
│   ├── adapters/ffmpeg_adapter.py (34 LoC) ⚠️ D9
│   └── services/{download_service.py (171 LoC) ⚠️ D1/D2, search_service.py (77 LoC) ⚠️ D3}
├── requirements.txt (unpinned) ⚠️
├── .gitignore:33 *.spec ⚠️ fix
├── AGENTS.md / TODO.md / PROJECT_PLAN.md (this file) ✅
└── ANALYSIS_REPORT.md (699 LoC, reference) ✅
```

---

## 11) Appendix B — Quick Wins (7 hours → massive stability gain — Claude)

1. Fix playlist search D3 (2h) — unblocks search
2. Delete legacy/duplicates (1h) — reduces confusion
3. Pin requirements (1h) — reproducible builds
4. Fix `format_has_audio` D4 (1h) — 10× faster picker
5. Add `ruff` + pre-commit (2h) — quality baseline

---

*This plan is constraint for agents — see `AGENTS.md` (§2 stop-ship, §5 layers, §6 quality bar) and `TODO.md` (phase order). No code without phase alignment; one concern per commit <300 LoC; verify by `python main.py` + `pytest` + `ffmpeg -version` + `yt-dlp --version`.*
