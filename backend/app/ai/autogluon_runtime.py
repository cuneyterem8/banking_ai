"""Shared AutoGluon runtime: single-job lock and local-dev safety patches."""

from __future__ import annotations

import logging
import os
import sys
import threading
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)

_fit_lock = threading.Lock()
_patches_applied = False


def configure_local_environment() -> None:
    os.environ.setdefault("RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO", "0")


def apply_runtime_patches() -> None:
    global _patches_applied
    if _patches_applied:
        return
    configure_local_environment()
    _patch_lgb_memory_early_stop_logging()
    _patches_applied = True


def _patch_lgb_memory_early_stop_logging() -> None:
    """Avoid TypeError when AutoGluon memory guard fires before the first validation eval."""
    try:
        from autogluon.tabular.models.lgb import callbacks as lgb_callbacks
        from lightgbm.callback import EarlyStopException
    except ImportError:
        return

    if getattr(lgb_callbacks, "_banking_ai_memory_patch", False):
        return

    original_factory = lgb_callbacks.early_stopping_custom

    def early_stopping_custom(*args, **kwargs):
        callback = original_factory(*args, **kwargs)
        order = getattr(callback, "order", 30)

        def safe_callback(env):
            try:
                return callback(env)
            except TypeError as exc:
                if "NoneType" not in str(exc):
                    raise
                logger.warning(
                    "LightGBM memory guard triggered before validation metrics were available; stopping this fold early."
                )
                raise EarlyStopException(0, None) from exc

        safe_callback.order = order
        return safe_callback

    lgb_callbacks.early_stopping_custom = early_stopping_custom
    lgb_callbacks._banking_ai_memory_patch = True


@contextmanager
def autogluon_fit_lock() -> Iterator[None]:
    apply_runtime_patches()
    _fit_lock.acquire()
    try:
        yield
    finally:
        _fit_lock.release()


def default_num_cpus() -> int:
    if sys.platform == "win32":
        return 1
    return 2
