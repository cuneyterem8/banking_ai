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
from app.use_cases.credit_risk.data_leakage import audit_training_inputs
from app.use_cases.credit_risk.feature_engineering import (
    LABEL_COLUMN,
    enrich_rows,
    load_operational_threshold,
    prepare_ml_frame,
    save_operational_threshold,
)
from app.use_cases.credit_risk.metrics import AUTOGLUON_EVAL_METRIC, PRIMARY_METRIC, PRIMARY_METRIC_LABEL
from app.use_cases.credit_risk.raw_data import load_test_applications
from app.use_cases.credit_risk.schemas import (
    ConfusionMatrix,
    CreditDecision,
    PrPoint,
    RocPoint,
    SplitEvaluation,
)
from app.use_cases.credit_risk.threshold_tuning import find_best_f1_threshold
from app.utils.json_safe import json_safe_float, sanitize_for_json

DEFAULT_THRESHOLD = 0.28

ProgressCallback = Callable[[int, str], None]


def get_model_dir() -> Any:
    settings = get_settings()
    return settings.storage_dir / "credit-risk" / "autogluon"


def _resolve_threshold(model_dir: Any, override: float | None = None) -> float:
    if override is not None:
        return override
    return load_operational_threshold(model_dir)


def _risk_grade(probability: float) -> str:
    if probability < 0.03:
        return "A"
    if probability < 0.07:
        return "B"
    if probability < 0.15:
        return "C"
    if probability < 0.30:
        return "D"
    return "E"


def _decision(probability: float, requested_amount: float) -> str:
    if probability < 0.07:
        return "Approve"
    if probability < 0.15:
        return "Approve with lower limit"
    if probability < 0.30:
        return "Manual underwriting review"
    return "Decline"


def _recommended_limit(probability: float, requested_amount: float, collateral_value: float) -> float:
    if probability < 0.07:
        factor = 1.0
    elif probability < 0.15:
        factor = 0.68
    elif probability < 0.30:
        factor = 0.38
    else:
        factor = 0.0
    collateral_floor = min(collateral_value * 0.75, requested_amount)
    return round(max(requested_amount * factor, collateral_floor if factor > 0 else 0.0), 2)


def _predicted_default(probability: float, threshold: float) -> int:
    return 1 if probability >= threshold else 0


def _top_factors(row: dict[str, Any]) -> list[str]:
    factors: list[str] = []
    if row.get("debt_to_income_ratio", 0) > 0.42:
        factors.append("Debt-to-income ratio is elevated.")
    if row.get("payment_to_income_ratio", 0) > 0.22:
        factors.append("Requested payment is high relative to monthly income.")
    if row.get("credit_utilization", 0) > 0.75:
        factors.append("Credit utilization is high.")
    if row.get("delinquencies_12m", 0) >= 2:
        factors.append("Recent delinquency count is elevated.")
    if row.get("prior_defaults", 0) > 0:
        factors.append("Applicant has prior default history.")
    if row.get("liquid_reserve_months", 99) < 1.5:
        factors.append("Liquid reserves cover less than 1.5 months of expenses.")
    if row.get("collateral_coverage", 1) < 0.25:
        factors.append("Collateral coverage is low.")
    if row.get("employment_years", 99) < 1:
        factors.append("Employment history is short.")
    if not factors:
        factors.append("No dominant adverse factor was detected.")
    return factors[:3]


