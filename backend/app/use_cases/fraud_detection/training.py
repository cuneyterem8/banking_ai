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
from app.utils.json_safe import json_safe_float, sanitize_for_json
from app.use_cases.fraud_detection.feature_engineering import (
    LABEL_COLUMN,
    enrich_rows,
    load_operational_threshold,
    prepare_ml_frame,
    save_operational_threshold,
)
from app.use_cases.fraud_detection.metrics import PRIMARY_METRIC, PRIMARY_METRIC_LABEL
from app.use_cases.fraud_detection.metrics import AUTOGLUON_EVAL_METRIC
from app.use_cases.fraud_detection.schemas import (
    ConfusionMatrix,
    FraudDecision,
    PrPoint,
    RocPoint,
    SplitEvaluation,
)
from app.use_cases.fraud_detection.data_leakage import assert_splits_disjoint, audit_training_inputs
from app.use_cases.fraud_detection.raw_data import load_test_transactions
from app.use_cases.fraud_detection.threshold_tuning import find_best_f1_threshold


DEFAULT_THRESHOLD = 0.5
MEDIUM_RISK_THRESHOLD = 0.35

ProgressCallback = Callable[[int, str], None]


def get_model_dir() -> Any:
    settings = get_settings()
    return settings.storage_dir / "models" / "fraud-detection" / "autogluon"


def _resolve_threshold(model_dir: Any, override: float | None = None) -> float:
    if override is not None:
        return override
    return load_operational_threshold(model_dir)


def _risk_level(probability: float, threshold: float) -> str:
    if probability >= threshold:
        return "High"
    if probability >= MEDIUM_RISK_THRESHOLD:
        return "Medium"
    return "Low"


def _decision(probability: float, threshold: float) -> str:
    if probability >= threshold:
        return "Block and review"
    if probability >= MEDIUM_RISK_THRESHOLD:
        return "Step-up authentication"
    return "Approve"


def _predicted_is_fraud(probability: float, threshold: float) -> int:
    return 1 if probability >= threshold else 0


def _top_factors(row: dict[str, Any]) -> list[str]:
    factors: list[str] = []
    if row.get("amount_ratio", row.get("amount", 0) / max(row.get("avg_30d_amount", 1), 1)) > 3:
        factors.append("Transaction amount is far above the customer 30-day average.")
    if row.get("device_trust_score", 1) < 0.4:
        factors.append("Device trust score is low.")
    if row.get("ip_risk_score", 0) > 0.55:
        factors.append("IP risk score is elevated.")
    if row.get("failed_login_count_24h", 0) >= 2:
        factors.append("Recent failed login activity is elevated.")
    if row.get("velocity_24h_count", 0) >= 7:
        factors.append("Transaction velocity in the last 24 hours is unusually high.")
    if row.get("merchant_risk_score", 0) > 0.6:
        factors.append("Merchant risk score is high.")
    if row.get("prior_chargebacks", 0) > 0:
        factors.append("Customer has prior chargeback history.")
    if row.get("is_new_payee") == 1:
        factors.append("Payment is being sent to a new payee.")
    if row.get("distance_from_home_km", 0) > 600:
        factors.append("Transaction location is far from the customer home pattern.")
    if row.get("weak_auth") == 1 or row.get("auth_method") == "none":
        factors.append("Transaction was approved without strong authentication.")
    if not factors:
        factors.append("No dominant risk factor was detected.")
    return factors[:3]


def _fraud_probabilities(predictor: Any, feature_frame: pd.DataFrame) -> list[float]:
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
    fraud_scores: list[float],
    *,
    threshold: float,
) -> list[FraudDecision]:
    enriched_rows = enrich_rows(feature_rows)
    return [
        FraudDecision(
            transaction_id=str(row["transaction_id"]),
            customer_id=str(row["customer_id"]),
            amount=float(row["amount"]),
            actual_is_fraud=int(actual),
            predicted_is_fraud=_predicted_is_fraud(float(probability), threshold),
            fraud_probability=round(float(probability), 4),
            risk_level=_risk_level(float(probability), threshold),
            decision=_decision(float(probability), threshold),
            top_factors=_top_factors(enriched_row),
        )
        for row, enriched_row, actual, probability in zip(
            feature_rows, enriched_rows, actual_labels, fraud_scores, strict=True
        )
    ]


