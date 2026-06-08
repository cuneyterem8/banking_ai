import threading

from app.services.ml_job_queue import (
    enqueue_ml_job,
    enqueue_startup_job,
    enqueue_user_job,
    wait_for_queue_idle,
    wait_for_startup_queue_idle,
)


def test_ml_jobs_run_sequentially() -> None:
    order: list[str] = []

    enqueue_ml_job("first", lambda: order.append("first"))
    enqueue_ml_job("second", lambda: order.append("second"))

    assert wait_for_queue_idle(timeout=10.0)
    assert order == ["first", "second"]


def test_user_jobs_can_run_while_startup_queue_is_blocked() -> None:
    startup_can_finish = threading.Event()
    startup_started = threading.Event()
    user_done = threading.Event()

    def startup_task() -> None:
        startup_started.set()
        startup_can_finish.wait(timeout=10.0)

    enqueue_startup_job("blocked-startup", startup_task)
    assert startup_started.wait(timeout=5.0)

    enqueue_user_job("parallel-user-run", user_done.set)
    assert wait_for_queue_idle(timeout=5.0)
    assert user_done.is_set()

    startup_can_finish.set()
    assert wait_for_startup_queue_idle(timeout=5.0)