def _default_probabilities(predictor: Any, feature_frame: pd.DataFrame) -> list[float]:
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
    raw_rows: list[dict[str, Any]],
    actual_labels: list[int],
    scores: list[float],
    *,
    threshold: float,
) -> list[CreditDecision]:
    enriched_rows = enrich_rows(raw_rows)
    return [
        CreditDecision(
            application_id=str(row["application_id"]),
            customer_id=str(row["customer_id"]),
            requested_loan_amount=float(row["requested_loan_amount"]),
            actual_default_12m=int(actual),
            predicted_default_12m=_predicted_default(float(score), threshold),
            pd_probability=round(float(score), 4),
            risk_grade=_risk_grade(float(score)),
            decision=_decision(float(score), float(row["requested_loan_amount"])),
            recommended_limit=_recommended_limit(float(score), float(row["requested_loan_amount"]), float(row["collateral_value"])),
            expected_loss=round(float(score) * float(row["target_loss_given_default"]) * float(row["requested_loan_amount"]), 2),
            top_factors=_top_factors(enriched_row),
        )
        for row, enriched_row, actual, score in zip(raw_rows, enriched_rows, actual_labels, scores, strict=True)
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
    return points[:25]


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
        points.append(PrPoint(threshold=round(safe_threshold, 4), precision=round(safe_precision, 4), recall=round(safe_recall, 4)))
    return points[:25]


def _roc_auc(y_true: list[int], scores: list[float]) -> float | None:
    if len(set(y_true)) < 2:
        return None
    safe = json_safe_float(float(roc_auc_score(y_true, scores)), inf_replacement=1.0)
    return round(safe, 4) if safe is not None else None


def _pr_auc(y_true: list[int], scores: list[float]) -> float | None:
    if len(set(y_true)) < 2:
        return None
    safe = json_safe_float(float(average_precision_score(y_true, scores)), inf_replacement=1.0)
    return round(safe, 4) if safe is not None else None


def calibrate_threshold_on_rows(predictor: Any, rows: list[dict[str, Any]]) -> float:
    feature_frame, actual_labels = _ml_features_from_rows(rows)
    if actual_labels is None:
        return DEFAULT_THRESHOLD
    scores = _default_probabilities(predictor, feature_frame)
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
    operational_threshold = _resolve_threshold(get_model_dir(), threshold)
    feature_frame, actual_labels = _ml_features_from_rows(rows)
    if actual_labels is None:
        raise ValueError("Rows must include label_default_12m for evaluation.")
    scores = _default_probabilities(predictor, feature_frame)
    predictions = [_predicted_default(score, operational_threshold) for score in scores]
    raw_rows = [dict(row) for row in rows]
    decisions = _build_decisions(raw_rows, actual_labels, scores, threshold=operational_threshold)
    tn, fp, fn, tp = confusion_matrix(actual_labels, predictions, labels=[0, 1]).ravel()

    return SplitEvaluation(
        split=split_name,
        record_count=len(rows),
        primary_metric=PRIMARY_METRIC,
        primary_metric_label=PRIMARY_METRIC_LABEL,
        primary_score=_roc_auc(actual_labels, scores),
        pr_auc=_pr_auc(actual_labels, scores),
        precision=round(float(precision_score(actual_labels, predictions, zero_division=0)), 4),
        recall=round(float(recall_score(actual_labels, predictions, zero_division=0)), 4),
        f1=round(float(f1_score(actual_labels, predictions, zero_division=0)), 4),
        accuracy=round(float(accuracy_score(actual_labels, predictions)), 4),
        threshold=round(operational_threshold, 4),
        correct_predictions=sum(1 for item in decisions if item.actual_default_12m == item.predicted_default_12m),
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
    test_rows = [item.model_dump() for item in load_test_applications()]
    audit_training_inputs(train_rows, val_rows, test_rows)

    adapter = AutoGluonTabularAdapter(artifact_dir=get_model_dir())
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
    threshold = calibrate_threshold_on_rows(predictor, val_rows)
    if progress_callback:
        progress_callback(80, "evaluating_val")
    val_evaluation = evaluate_split(predictor, val_rows, split_name="val", threshold=threshold)
    leaderboard = predictor.leaderboard(val_frame, silent=True).head(8).to_dict(orient="records")
    if progress_callback:
        progress_callback(95, "done")
    explanation = sanitize_for_json(
        {
            "top_model_rows": leaderboard,
            "calibrated_threshold": threshold,
            "leakage_audit": audit_training_inputs(train_rows, val_rows, test_rows),
            "explanation_method": "AutoGluon tabular credit PD model fit on train split only; threshold tuned on validation split.",
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
            "explanation_method": "Held-out credit test evaluation with engineered affordability and credit-history features.",
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
