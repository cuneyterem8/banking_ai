import math

from app.utils.json_safe import sanitize_for_json


def test_sanitize_replaces_infinity_in_nested_structure() -> None:
    payload = {
        "roc_curve": [{"threshold": math.inf, "tpr": 1.0, "fpr": 0.0}],
        "score": float("nan"),
    }
    cleaned = sanitize_for_json(payload)
    assert cleaned["roc_curve"][0]["threshold"] == 1.0
    assert cleaned["score"] is None
