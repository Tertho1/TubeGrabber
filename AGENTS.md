# AGENTS.md — Rules for AI & Human Agents Working on TubeGrabber

> **Read this first. Every change must obey these rules. When in doubt, ask the owner instead of guessing.**

---

## 0) Project Identity — Do Not Drift

- **What this is:** TubeGrabber is a **private, safe, zero-popup universal downloader** (evolved from a 3rd-year Python demo). Goal is **faster than IDM**, versatile (any URL via `yt-dlp` + generic HTTP), high-quality, modern design. See `PROJECT_PLAN.md` for vision.
- **What this is NOT:** Adware, telemetry collector, DRM cracker, torrent indexer. Never add popups, ads, tracking, or paywall bypass without credentials.
- **Primary entry:** `main.py:1` → `tubegrabber/app.py:36`. Legacy `main2.py:59` is **frozen** — do not edit except to archive. Canonical business logic lives in `tubegrabber/services/*` + `adapters/*`.

---

## 1) Prime Directives (Hard Rules)

1.  **Do NOT write code unasked? Now you may — but never rashly.** The earlier "dont start writing codes" is lifted only via `TODO.md` phase order. Still: no bulk rewrites without a `TodoWrite` plan and user go-ahead for cross-cutting changes.
2.  **Evidence before synthesis.** Read the file you claim to change. Quote `path:line` when referencing behaviour (e.g., `services/download_service.py:166`). Never invent URLs/APIs.
3.  **Verify by execution.** After any feature/fix: run the relevant path (`python main.py` smoke, `pytest`, `ffmpeg -version`, `yt-dlp --version`). If you cannot run, say so — do not fake pass.
4.  **One concern per commit.** No mixing of refactor + feature + spec change in one commit. Keep diffs reviewable (<300 LoC).
5.  **No secrets in repo.** No cookies, tokens, keys, signed binaries credentials. Use OS `keyring` or `~/.tubegrabber/secrets` git-ignored and documented in `security.md`.
6.  **No silent data loss.** `utils.py:7 move_to_final_location` must never overwrite user data silently — dedup or prompt. Enforce before changing IO.
7.  **No push/commit without explicit owner approval.** No agent (human or AI) may `git commit`, `git push`, `gh pr create`, `git tag` or publish releases without the owner's direct instruction in this conversation. Local edits and `git diff` are allowed; pushing to `origin` is blocked. If you need a commit for checkpointing, ask first and use `draft` branch only.

---

## 2) Stop-Ship Defects — Must Fix Before Any New Feature

Any agent touching downloads must acknowledge these or refuse to add features:

- `services/download_service.py:48-85` temp vs output path confusion (outputs directly to `output_dir` then tries to move). Must stage in per-job `TEMP_DIR/<job_id>/`.
- `services/download_service.py:166` `os.listdir(output_dir)` leaks all history — scope to job temp.
- `services/search_service.py:46` playlist search returns zero ( `ytsearch` only videos). Needs extractor fix.
- `utils.py:20` `format_has_audio` does extra network fetch per call — reuse `info` already fetched in `app.py:68-71`.
- `tubegrabber/app.py:53` single global `active_download` blocks queue — queue design required.
- `tubegrabber/config.py:20` vs `app.py:108` config bypass — unify via one manager.
- Triple spec (`TubeGrabber.spec`, `main.spec`, `TubeGrabber1.spec:20` hardcode `E:\...`) — keep one canonical.

---

## 3) Scope Guardrails — What Agents MUST NOT Do

| Never Do | Why | Do Instead |
|---|---|---|
| Add telemetry, ads, popups, auto-launch on boot without opt-in | Violates private/safe promise | Add opt-in toggle with docs |
| Bypass paywall/DRM without user-supplied cookies/creds | Legal/ethical | Implement `cookies.txt` import + credential vault |
| Add new dependency without pin + justification | Supply-chain risk | Propose in PR desc, update `requirements.txt` + `requirements.lock`, `pip-audit` |
| Edit `main2.py` for new features | Divergent codebase | Archive to `legacy/` and edit `tubegrabber/*` |
| Mass-rename files or change `DEFAULT_DOWNLOAD_DIR` default path silently | Breaks user data | Migration step + changelog + setting |
| Commit `dist/`, `build/`, `ffmpeg/` binaries, `*.log`, `downloads/` | Bloat + leak | Ensure `.gitignore` covers it; use release artifacts |
| Push/commit/tag/PR without owner go-ahead | Violates §1.7 approval gate | Stage locally, show `git diff`, ask for `git push` explicitly |
| Force-push, rewrite git history, skip hooks | Irreversible | Ask owner |
| Use `Write` to overwrite `PROJECT_PLAN.md`/`AGENTS.md`/`TODO.md` without explicit request | Source of truth | Propose diff via `Edit` with rationale |

---

## 4) Working Process (Required)

