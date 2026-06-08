from types import SimpleNamespace

from app.ai.autogluon_adapter import EXCLUDED_MODEL_TYPES, _build_tabular_fit_kwargs
from app.ai.autogluon_runtime import apply_runtime_patches, autogluon_fit_lock


def test_apply_runtime_patches_is_idempotent() -> None:
    apply_runtime_patches()
    apply_runtime_patches()


def test_autogluon_fit_lock_can_be_acquired() -> None:
    with autogluon_fit_lock():
        pass


def test_tabular_fit_kwargs_disable_stacking_when_bagging_is_off() -> None:
    settings = SimpleNamespace(
        autogluon_preset="good_quality",
        autogluon_num_cpus=1,
        autogluon_time_limit_seconds=180,
        autogluon_num_bag_folds=0,
    )

    kwargs = _build_tabular_fit_kwargs(settings, tuning_frame=None)

    assert kwargs["num_bag_folds"] == 0
    assert kwargs["num_stack_levels"] == 0
    assert kwargs["dynamic_stacking"] is False


def test_tabular_fit_kwargs_exclude_unstable_local_learners() -> None:
    assert "XGB" in EXCLUDED_MODEL_TYPES
    assert "NN_TORCH" in EXCLUDED_MODEL_TYPES
