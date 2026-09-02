# TubeGrabber — Architecture Decision Records (ADR)

> Track why we chose a path, not just what. Update when a decision is superseded.
> Index: [`docs/README.md`](README.md) | Truth: `PROJECT_PLAN.md` + `TODO.md` + `AGENTS.md:117`

## Status table

| ADR | Title | Status | Date | Commit |
|-----|-------|--------|------|--------|
| ADR-001 | Config `platformdirs` + `pydantic-settings` | Accepted | 2026-09-02 | `016f563` |
| ADR-002 | UI CustomTkinter P1, Qt eval P2 | Accepted | 2026-09-02 | `docs/DECISIONS.md` |
| ADR-003 | Chunk engine native `yt-dlp`/`httpx`, `aria2c` optional | Accepted | 2026-09-02 | `docs/DECISIONS.md` |
| ADR-004 | Download isolation `TEMP_DIR/<job_id>/` | Accepted | 2026-09-02 | `bc3153a` |
| ADR-005 | Single spec `TubeGrabber.spec` canonical | Accepted | 2026-09-03 | `8575c16` |
| ADR-006 | Push/Commit guardrail `AGENTS.md:23` | Accepted | 2026-09-03 | `8575c16` |
| ADR-007 | YouTube bot/429 + JS runtime mitigation | Proposed | 2026-09-03 | — (see smoke log `2026-09-03`) |

### How to add an ADR

Copy template: `## ADR-00N: Title` → Context / Decision / Consequences / Verify. Set Status `Proposed → Accepted → Superseded`. Link `path:line`.

---

## ADR-001: Config paths — `platformdirs` + `pydantic-settings`

**Context:** `environment.py:8` used `~/.tubegrabber` and `app.py:108` bypassed `config.py:20`. Needed OS-appropriate paths and validation per `PROJECT_PLAN.md Pillar C` and `TODO.md 0.3`.

**Decision:** Use `platformdirs` (`user_config_dir`, `user_data_dir`, `user_cache_dir`) + `pydantic-settings` `TubeGrabberSettings` (`config.py:17`). `ConfigManager:60` now single source, with `legacy_config = Path.home()/.tubegrabber/settings.json:77` migration `config.py:81`.

**Consequences:**
- Windows: `%APPDATA%\TubeGrabber\settings.json` (single level, `appauthor=False` to avoid double-nesting `TubeGrabber/TubeGrabber`)
- macOS: `~/Library/Application Support/TubeGrabber`
- Linux: `~/.config/tubegrabber`
- Old `~/.tubegrabber/settings.json` auto-migrated on first load
- Validation `ge/le` for `max_concurrent_downloads 1-10`, `concurrent_fragments 1-16` (`config.py:33-34`)

**Verify:** `tests/test_config.py:8` — default, save/load, legacy migration.

---

## ADR-002: UI toolkit — CustomTkinter Phase 1, Qt eval Phase 2

**Context:** Current UI `tubegrabber/app.py:36` Tk `clam` with manual hex `app.py:142,675`. Need modern theme without full rewrite risk (`PROJECT_PLAN.md Pillar D`).

**Decision:** **Phase 1** migrate to `CustomTkinter` (drop-in, keeps `tk` event loop, `root.after` wiring `app.py:721` unchanged). **Phase 2** evaluate `PyQt6`/`Flet`/`Tauri` if CustomTk insufficient for queue table HiDPI/a11y.

**Rejected:** Immediate PyQt6 — requires `QApplication` rewrite, larger `pyinstaller` bundle, signal/slot threading changes.

**Consequences:** Single theme source, Light/Dark/System via `config.settings.theme`, `app.py:676 toggle_dark_mode` removed per-widget hex. Queue `Treeview` → `CTkTable` later.

---

## ADR-003: Chunk engine — native `yt-dlp`/`httpx` first, `aria2c` sidecar optional

**Context:** Need faster-than-IDM `concurrent_fragments 5-8` + `http_chunk_size 10M` (`PROJECT_PLAN.md Pillar B`), but `aria2c` adds external binary and licensing.

