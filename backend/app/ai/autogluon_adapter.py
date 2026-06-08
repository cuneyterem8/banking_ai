import importlib.util
import shutil
import threading
import time
from pathlib import Path
from typing import Any

import pandas as pd

from app.ai.autogluon_runtime import autogluon_fit_lock, default_num_cpus
from app.ai.base import AIAdapterUnavailable, AdapterHealth
from app.config import get_settings

# Heavy / GPU-only learners; keep the zeroshot portfolio (GBM, CAT, RF, XT, LR) enabled.
# KNN memorizes local patterns on ~2.5k rows and widens val/test gap.
# XGB is excluded because the current Windows local build can train successfully
# but fail during predict_proba with a missing n_classes_ attribute.
EXCLUDED_MODEL_TYPES = ("FASTAI", "NN_TORCH", "KNN", "XGB")


def _start_fit_heartbeat(progress_callback: Any | None, time_limit: int) -> tuple[threading.Event, threading.Thread | None]:
    stop_event = threading.Event()
    if progress_callback is None:
        return stop_event, None

    def heartbeat() -> None:
        started = time.monotonic()
        while not stop_event.wait(5):
            elapsed = time.monotonic() - started
            ratio = min(elapsed / max(float(time_limit), 1.0), 1.0)
            progress = min(52, 22 + int(ratio * 30))
            progress_callback(progress, "fitting")

    thread = threading.Thread(target=heartbeat, name="autogluon-fit-heartbeat", daemon=True)
    thread.start()
    return stop_event, thread


def _build_tabular_fit_kwargs(settings: Any, tuning_frame: Any | None) -> dict[str, Any]:
    preset = settings.autogluon_preset or "good_quality"
    num_cpus = settings.autogluon_num_cpus if settings.autogluon_num_cpus > 0 else default_num_cpus()
    fit_kwargs: dict[str, Any] = {
        "presets": preset,
        "time_limit": settings.autogluon_time_limit_seconds,
        "num_bag_folds": settings.autogluon_num_bag_folds,
        "excluded_model_types": list(EXCLUDED_MODEL_TYPES),
        "refit_full": False,
        "set_best_to_refit_full": False,
        "ag_args_fit": {"num_cpus": num_cpus},
    }
    if settings.autogluon_num_bag_folds <= 0:
        fit_kwargs["num_stack_levels"] = 0
        fit_kwargs["dynamic_stacking"] = False
    if tuning_frame is not None and not tuning_frame.empty:
        fit_kwargs["tuning_data"] = tuning_frame
        if settings.autogluon_num_bag_folds > 0:
            fit_kwargs["use_bag_holdout"] = True
    return fit_kwargs


class AutoGluonTabularAdapter:
    name = "AutoGluon Tabular"
    provider = "local-autogluon"
    model_name = "autogluon.tabular.TabularPredictor"

    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir

    def health_check(self) -> AdapterHealth:
        try:
            available = importlib.util.find_spec("autogluon.tabular") is not None
        except ModuleNotFoundError:
            available = False
        if available:
            return AdapterHealth(
                name=self.name,
                available=True,
                provider=self.provider,
                model_name=self.model_name,
                message="AutoGluon Tabular is available.",
            )
        return AdapterHealth(
            name=self.name,
            available=False,
            provider=self.provider,
            model_name=self.model_name,
            message="AutoGluon Tabular is not installed in the active Python environment.",
            setup_hint="Run: npm run setup:backend",
        )

    def require_available(self) -> None:
        health = self.health_check()
        if not health.available:
            raise AIAdapterUnavailable(health.message, health.setup_hint)

    def _model_exists(self) -> bool:
        return (self.artifact_dir / "predictor.pkl").exists()

    def _clear_model(self) -> None:
        if self.artifact_dir.exists():
            shutil.rmtree(self.artifact_dir, ignore_errors=True)

    def fit_binary_classifier(
        self,
        train_frame: pd.DataFrame,
        label: str,
        *,
        eval_metric: str,
        tuning_frame: pd.DataFrame | None = None,
        force_retrain: bool = False,
        progress_callback: Any | None = None,
    ) -> Any:
        self.require_available()
        from autogluon.tabular import TabularPredictor

        settings = get_settings()
        if force_retrain or settings.force_retrain:
            self._clear_model()

        if self._model_exists():
            if progress_callback:
                progress_callback(60, "loading_model")
            return TabularPredictor.load(str(self.artifact_dir))

        if progress_callback:
            progress_callback(20, "fitting")

        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        predictor = TabularPredictor(
            label=label,
            problem_type="binary",
            eval_metric=eval_metric,
            path=str(self.artifact_dir),
            verbosity=0,
        )

        fit_kwargs = _build_tabular_fit_kwargs(settings, tuning_frame)

        stop_heartbeat, heartbeat_thread = _start_fit_heartbeat(progress_callback, int(fit_kwargs["time_limit"]))
        try:
            with autogluon_fit_lock():
                predictor.fit(train_frame, **fit_kwargs)
        finally:
            stop_heartbeat.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join(timeout=1)
        if progress_callback:
            progress_callback(55, "fitting")
        return predictor

    def load_predictor(self) -> Any:
        self.require_available()
        from autogluon.tabular import TabularPredictor

        if not self._model_exists():
            raise AIAdapterUnavailable(
                "Tabular model is not trained yet. Wait for startup training or set FORCE_RETRAIN=1.",
                "Ensure the backend finished startup training.",
            )
        return TabularPredictor.load(str(self.artifact_dir))
