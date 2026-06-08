from __future__ import annotations

from typing import Any, Callable

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from app.ai.autogluon_adapter import AutoGluonTabularAdapter
from app.config import get_settings
from app.use_cases.aml_monitoring.feature_engineering import (
    LABEL_COLUMN,
    enrich_rows,
    load_operational_threshold,
    prepare_ml_frame,
    save_operational_threshold,
)
from app.use_cases.aml_monitoring.metrics import AUTOGLUON_EVAL_METRIC, PRIMARY_METRIC, PRIMARY_METRIC_LABEL
from app.use_cases.aml_monitoring.schemas import (
    AmlAlertDecision,
    AmlSplitEvaluation,
    ConfusionMatrix,
    PrPoint,
    RocPoint,
)
from app.use_cases.aml_monitoring.threshold_tuning import find_operational_threshold
from app.utils.json_safe import json_safe_float, sanitize_for_json

ProgressCallback = Callable[[int, str], None]
MEDIUM_RISK_THRESHOLD = 0.3
CRITICAL_RISK_THRESHOLD = 0.78


def get_model_dir() -> Any:
    settings = get_settings()
    return settings.storage_dir / "models" / "aml-monitoring" / "autogluon"


def _resolve_threshold(model_dir: Any, override: float | None = None) -> float:
    if override is not None:
        return override
    return load_operational_threshold(model_dir)


def _risk_level(probability: float, threshold: float) -> str:
    if probability >= max(CRITICAL_RISK_THRESHOLD, threshold + 0.16):
        return "Critical"
    if probability >= threshold:
        return "High"
    if probability >= MEDIUM_RISK_THRESHOLD:
        return "Medium"
    return "Low"


def _decision(probability: float, threshold: float) -> str:
    risk = _risk_level(probability, threshold)
    if risk == "Critical":
        return "Draft SAR"
    if risk == "High":
        return "Escalate"
    if risk == "Medium":
        return "Review"
    return "Close"


def _predicted_sar(probability: float, threshold: float) -> int:
    return 1 if probability >= threshold else 0


def _related_entities(value: Any) -> list[str]:
    return [item.strip() for item in str(value or "").split(";") if item.strip()]


def _top_factors(row: dict[str, Any]) -> list[str]:
    factors: list[str] = []
    if row.get("sanctions_name_similarity", 0) >= 0.5:
        factors.append("Sanctions name similarity is elevated.")
    if row.get("counterparty_cluster_risk", 0) >= 0.62:
        factors.append("Counterparty cluster risk is high.")
    if row.get("rapid_movement_ratio", 0) >= 0.56:
        factors.append("Rapid movement ratio indicates quick fund movement.")
    if row.get("structuring_count_7d", 0) >= 5:
        factors.append("Multiple recent structuring-pattern events were detected.")
    if row.get("beneficial_owner_mismatch", 0) == 1:
        factors.append("Beneficial owner mismatch is present.")
    if row.get("jurisdiction_risk_score", 0) >= 0.68:
        factors.append("Jurisdiction risk score is above the review band.")
    if row.get("adverse_media_flag", 0) == 1:
        factors.append("Adverse media signal is present.")
    if row.get("nested_entity_depth", 0) >= 3:
        factors.append("Nested entity depth suggests complex ownership.")
    if row.get("round_amount_ratio", 0) >= 0.62:
        factors.append("Round amount transaction ratio is elevated.")
    if not factors:
        factors.append("No dominant AML risk factor was detected.")
    return factors[:4]


def _sar_probabilities(predictor: Any, feature_frame: pd.DataFrame) -> list[float]:
    probabilities = predictor.predict_proba(feature_frame)
    if 1 in probabilities.columns:
        return probabilities[1].astype(float).tolist()
    return probabilities.iloc[:, -1].astype(float).tolist()


def _ml_features_from_rows(rows: list[dict[str, Any]]) -> tuple[pd.DataFrame, list[int] | None]:
    frame = prepare_ml_frame(rows)
    if LABEL_COLUMN not in frame.columns:
        return frame, None
    labels = frame[LABEL_COLUMN].astype(int).tolist()
    features = frame.drop(columns=[LABEL_COLUMN])
    return features, labels


