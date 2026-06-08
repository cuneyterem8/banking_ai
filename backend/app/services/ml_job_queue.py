"""FIFO queues for startup processing and user-triggered local ML jobs."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

Task = Callable[[], None]

_startup_pipeline_done = threading.Event()
_api_ready = threading.Event()


@dataclass
class _JobQueue:
    label: str
    queue: queue.Queue[tuple[str, Task]] = field(default_factory=queue.Queue)
    worker_lock: threading.Lock = field(default_factory=threading.Lock)
    worker_started: bool = False

    def enqueue(self, name: str, task: Task) -> None:
        self._ensure_worker()
        self.queue.put((name, task))

    def wait_idle(self, timeout: float = 30.0, poll_interval: float = 0.05) -> bool:
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.queue.unfinished_tasks == 0:
                return True
            time.sleep(poll_interval)
        return self.queue.unfinished_tasks == 0

    def _ensure_worker(self) -> None:
        with self.worker_lock:
            if self.worker_started:
                return
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"{self.label}-worker",
                daemon=True,
            )
            thread.start()
            self.worker_started = True

    def _worker_loop(self) -> None:
        while True:
            name, task = self.queue.get()
            try:
                logger.info("%s job started: %s", self.label, name)
                task()
                logger.info("%s job finished: %s", self.label, name)
            except Exception:
                logger.exception("%s job failed: %s", self.label, name)
            finally:
                self.queue.task_done()


_startup_queue = _JobQueue("startup")
_user_run_queue = _JobQueue("user-run")


def mark_api_ready() -> None:
    _api_ready.set()


def is_api_ready() -> bool:
    return _api_ready.is_set()


def mark_startup_pipeline_complete() -> None:
    _startup_pipeline_done.set()


def reset_startup_pipeline_complete() -> None:
    _startup_pipeline_done.clear()


def is_startup_pipeline_complete() -> bool:
    return _startup_pipeline_done.is_set()


def wait_for_startup_pipeline(timeout: float | None = None) -> bool:
    return _startup_pipeline_done.wait(timeout)


def enqueue_ml_job(name: str, task: Task) -> None:
    """Backward-compatible alias for user-triggered ML jobs."""
    enqueue_user_job(name, task)


def enqueue_user_job(name: str, task: Task) -> None:
    _user_run_queue.enqueue(name, task)


def enqueue_startup_job(name: str, task: Task) -> None:
    _startup_queue.enqueue(name, task)


def wait_for_queue_idle(timeout: float = 30.0, poll_interval: float = 0.05) -> bool:
    return _user_run_queue.wait_idle(timeout=timeout, poll_interval=poll_interval)


def wait_for_startup_queue_idle(timeout: float = 30.0, poll_interval: float = 0.05) -> bool:
    return _startup_queue.wait_idle(timeout=timeout, poll_interval=poll_interval)
