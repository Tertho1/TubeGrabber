"""Unit tests for DownloadQueue (Phase 1.2)."""
import time
from tubegrabber.services.queue_service import DownloadQueue, JobStatus
from tubegrabber.events import EventBus


def test_queue_submit_and_complete():
    bus = EventBus()
    q = DownloadQueue(max_workers=2, event_bus=bus)

    def fake_download():
        time.sleep(0.05)
        return "done"

    jid = q.submit(fake_download, url="https://example.com/v", kind="video")
    assert jid in q.get_jobs()
    # Wait a bit for completion
    time.sleep(0.15)
    job = q.get_job(jid)
    assert job is not None
    assert job.status == JobStatus.COMPLETED
    assert not q.has_active
    q.shutdown(wait=False)


def test_queue_concurrent_limit():
    bus = EventBus()
    q = DownloadQueue(max_workers=2, event_bus=bus)

    def slow():
        time.sleep(0.1)

    q.submit(slow, url="u1", kind="video")
    q.submit(slow, url="u2", kind="video")
    q.submit(slow, url="u3", kind="video")
    # At least one should be queued or active
    time.sleep(0.02)
    assert q.active_count <= 2
    time.sleep(0.25)
    assert not q.has_active
    q.shutdown(wait=False)


def test_queue_has_active_property():
    q = DownloadQueue(max_workers=1)
    assert not q.has_active

    def slow():
        time.sleep(0.1)

    q.submit(slow, url="u", kind="video")
    time.sleep(0.02)
    assert q.has_active
    time.sleep(0.15)
    assert not q.has_active
    q.shutdown(wait=False)