def _build_decisions(
    feature_rows: list[dict[str, Any]],
    actual_labels: list[int],
    sar_scores: list[float],
    *,
    threshold: float,
) -> list[AmlAlertDecision]:
    enriched_rows = enrich_rows(feature_rows)
    return [
        AmlAlertDecision(
            alert_id=str(row["alert_id"]),
            customer_id=str(row["customer_id"]),
            account_id=str(row["account_id"]),
            typology_tag=str(row["typology_tag"]),
            sar_probability=round(float(probability), 4),
            risk_level=_risk_level(float(probability), threshold),
            predicted_sar_recommended=_predicted_sar(float(probability), threshold),
            actual_sar_recommended=int(actual),
            decision=_decision(float(probability), threshold),
            top_factors=_top_factors(enriched_row),
            related_entities=_related_entities(row.get("related_entities")),
            linked_transaction_count=int(row.get("linked_transaction_count", 0)),
            provider_used="local-autogluon",
        )
        for row, enriched_row, actual, probability in zip(
            feature_rows, enriched_rows, actual_labels, sar_scores, strict=True
        )
    ]


def _roc_curve_points(y_true: list[int], scores: list[float]) -> list[RocPoint]:
    if len(set(y_true)) < 2:
        return [RocPoint(threshold=0.0, tpr=1.0, fpr=1.0), RocPoint(threshold=1.0, tpr=0.0, fpr=0.0)]
    fpr, tpr, thresholds = roc_curve(y_true, scores)
    points: list[RocPoint] = []
    for idx, threshold in enumerate(thresholds):
        safe_threshold = json_safe_float(threshold, inf_replacement=1.0)
        safe_tpr = json_safe_float(tpr[idx], inf_replacement=1.0)
        safe_fpr = json_safe_float(fpr[idx], inf_replacement=1.0)
        if safe_threshold is None or safe_tpr is None or safe_fpr is None:
            continue
        points.append(RocPoint(threshold=round(safe_threshold, 4), tpr=round(safe_tpr, 4), fpr=round(safe_fpr, 4)))
    return points[:25] if points else [RocPoint(threshold=0.0, tpr=1.0, fpr=1.0), RocPoint(threshold=1.0, tpr=0.0, fpr=0.0)]


def _pr_curve_points(y_true: list[int], scores: list[float]) -> list[PrPoint]:
    if len(set(y_true)) < 2:
        return [PrPoint(threshold=1.0, precision=1.0, recall=0.0), PrPoint(threshold=0.0, precision=0.0, recall=1.0)]
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    points: list[PrPoint] = []
    for idx, threshold in enumerate(thresholds):
        safe_threshold = json_safe_float(threshold, inf_replacement=1.0)
        safe_precision = json_safe_float(precision[idx], inf_replacement=1.0)
        safe_recall = json_safe_float(recall[idx], inf_replacement=1.0)
        if safe_threshold is None or safe_precision is None or safe_recall is None:
            continue
        points.append(
            PrPoint(
                threshold=round(safe_threshold, 4),
                precision=round(safe_precision, 4),
                recall=round(safe_recall, 4),
            )
        )
    return points[:25] if points else [PrPoint(threshold=1.0, precision=1.0, recall=0.0), PrPoint(threshold=0.0, precision=0.0, recall=1.0)]


def _primary_score(y_true: list[int], scores: list[float]) -> float | None:
    if len(set(y_true)) < 2:
        return None
    try:
        safe = json_safe_float(float(average_precision_score(y_true, scores)), inf_replacement=1.0)
        return round(safe, 4) if safe is not None else None
    except ValueError:
        return None


def _roc_auc(y_true: list[int], scores: list[float]) -> float | None:
    if len(set(y_true)) < 2:
        return None
    try:
        safe = json_safe_float(float(roc_auc_score(y_true, scores)), inf_replacement=1.0)
        return round(safe, 4) if safe is not None else None
    except ValueError:
        return None


def calibrate_threshold_on_rows(predictor: Any, rows: list[dict[str, Any]]) -> float:
    feature_frame, actual_labels = _ml_features_from_rows(rows)
    if actual_labels is None:
        return 0.5
    scores = _sar_probabilities(predictor, feature_frame)
    threshold = find_operational_threshold(actual_labels, scores)
    save_operational_threshold(get_model_dir(), threshold)
    return threshold


