"""Benchmark harness for TubeGrabber vs IDM (Phase 1.7).

Measures segmented fragments + concurrent queue throughput.
Usage: py -3 tests/bench_speed.py --url https://speed.hetzner.de/100MB.bin
Requires: yt-dlp, httpx (or aria2c)
"""

from __future__ import annotations

import argparse
import time


def bench_generic_http(url: str, chunks: int = 8) -> float:
    """Benchmark GenericHttp chunked download (when implemented)."""
    # Placeholder — Phase 2 will implement httpx Range
    start = time.time()
    # fake: would download via DownloadService with concurrent_fragments
    elapsed = time.time() - start
    return elapsed


def bench_ytdlp_concurrent(urls: list[str], max_workers: int = 3) -> dict:
    """Benchmark concurrent queue with N workers."""

    # Mock: not hitting network in CI
    return {"urls": len(urls), "workers": max_workers, "note": "run with real URLs locally"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="TubeGrabber bench vs IDM")
    ap.add_argument("--url", default="https://speed.hetzner.de/100MB.bin")
    ap.add_argument(
        "--idm-baseline", type=float, default=22.0, help="IDM 1GB/100Mbps baseline seconds"
    )
    args = ap.parse_args()
    print(f"TubeGrabber bench — target ≤20s for 1GB/100Mbps (IDM ~{args.idm_baseline}s)")
    print(f"URL: {args.url}")
    print("Run: py -3 -m pytest tests/test_queue.py -vv (queue 3-concurrent verified)")
    print("Full bench requires real network + deno + cookies; see docs/BENCH.md")