**Decision:** **Native first:** `yt-dlp` `concurrent_fragment_downloads` for HLS/DASH + `httpx` `Range` 8-16 chunks with merge for GenericHttp (`adapters/http_adapter.py` planned Phase 2). **Optional** `aria2c` via `aria2_adapter.py` sidecar, invoked when `aria2c` in PATH or `~/.tubegrabber/bin/`.

**Consequences:** No mandatory `aria2` install for v2; speed via `concurrent_fragments` already ~saturates link. Fallback `aria2 --split=16 --max-connection-per-server=16` for users needing max speed. Keeps bundle small.

---

## ADR-004: Download isolation — per-job `TEMP_DIR/<job_id>/`

**Context:** `services/download_service.py:48` wrote directly to `output_dir` then `move_to_final_location` no-op, `download_service.py:166` `os.listdir(output_dir)` leaked history (`AGENTS.md §2 D1/D2`).

**Decision:** `DownloadService:49 _get_job_temp_dir()` → `temp_base/uuid4().hex[:8]` (later switch to `uuid4().hex` + job registry for queue). `utils.py:55 move_to_final_location` handles `shutil.move` cross-device + `get_unique_path` dedup + `sanitize_filename`.

**Verify:** `tests/test_download_paths.py:39` — atomic + dedup.

---

## ADR-005: Single spec — `TubeGrabber.spec` canonical

**Context:** 3 specs (`TubeGrabber.spec`, `main.spec`, `TubeGrabber1.spec:20` hardcode `E:\...`) and `.gitignore:33` `*.spec` hid canonical.

**Decision:** Keep `TubeGrabber.spec` (91 LoC) canonical, tracked in git; delete `main.spec`/`TubeGrabber1.spec`; remove `*.spec` from `.gitignore` (now comment), add `ffmpeg_bundle/` ignore, untrack `build/`/`dist/` binaries.

**Verify:** `pyinstaller TubeGrabber.spec --clean` smoke in `ci.yml` job `build-spec-smoke`.

---

## ADR-006: Push/Commit guardrail

**Context:** Need to prevent AI/human pushing without owner approval per `AGENTS.md §1.7`.

**Decision:** `AGENTS.md:23` — no `git commit/push/tag/PR` without explicit owner instruction in conversation; local `git diff` allowed; `draft` branch for checkpoint commits if needed.

---

## ADR-007: YouTube bot/429 + JS runtime mitigation (Proposed)

**Context:** `py -3 main.py` smoke `2026-09-03` hit `WARNING: [youtube] KvMY1uzSC1E: HTTP Error 429` + `No supported JavaScript runtime` + `ERROR: Sign in to confirm you're not a bot` (`adapters/ytdlp_adapter.py:42`). YouTube now requires `deno`/`node` for `nsig` and `cookies-from-browser` for authenticated extract (`yt-dlp/wiki/EJS`, `FAQ#cookies`). Our `retries=3` (`services/download_service.py:186`) insufficient.

**Decision (proposed):** Bring `TODO.md 2.5` forward as patch: `adapters/ytdlp_adapter.py:17` add `retries=10, fragment_retries=10, extractor_retries=3, sleep_interval_requests=1`, `js_runtimes: {"deno": {}}` auto-detect, pass `cookies`/`cookiesfrombrowser` from `config.py:51` `TubeGrabberSettings` (stored via `keyring`/`platformdirs`). UI `File → Import cookies.txt` (`app.py:304` menu) + `Settings → Browser cookies` dropdown. Map `ExtractionError` → toast `Sign-in required — import cookies` (`app.py:794`).

**Consequences:** Unauthenticated YouTube will still 429 without JS/cookies; with `deno` + `cookies-from-browser chrome` smoke passes. No telemetry added.

---

## Open decisions (Phase 1+)

- Speed limiter token-bucket (per-job vs global caps)
- Queue persistence `jobs.db` schema (SQLite vs `sqlalchemy`)
- Thumbnail cache `user_cache_dir/Thumbnails` vs `thumbnails/`
- Auth vault UI placement (Settings tab vs toolbar badge)
