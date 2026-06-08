from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.use_cases.aml_monitoring.metrics import OPERATIONAL_THRESHOLD

LABEL_COLUMN = "label_sar_recommended"
DROP_FOR_ML = (
    "alert_id",
    "customer_id",
    "account_id",
    "entity_id",
    "related_entities",
    "rule_triggers",
)

TYPOLOGY_RISK = {
    "Structuring": 0.82,
    "Rapid Movement": 0.78,
    "High-Risk Jurisdiction": 0.74,
    "Sanctions Proximity": 0.9,
    "Adverse Media": 0.69,
    "Shell Entity Network": 0.86,
    "Unusual Cash Activity": 0.62,
}

ALERT_TYPE_RISK = {
    "cash_structuring": 0.78,
    "wire_velocity": 0.74,
    "sanctions_screening": 0.88,
    "kyc_refresh": 0.52,
    "network_cluster": 0.83,
    "adverse_media_review": 0.68,
}


def _row_get(row: dict[str, Any] | pd.Series, key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _trigger_count(value: Any) -> int:
    return len([item for item in str(value or "").split(";") if item.strip()])


def _related_entity_count(value: Any) -> int:
    return len([item for item in str(value or "").split(";") if item.strip()])


def enrich_alert_row(row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    cash_total = _row_get(row, "cash_deposit_total_30d")
    wire_total = _row_get(row, "outgoing_wire_total_30d")
    network_degree = _row_get(row, "network_degree")
    linked_transactions = max(_row_get(row, "linked_transaction_count"), 1.0)
    typology = str(row.get("typology_tag", "Unusual Cash Activity"))
    alert_type = str(row.get("alert_type", "kyc_refresh"))
    sanctions = _row_get(row, "sanctions_name_similarity")
    adverse_media = _row_get(row, "adverse_media_flag")
    jurisdiction = _row_get(row, "jurisdiction_risk_score")
    kyc = _row_get(row, "kyc_risk_score")
    cluster = _row_get(row, "counterparty_cluster_risk")
    centrality = _row_get(row, "network_centrality_score")
    structuring = _row_get(row, "structuring_count_7d")
    rapid = _row_get(row, "rapid_movement_ratio")
    nested_depth = _row_get(row, "nested_entity_depth")
    owner_mismatch = _row_get(row, "beneficial_owner_mismatch")

    cash_wire_ratio = cash_total / max(wire_total, 1.0)
    aggregate_risk = _clamp01(
        0.18 * kyc
        + 0.15 * jurisdiction
        + 0.16 * sanctions
        + 0.12 * cluster
        + 0.1 * centrality
        + 0.1 * min(structuring / 8.0, 1.0)
        + 0.09 * rapid
        + 0.05 * adverse_media
        + 0.05 * owner_mismatch
    )
    enriched.update(
        {
            "typology_risk_score": TYPOLOGY_RISK.get(typology, 0.5),
            "alert_type_risk_score": ALERT_TYPE_RISK.get(alert_type, 0.5),
            "aggregate_risk_score": round(aggregate_risk, 4),
            "cash_wire_ratio": round(min(cash_wire_ratio, 10.0), 4),
            "structuring_pressure": round(_clamp01(structuring / 8.0 + _row_get(row, "round_amount_ratio") * 0.45), 4),
            "network_risk_index": round(_clamp01(0.45 * cluster + 0.35 * centrality + 0.2 * min(network_degree / 18.0, 1.0)), 4),
            "entity_complexity_score": round(_clamp01(nested_depth / 5.0 + owner_mismatch * 0.35), 4),
            "sanctions_adverse_signal": round(_clamp01(sanctions * 0.75 + adverse_media * 0.25), 4),
            "high_risk_jurisdiction_flag": 1 if jurisdiction >= 0.68 else 0,
            "rapid_movement_wire_interaction": round(_clamp01(rapid * min(wire_total / 65000.0, 1.4)), 4),
            "beneficial_owner_network_flag": 1 if owner_mismatch and cluster >= 0.58 else 0,
            "rule_trigger_count": _trigger_count(row.get("rule_triggers")),
            "related_entity_count": _related_entity_count(row.get("related_entities")),
            "linked_transaction_density": round(min(linked_transactions / max(network_degree, 1.0), 4.0), 4),
        }
    )
    return enriched


def enrich_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_alert_row(row) for row in rows]


def prepare_ml_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(enrich_rows(rows))
    for column in DROP_FOR_ML:
        if column in frame.columns:
            frame = frame.drop(columns=[column])
    return frame


def threshold_file(model_dir: Path) -> Path:
    return Path(model_dir) / "operational_threshold.json"


def save_operational_threshold(model_dir: Path, threshold: float) -> None:
    Path(model_dir).mkdir(parents=True, exist_ok=True)
    threshold_file(model_dir).write_text(json.dumps({"threshold": round(float(threshold), 4)}), encoding="utf-8")


def load_operational_threshold(model_dir: Path) -> float:
    path = threshold_file(model_dir)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        return float(payload.get("threshold", OPERATIONAL_THRESHOLD))
    return OPERATIONAL_THRESHOLD
