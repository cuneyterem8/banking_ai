"""Holdout slice of train for threshold tuning (never used in model fit)."""

from __future__ import annotations

import random
from typing import Any


def split_train_for_calibration(
    train_rows: list[dict[str, Any]],
    *,
    calibration_fraction: float = 0.15,
    seed: int = 3912,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Stratified split inside train only.
    Model fits on train_fit; threshold is tuned on train_cal (unseen during fit).
    """
    rng = random.Random(seed)
    fraud = [row for row in train_rows if row["label_is_fraud"] == 1]
    legit = [row for row in train_rows if row["label_is_fraud"] == 0]
    rng.shuffle(fraud)
    rng.shuffle(legit)

    cal_fraud = max(1, int(len(fraud) * calibration_fraction)) if fraud else 0
    cal_legit = max(1, int(len(legit) * calibration_fraction)) if legit else 0
    cal_fraud = min(cal_fraud, len(fraud))
    cal_legit = min(cal_legit, len(legit))

    train_cal = fraud[:cal_fraud] + legit[:cal_legit]
    train_fit = fraud[cal_fraud:] + legit[cal_legit:]
    rng.shuffle(train_fit)
    rng.shuffle(train_cal)
    return train_fit, train_cal


def split_train_for_autogluon_holdout(
    train_rows: list[dict[str, Any]],
    *,
    holdout_fraction: float = 0.18,
    seed: int = 5517,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Stratified train-only holdout for AutoGluon bagged early stopping (never val/test)."""
    return split_train_for_calibration(
        train_rows,
        calibration_fraction=holdout_fraction,
        seed=seed,
    )
