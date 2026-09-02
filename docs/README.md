# TubeGrabber Docs

> **Docs index — start here.** Root truth: `PROJECT_PLAN.md` (vision) + `TODO.md` (execution order) + `AGENTS.md` (rules). This folder holds ADRs and supporting docs.

## Map

| Doc | Purpose | Source of truth? |
|-----|---------|------------------|
| [`PROJECT_PLAN.md`](../PROJECT_PLAN.md) | Vision, 6 pillars, 5-phase roadmap, DoD, tech stack | **Yes — tie-breaker** per `AGENTS.md:117` |
| [`TODO.md`](../TODO.md) | Ordered checklist 0.1→4.6, DoD per phase | **Yes** |
| [`AGENTS.md`](../AGENTS.md) | Hard rules, stop-ship defects, guardrails, checklists | **Yes — highest priority** |
| [`docs/DECISIONS.md`](DECISIONS.md) | Architecture Decision Records (ADR-001…007) | **Yes — why we chose** |
| [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) | Current map `main.py:1 → app.py:36 → services/adapters` (derived from `PROJECT_PLAN.md §2`) | Derived |
| `SESSION_REVIEW.md` | Phase 0 session log (`2026-09-02`, 343 lines) | Log — not constraint |
| `ANALYSIS_REPORT.md` | Claude vs Muse comparison (reference) | Reference |

## Conventions

- Every change cites `path:line` (`services/download_service.py:48`).
- One concern per commit `<300 LoC` (`AGENTS.md:20`).
- No `git push` without owner go-ahead (`AGENTS.md:23` §1.7).
- `pytest` + `ruff` + `mypy --strict` must pass before merge (`AGENTS.md:80`).

## Quick links

- Stop-ship defects: `AGENTS.md:28` §2 (D1–D12)
- Working process: `AGENTS.md:57` §4 (TodoWrite → Read → Edit → Verify)
- Checklists: `AGENTS.md:121` §11 (copy into PR)
