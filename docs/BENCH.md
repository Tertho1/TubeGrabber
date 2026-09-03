# TubeGrabber Benchmark — vs IDM (Phase 1.7)

> Target: **1 GB file on 100 Mbps ≤20s** (IDM ~22s) with `concurrent_fragments=5` + 3-queue workers (`PROJECT_PLAN.md:9`).

## Method

- **Fixture:** `https://speed.hetzner.de/100MB.bin` (100 MB) ×10 or `https://speed.hetzner.de/1GB.bin` if available; throttle to 100 Mbps via `netsh` or router QoS.
- **TubeGrabber:** `services/download_service.py:104` `concurrent_fragment_downloads=5`, `http_chunk_size=10M`, `retries=10` + `services/queue_service.py:1` `ThreadPoolExecutor(3)` — run `tests/bench_speed.py --url <url>`.
- **IDM:** baseline 8-16 segments, same URL, same throttle.
- **Metrics:** wall time, `speed`/`eta` from `download.progress` (`app.py:768`), CPU/RAM via `psutil` (optional).

## Current (Phase 1.1-1.5)

- Single-thread baseline ~80s/GB (estimate, not yet measured) — need `bench_speed` run with real network.
- Queue 3-concurrent verified via `tests/test_queue.py:18` (`12/12 pytest`).

## How to run

```powershell
py -3 tests/bench_speed.py --url https://speed.hetzner.de/100MB.bin
# with deno + cookies for YouTube (see docs/DECISIONS.md ADR-007):
py -3 -m yt_dlp --cookies-from-browser chrome --js-runtimes deno --concurrent-fragments 5 <url>
```

## Results (fill after 1.7 run)

| Test | IDM | TubeGrabber | Notes |
|------|-----|-------------|-------|
| 1 GB/100Mbps | ~22s | TODO | run after 1.6 |
| 3× 100MB concurrent | — | TODO | queue 3 workers |

## Next

- After 1.6, run full matrix and update this doc; failure → file debt to `TODO.md Phase 0`.