def _roc_curve_points(y_true: list[int], scores: list[float]) -> list[RocPoint]:
    if len(set(y_true)) < 2:
        return [
            RocPoint(threshold=0.0, tpr=1.0, fpr=1.0),
            RocPoint(threshold=1.0, tpr=0.0, fpr=0.0),
        ]
    fpr, tpr, thresholds = roc_curve(y_true, scores)
    points: list[RocPoint] = []
    for idx, threshold in enumerate(thresholds):
        safe_threshold = json_safe_float(threshold, inf_replacement=1.0)
        safe_tpr = json_safe_float(tpr[idx], inf_replacement=1.0)
        safe_fpr = json_safe_float(fpr[idx], inf_replacement=1.0)
        if safe_threshold is None or safe_tpr is None or safe_fpr is None:
            continue
        points.append(
            RocPoint(
                threshold=round(safe_threshold, 4),
                tpr=round(safe_tpr, 4),
                fpr=round(safe_fpr, 4),
            )
        )
    return points[:25] if points else [
        RocPoint(threshold=0.0, tpr=1.0, fpr=1.0),
        RocPoint(threshold=1.0, tpr=0.0, fpr=0.0),
    ]


def _pr_curve_points(y_true: list[int], scores: list[float]) -> list[PrPoint]:
    if len(set(y_true)) < 2:
        return [
            PrPoint(threshold=1.0, precision=1.0, recall=0.0),
            PrPoint(threshold=0.0, precision=0.0, recall=1.0),
        ]
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
    if not points:
        return [
            PrPoint(threshold=1.0, precision=1.0, recall=0.0),
            PrPoint(threshold=0.0, precision=0.0, recall=1.0),
        ]
    return points[:25]


def _primary_score(y_true: list[int], scores: list[float]) -> float | None:
    if len(set(y_true)) < 2:
        return None
    try:
        raw = float(average_precision_score(y_true, scores))
        safe = json_safe_float(raw, inf_replacement=1.0)
        return round(safe, 4) if safe is not None else None
    except ValueError:
        return None


def _roc_auc(y_true: list[int], scores: list[float]) -> float | None:
    if len(set(y_true)) < 2:
        return None
    try:
        raw_auc = float(roc_auc_score(y_true, scores))
        safe = json_safe_float(raw_auc, inf_replacement=1.0)
        return round(safe, 4) if safe is not None else None
    except ValueError:
        return None


def calibrate_threshold_on_rows(predictor: Any, rows: list[dict[str, Any]]) -> float:
    """Tune threshold on rows the model did not train on (train_cal holdout)."""
    feature_frame, actual_labels = _ml_features_from_rows(rows)
    if actual_labels is None:
        return DEFAULT_THRESHOLD
    scores = _fraud_probabilities(predictor, feature_frame)
    threshold = find_best_f1_threshold(actual_labels, scores)
    save_operational_threshold(get_model_dir(), threshold)
    return threshold


