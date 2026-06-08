"""Convert Python/numpy values to PostgreSQL-compatible JSON (no NaN/Infinity)."""

from __future__ import annotations

import math
from numbers import Integral, Real
from typing import Any


def json_safe_float(value: float, *, inf_replacement: float = 1.0) -> float | None:
    f = float(value)
    if math.isnan(f):
        return None
    if math.isinf(f):
        return inf_replacement if f > 0 else 0.0
    return round(f, 6)


def sanitize_for_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(key): sanitize_for_json(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, str) or obj is None:
        return obj
    if isinstance(obj, Integral) and not isinstance(obj, bool):
        return int(obj)
    if isinstance(obj, Real):
        return json_safe_float(float(obj))
    return obj
