from app.use_cases.aml_monitoring.feature_engineering import LABEL_COLUMN, enrich_alert_row, prepare_ml_frame
from app.use_cases.aml_monitoring.raw_data import load_val_alerts
from sklearn.metrics import recall_score

from app.use_cases.aml_monitoring.metrics import MINIMUM_RECALL_TARGET
from app.use_cases.aml_monitoring.threshold_tuning import f1_at_threshold, find_operational_threshold


def test_aml_feature_engineering_is_deterministic_and_drops_ids() -> None:
    row = load_val_alerts()[0].model_dump()
    first = enrich_alert_row(row)
    second = enrich_alert_row(row)

    assert first == second
    assert first["aggregate_risk_score"] >= 0
    assert first["network_risk_index"] >= 0
    assert first["rule_trigger_count"] >= 1

    frame = prepare_ml_frame([row])
    for forbidden in ("alert_id", "customer_id", "account_id", "entity_id", "related_entities", "rule_triggers"):
        assert forbidden not in frame.columns
    assert LABEL_COLUMN in frame.columns


def test_aml_threshold_tuning_prefers_recall_biased_f1() -> None:
    labels = [0, 0, 1, 1, 1, 0, 1, 0]
    scores = [0.05, 0.18, 0.38, 0.62, 0.82, 0.44, 0.74, 0.26]

    threshold = find_operational_threshold(labels, scores)
    predictions = [1 if score >= threshold else 0 for score in scores]

    assert 0.0 <= threshold <= 1.0
    assert recall_score(labels, predictions, zero_division=0) >= MINIMUM_RECALL_TARGET
    assert f1_at_threshold(labels, scores, threshold) > 0