def evaluate_split(
    predictor: Any,
    rows: list[dict[str, Any]],
    *,
    split_name: str,
    threshold: float | None = None,
) -> SplitEvaluation:
    model_dir = get_model_dir()
    operational_threshold = _resolve_threshold(model_dir, threshold)

    feature_frame, actual_labels = _ml_features_from_rows(rows)
    if actual_labels is None:
        raise ValueError("Rows must include label_is_fraud for evaluation.")

    scores = _fraud_probabilities(predictor, feature_frame)
    predictions = [_predicted_is_fraud(score, operational_threshold) for score in scores]
    raw_feature_rows = [dict(row) for row in rows]
    decisions = _build_decisions(
        raw_feature_rows,
        actual_labels,
        scores,
        threshold=operational_threshold,
    )

    tn, fp, fn, tp = confusion_matrix(actual_labels, predictions, labels=[0, 1]).ravel()
    accuracy = round(float(accuracy_score(actual_labels, predictions)), 4)
    precision = round(float(precision_score(actual_labels, predictions, zero_division=0)), 4)
    recall = round(float(recall_score(actual_labels, predictions, zero_division=0)), 4)
    f1 = round(float(f1_score(actual_labels, predictions, zero_division=0)), 4)

    return SplitEvaluation(
        split=split_name,
        record_count=len(rows),
        primary_metric=PRIMARY_METRIC,
        primary_metric_label=PRIMARY_METRIC_LABEL,
        primary_score=_primary_score(actual_labels, scores),
        precision=precision,
        recall=recall,
        f1=f1,
        accuracy=accuracy,
        roc_auc=_roc_auc(actual_labels, scores),
        threshold=round(operational_threshold, 4),
        correct_predictions=sum(1 for item in decisions if item.actual_is_fraud == item.predicted_is_fraud),
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
) -> tuple[Any, SplitEvaluation, dict[str, Any]]:
    if progress_callback:
        progress_callback(5, "loading_data")

    test_rows = [item.model_dump() for item in load_test_transactions()]
    audit_training_inputs(train_rows, val_rows, test_rows)

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
        progress_callback(70, "calibrating_threshold")

    # Train holdout guides AutoGluon; val is untouched by fit (threshold + metrics only).
    calibrated_threshold = calibrate_threshold_on_rows(predictor, val_rows)

    if progress_callback:
        progress_callback(80, "evaluating_val")

    val_evaluation = evaluate_split(
        predictor,
        val_rows,
        split_name="val",
        threshold=calibrated_threshold,
    )
    leaderboard = predictor.leaderboard(val_frame, silent=True).head(8).to_dict(orient="records")

    if progress_callback:
        progress_callback(95, "done")

    explanation = sanitize_for_json(
        {
            "top_model_rows": leaderboard,
            "calibrated_threshold": calibrated_threshold,
            "leakage_audit": audit_training_inputs(train_rows, val_rows, test_rows),
            "explanation_method": (
                "AutoGluon good_quality on the train split with local-heavy learners excluded "
                "(val/test never in fit), aligned label DGP, rich features, refit_full disabled. "
                "Threshold tuned on val only."
            ),
            "evaluation": val_evaluation.model_dump(),
        }
    )
    return predictor, val_evaluation, explanation


def evaluate_test(
    test_rows: list[dict[str, Any]],
    *,
    progress_callback: ProgressCallback | None = None,
) -> tuple[SplitEvaluation, dict[str, Any]]:
    if progress_callback:
        progress_callback(10, "loading_model")

    adapter = AutoGluonTabularAdapter(artifact_dir=get_model_dir())
    predictor = adapter.load_predictor()

    if progress_callback:
        progress_callback(50, "scoring_test")

    test_evaluation = evaluate_split(predictor, test_rows, split_name="test")

    if progress_callback:
        progress_callback(80, "computing_metrics")

    explanation = sanitize_for_json(
        {
            "explanation_method": (
                "Held-out test evaluation with engineered features and validation-calibrated threshold."
            ),
            "evaluation": test_evaluation.model_dump(),
        }
    )
    return test_evaluation, explanation


def evaluation_payload_for_db(evaluation: SplitEvaluation) -> dict[str, Any]:
    return sanitize_for_json(
        {
            "split": evaluation.split,
            "evaluation": evaluation.model_dump(),
            "records": [item.model_dump() for item in evaluation.records],
        }
    )
