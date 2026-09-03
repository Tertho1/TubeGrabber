"""Concurrent download queue for TubeGrabber (Phase 1.2).

Replaces app.py:53 active_download:bool with ThreadPoolExecutor 3-5 workers.
Persists minimal job state; SQLite persistence added in 1.3.
"""

from __future__ import annotations

import concurrent.futures
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ..errors import DownloadCancelled
from ..events import EventBus


class JobStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    url: str = ""
    kind: str = "video"  # video|audio|playlist|playlist_audio|convert
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0  # 0-100
    speed: float = 0.0
    eta: int = 0
    output_path: Path | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None


class DownloadQueue:
    """Thread-safe queue with 3-5 workers, job tracking, and EventBus integration."""

    def __init__(
        self,
        max_workers: int = 3,
        event_bus: EventBus | None = None,
        logger=None,
    ) -> None:
        self.max_workers = max(1, min(max_workers, 10))
        self.event_bus = event_bus
        self.logger = logger
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="tg-queue"
        )
        self._jobs: dict[str, Job] = {}
        self._futures: dict[str, concurrent.futures.Future] = {}
        self._lock = threading.Lock()
        self._active_count = 0

    def _publish(self, event: str, payload: Any = None) -> None:
        if self.event_bus:
            self.event_bus.publish(event, payload)

    def submit(
        self,
        func: Callable[..., Any],
        *args: Any,
        url: str = "",
        kind: str = "video",
        **kwargs: Any,
    ) -> str:
        """Enqueue a download callable; returns job_id."""
        job = Job(url=url, kind=kind, status=JobStatus.QUEUED)
        with self._lock:
            self._jobs[job.id] = job
        self._publish("queue.job_queued", job)

        def _run():
            with self._lock:
                job.status = JobStatus.DOWNLOADING
                job.started_at = time.time()
                self._active_count += 1
            self._publish("queue.job_started", job)
            try:
                result = func(*args, **kwargs)
                with self._lock:
                    job.status = JobStatus.COMPLETED
                    job.progress = 100.0
                    job.finished_at = time.time()
                    if isinstance(result, Path):
                        job.output_path = result
                    elif isinstance(result, list) and result:
                        job.output_path = result[0] if isinstance(result[0], Path) else None
                self._publish("queue.job_completed", job)
                return result
            except DownloadCancelled as e:
                with self._lock:
                    job.status = JobStatus.CANCELLED
                    job.error = str(e)
                    job.finished_at = time.time()
                self._publish("queue.job_cancelled", job)
                raise
            except Exception as e:
                with self._lock:
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    job.finished_at = time.time()
                self._publish("queue.job_failed", job)
                if self.logger:
                    self.logger.exception("Queue job %s failed", job.id)
                raise
            finally:
                with self._lock:
                    self._active_count = max(0, self._active_count - 1)
                self._publish("queue.active_count", self.active_count)

        future = self._executor.submit(_run)
        with self._lock:
            self._futures[job.id] = future
        return job.id

    def cancel(self, job_id: str) -> bool:
        fut = self._futures.get(job_id)
        if fut and not fut.done():
            cancelled = fut.cancel()
            if cancelled:
                with self._lock:
                    if job_id in self._jobs:
                        self._jobs[job_id].status = JobStatus.CANCELLED
                self._publish("queue.job_cancelled", self._jobs.get(job_id))
            return cancelled
        return False

    def cancel_all(self) -> None:
        for jid in list(self._futures.keys()):
            self.cancel(jid)

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._active_count

    @property
    def queued_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status == JobStatus.QUEUED)

    @property
    def has_active(self) -> bool:
        return self.active_count > 0

    def get_jobs(self) -> dict[str, Job]:
        with self._lock:
            return dict(self._jobs)

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)