1.  **Plan:** Create `TodoWrite` for any task >2 steps. For multi-file work, open a `Task` subagent per workstream with explicit prompt.
2.  **Inspect:** `Read` target files fully before `Edit`. Use `Grep`/`Glob` to find all call sites (e.g., `Grep pattern="format_has_audio"` before changing signature).
3.  **Change small:** Prefer `Edit` with minimal `oldString`. Set `replaceAll=false` unless renaming. After edit, `Read` the edited region to confirm preservation constraints.
4.  **Parallelism:** Independent tools (e.g., `Read app.py` + `Read download_service.py`) in parallel via one turn. Dependent steps sequential.
5.  **Local compute:** Use `bash python3 -c` for quick parsing/stats, not mental math.
6.  **Communicate:** Responses short, factual, no praise/superlatives, include `path:line` refs. After `Task` delegation, summarize hypotheses vs evidence, flag any load-bearing issue clearly.

---

## 5) Architecture Constraints

- **Layers:** `UI (app.py)` → `Services` → `Adapters (ytdlp_adapter.py:13, ffmpeg_adapter.py:12)` → external (`yt-dlp`, `ffmpeg/aria2`). UI never calls `yt_dlp.YoutubeDL` directly except via adapter (exception `app.py:367` format fetch — migrate it).
- **Error flow:** Raise domain errors (`errors.py:4 TubeGrabberError` hierarchy) in services; UI maps via `app.py:794 _handle_error`. Don't `raise RuntimeError` in services (`downloaders.py:37` does — fix to domain errors).
- **Events:** `events.py:6 EventBus` is UI-marshaling only; publishers (`DownloadService:38`) publish, subscribers (`app.py:721 _wire_event_subscriptions`) do `root.after(0, ...)`. Never call `messagebox` from service thread.
- **Config:** One manager. Prefer `platformdirs` for paths. Migration must preserve existing `~/.tubegrabber/settings.json` or `CONFIG_FILE:11`.
- **Build:** One spec = `TubeGrabber.spec`. Any change must test `pyinstaller TubeGrabber.spec` dry-run and `pyinstaller --clean`.

---

## 6) Code Quality Bar

- **Typing:** Add `from __future__ import annotations`, type hints on public functions. `mypy --strict` on `tubegrabber/*` must pass before merge.
- **Lint:** `ruff check` + `ruff format` clean.
- **Security:** `bandit -r tubegrabber`, `pip-audit`. No `subprocess` without `get_startup_info():33` on Windows.
- **Tests:** New service logic needs `pytest` unit test with mocked `YtDlpAdapter`/`FFmpegAdapter`. Aim ≥60% on `services/` + `adapters/`. No manual QA-only merges.
- **Logging:** Use `logging_utils.py:12` logger, never `print`. Don't log URLs with tokens.
- **Commits:** Conventional `feat:`, `fix:`, `refactor:`, `docs:`, `build:`; reference `TODO.md` item ID.

---

## 7) UI/UX Rules

- No modal `messagebox` for progress/completion in worker threads — use toast + status label + history entry.
- Dark mode via theme, not manual `style.configure` hex per widget (`app.py:675`). If migrating to CustomTkinter/Qt, keep one theme source.
- Thumbnail loading must be async + cached (`thumbnails/`), never block UI thread.
- Accessibility: keyboard navigable, focus order, contrast.

---

## 8) Performance Rules

- Never add synchronous network/ffmpeg on UI thread. Use `threading.Thread(..., daemon=True)` → later `ThreadPoolExecutor` queue. Always `root.after` for UI updates.
- Default `concurrent_fragments >=5`, `http_chunk_size` tuned; make configurable but caps `max 16` to avoid IP ban.
- Temp files per-job, cleanup on cancel/failure. Verify via `_cleanup_temp_files` pattern in legacy `main2.py:1104`.

---

## 9) Documentation Duties

- When you close a `TODO.md` item, update its checkbox `- [x]` + date + PR link.
- Keep `PROJECT_PLAN.md`, `TODO.md`, this file in sync — if you discover new debt, add to `TODO.md` Phase 0.
- README `Requirements` section must match `requirements.txt` pins.

---

## 10) When to Stop and Ask

- Any change that would: delete user downloads, change default dirs, add network egress beyond `yt-dlp`/`ffmpeg`/`aria2`, require admin, or touch signing/packaging with hardcoded absolute paths.
- If you see contradictory instructions across `PROJECT_PLAN.md` / `TODO.md` / this file — treat this file + `PROJECT_PLAN.md` as tie-breaker and ask.

---

## 11) Checklists (Copy into PR Description)

**Pre-edit:**
- [ ] Read target file(s) & call sites via `Grep`
- [ ] `TodoWrite` plan for >2 steps
- [ ] No stop-ship defect ignored

**Pre-merge:**
- [ ] `ruff`, `mypy`, `pytest`, `bandit` green (or noted why not)
- [ ] Manual smoke `python main.py` + one download (video+audio) tested
- [ ] No secret, no `dist/build/ffmpeg` committed, spec still builds
- [ ] Docs (`PROJECT_PLAN`/`TODO`) updated, `path:line` refs in notes

---

*Violations of §1-§3 are reversible but costly. Prefer asking over rushing. The user's trust depends on careful agents.*