def evaluate_split(
    predictor: Any,
    rows: list[dict[str, Any]],
    *,
    split_name: str,
    threshold: float | None = None,
) -> AmlSplitEvaluation:
    model_dir = get_model_dir()
    operational_threshold = _resolve_threshold(model_dir, threshold)
    feature_frame, actual_labels = _ml_features_from_rows(rows)
    if actual_labels is None:
        raise ValueError("Rows must include label_sar_recommended for evaluation.")
    scores = _sar_probabilities(predictor, feature_frame)
    predictions = [_predicted_sar(score, operational_threshold) for score in scores]
    raw_feature_rows = [dict(row) for row in rows]
    decisions = _build_decisions(raw_feature_rows, actual_labels, scores, threshold=operational_threshold)
    tn, fp, fn, tp = confusion_matrix(actual_labels, predictions, labels=[0, 1]).ravel()

    return AmlSplitEvaluation(
        split=split_name,
        record_count=len(rows),
        primary_metric=PRIMARY_METRIC,
        primary_metric_label=PRIMARY_METRIC_LABEL,
        primary_score=_primary_score(actual_labels, scores),
        precision=round(float(precision_score(actual_labels, predictions, zero_division=0)), 4),
        recall=round(float(recall_score(actual_labels, predictions, zero_division=0)), 4),
        f1=round(float(f1_score(actual_labels, predictions, zero_division=0)), 4),
        accuracy=round(float(accuracy_score(actual_labels, predictions)), 4),
        roc_auc=_roc_auc(actual_labels, scores),
        threshold=round(operational_threshold, 4),
        correct_predictions=sum(1 for item in decisions if item.actual_sar_recommended == item.predicted_sar_recommended),
        confusion_matrix=ConfusionMatrix(tp=int(tp), tn=int(tn), fp=int(fp), fn=int(fn)),
        pr_curve=_pr_curve_points(actual_labels, scores),
        roc_curve=_roc_curve_points(actual_labels, scores),
        records=decisions,
    )


def train_and_validate(
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    *,
    progress_callback: ProgressCallback | None = None,
    force_retrain: bool = False,
) -> tuple[Any, AmlSplitEvaluation, dict[str, Any]]:
    if progress_callback:
        progress_callback(8, "loading_aml_alerts")

    model_dir = get_model_dir()
    adapter = AutoGluonTabularAdapter(artifact_dir=model_dir)
    train_frame = prepare_ml_frame(train_rows)
    val_frame = prepare_ml_frame(val_rows)
    predictor = adapter.fit_binary_classifier(
        train_frame,
        LABEL_COLUMN,
        eval_metric=AUTOGLUON_EVAL_METRIC,
        tuning_frame=None,
        force_retrain=force_retrain,
        progress_callback=progress_callback,
    )

    if progress_callback:
        progress_callback(68, "calibrating_threshold")
    calibrated_threshold = calibrate_threshold_on_rows(predictor, val_rows)

    if progress_callback:
        progress_callback(78, "evaluating_validation_alerts")
    val_evaluation = evaluate_split(predictor, val_rows, split_name="val", threshold=calibrated_threshold)
    leaderboard = predictor.leaderboard(val_frame, silent=True).head(8).to_dict(orient="records")

    if progress_callback:
        progress_callback(88, "preparing_narratives")

    explanation = sanitize_for_json(
        {
            "top_model_rows": leaderboard,
            "calibrated_threshold": calibrated_threshold,
            "explanation_method": (
                "AutoGluon Tabular scored synthetic AML alerts with deterministic network features. "
                "Validation rows tune the operational SAR threshold and provide startup metrics."
            ),
            "evaluation": val_evaluation.model_dump(),
        }
    )
    return predictor, val_evaluation, explanation


def evaluate_test(
    test_rows: list[dict[str, Any]],
    *,
    progress_callback: ProgressCallback | None = None,
) -> tuple[AmlSplitEvaluation, dict[str, Any]]:
    if progress_callback:
        progress_callback(10, "loading_aml_model")
    adapter = AutoGluonTabularAdapter(artifact_dir=get_model_dir())
    predictor = adapter.load_predictor()

    if progress_callback:
        progress_callback(45, "scoring_test_alerts")
    test_evaluation = evaluate_split(predictor, test_rows, split_name="test")

    if progress_callback:
        progress_callback(64, "computing_aml_metrics")
    explanation = sanitize_for_json(
        {
            "explanation_method": "Held-out synthetic AML alert test scoring with the validation-calibrated SAR threshold.",
            "evaluation": test_evaluation.model_dump(),
        }
    )
    return test_evaluation, explanation


def evaluation_payload_for_db(
    evaluation: AmlSplitEvaluation,
    *,
    summary: dict[str, Any],
    narratives: list[dict[str, Any]],
    network_summary: dict[str, Any],
    case_note_summary: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    return sanitize_for_json(
        {
            "split": evaluation.split,
            "summary": summary,
            "evaluation": evaluation.model_dump(),
            "alerts": [item.model_dump() for item in evaluation.records],
            "narratives": narratives,
            "network_summary": network_summary,
            "case_note_summary": case_note_summary,
            "warnings": warnings,
        }
    )
