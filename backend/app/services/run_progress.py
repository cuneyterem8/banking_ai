from dataclasses import dataclass, field
from threading import Lock


@dataclass
class ProgressState:
    run_id: str
    status: str = "running"
    progress_percent: int = 0
    stage: str = "starting"


_progress: dict[str, ProgressState] = {}
_lock = Lock()


def set_run_progress(run_id: str, percent: int, stage: str, status: str = "running") -> None:
    with _lock:
        _progress[run_id] = ProgressState(
            run_id=run_id,
            status=status,
            progress_percent=max(0, min(100, percent)),
            stage=stage,
        )


def complete_run_progress(run_id: str) -> None:
    set_run_progress(run_id, 100, "done", status="completed")


def fail_run_progress(run_id: str, stage: str = "failed") -> None:
    with _lock:
        current = _progress.get(run_id)
        percent = current.progress_percent if current else 0
        _progress[run_id] = ProgressState(
            run_id=run_id,
            status="failed",
            progress_percent=percent,
            stage=stage,
        )


def get_run_progress(run_id: str) -> ProgressState | None:
    with _lock:
        return _progress.get(run_id)
