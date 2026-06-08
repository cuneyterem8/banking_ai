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
from app.use_cases.kyc_kyb.feature_engineering import (
    LABEL_COLUMN,
    load_operational_threshold,
    prepare_ml_frame,
    save_operational_threshold,
)
from app.use_cases.kyc_kyb.metrics import AUTOGLUON_EVAL_METRIC, PRIMARY_METRIC, PRIMARY_METRIC_LABEL
from app.use_cases.kyc_kyb.schemas import (
    ConfusionMatrix,
    KycKybExtractedDocument,
    KycKybPackageDecision,
    KycKybPackageRecord,
    KycKybRuleFinding,
    KycKybSplitEvaluation,
    PrPoint,
    RocPoint,
)
from app.use_cases.kyc_kyb.threshold_tuning import find_operational_threshold
from app.utils.json_safe import json_safe_float, sanitize_for_json

ProgressCallback = Callable[[int, str], None]
MEDIUM_RISK_THRESHOLD = 0.3
CRITICAL_RISK_THRESHOLD = 0.78


def get_model_dir() -> Any:
    settings = get_settings()
    return settings.storage_dir / "models" / "kyc-kyb" / "autogluon"


def _resolve_threshold(model_dir: Any, override: float | None = None) -> float:
    if override is not None:
        return override
    return load_operational_threshold(model_dir)


def _risk_level(probability: float, threshold: float, hard_rule_triggered: bool) -> str:
    if probability >= max(CRITICAL_RISK_THRESHOLD, threshold + 0.16) or (
        hard_rule_triggered and probability >= threshold
    ):
        return "Critical"
    if hard_rule_triggered or probability >= threshold:
        return "High"
    if probability >= MEDIUM_RISK_THRESHOLD:
        return "Medium"
    return "Low"


def _verification_status(probability: float, threshold: float, hard_rule_triggered: bool) -> str:
    if hard_rule_triggered:
        return "Rejected"
    if probability >= threshold:
        return "Needs Review"
    return "Approved"


def _manual_review_required(probability: float, threshold: float, hard_rule_triggered: bool) -> int:
    return 1 if hard_rule_triggered or probability >= threshold else 0


def _split_semicolon(value: Any) -> list[str]:
    return [item.strip() for item in str(value or "").split(";") if item.strip()]


def _row_provider(row: dict[str, Any]) -> str:
    if int(row.get("fallback_unavailable_count", 0) or 0) > 0:
        return "fallback-unavailable"
    if int(row.get("gpt4o_fallback_count", 0) or 0) > 0:
        return "local-ocr-rules-autogluon+gpt-4o-fallback"
    return "local-ocr-rules-autogluon"


def _top_factors(row: dict[str, Any]) -> list[str]:
    factors: list[str] = []
    failed_rules = _split_semicolon(row.get("failed_rule_ids"))
    rule_messages = {
        "sanctions_watchlist_match": "Synthetic sanctions watchlist match is present.",
        "high_risk_jurisdiction": "Jurisdiction appears on the synthetic high-risk list.",
        "expired_identity_document": "Identity document is expired.",
        "signatory_id_expired": "Authorized signatory ID is expired.",
        "missing_tax_certification": "Tax certification is missing or incomplete.",
        "missing_beneficial_owner": "Beneficial ownership information is missing.",
        "ownership_total_incomplete": "Beneficial ownership coverage is below policy minimum.",
        "risk_attestation_missing": "KYB risk attestation is missing or incomplete.",
        "address_mismatch": "Address evidence does not match onboarding records.",
        "required_documents_present": "At least one required document could not be extracted.",
    }
    for rule_id in failed_rules:
        message = rule_messages.get(rule_id)
        if message:
            factors.append(message)
    if int(row.get("fallback_unavailable_count", 0) or 0) > 0:
        factors.append("Image extraction fallback was unavailable for at least one document.")
    if float(row.get("average_extraction_confidence", 1.0) or 0) < 0.8:
        factors.append("Average document extraction confidence is below the review band.")
    if not factors:
        factors.append("No dominant KYC/KYB review factor was detected.")
    return factors[:5]


def _manual_review_probabilities(predictor: Any, feature_frame: pd.DataFrame) -> list[float]:
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
    scores: list[float],
    *,
    threshold: float,
) -> list[KycKybPackageDecision]:
    decisions: list[KycKybPackageDecision] = []
    for row, actual, probability in zip(feature_rows, actual_labels, scores, strict=True):
        hard_rule_triggered = int(row.get("hard_fail_rule_count", 0) or 0) > 0
        risk_level = _risk_level(float(probability), threshold, hard_rule_triggered)
        decisions.append(
            KycKybPackageDecision(
                package_id=str(row["package_id"]),
                subject_type=str(row["subject_type"]),
                subject_name=str(row["subject_name"]),
                verification_status=_verification_status(float(probability), threshold, hard_rule_triggered),
                risk_score=round(float(probability), 4),
                risk_level=risk_level,
                manual_review_required=_manual_review_required(float(probability), threshold, hard_rule_triggered),
                actual_manual_review_required=int(actual),
                hard_rule_triggered=hard_rule_triggered,
                top_factors=_top_factors(row),
                missing_documents=_split_semicolon(row.get("missing_documents")),
                field_mismatches=_split_semicolon(row.get("field_mismatches")),
                provider_used=_row_provider(row),
            )
        )
    return decisions


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
    scores = _manual_review_probabilities(predictor, feature_frame)
    threshold = find_operational_threshold(actual_labels, scores)
    save_operational_threshold(get_model_dir(), threshold)
    return threshold


def evaluate_split(
    predictor: Any,
    rows: list[dict[str, Any]],
    *,
    split_name: str,
    threshold: float | None = None,
) -> KycKybSplitEvaluation:
    model_dir = get_model_dir()
    operational_threshold = _resolve_threshold(model_dir, threshold)
    feature_frame, actual_labels = _ml_features_from_rows(rows)
    if actual_labels is None:
        raise ValueError("Rows must include label_manual_review_required for evaluation.")
    scores = _manual_review_probabilities(predictor, feature_frame)
    raw_feature_rows = [dict(row) for row in rows]
    decisions = _build_decisions(raw_feature_rows, actual_labels, scores, threshold=operational_threshold)
    predictions = [item.manual_review_required for item in decisions]
    tn, fp, fn, tp = confusion_matrix(actual_labels, predictions, labels=[0, 1]).ravel()

    return KycKybSplitEvaluation(
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
        correct_predictions=sum(1 for item in decisions if item.actual_manual_review_required == item.manual_review_required),
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
) -> tuple[Any, KycKybSplitEvaluation, dict[str, Any]]:
    if progress_callback:
        progress_callback(8, "loading_kyc_kyb_packages")

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
        progress_callback(78, "evaluating_validation_packages")
    val_evaluation = evaluate_split(predictor, val_rows, split_name="val", threshold=calibrated_threshold)
    leaderboard = predictor.leaderboard(val_frame, silent=True).head(8).to_dict(orient="records")

    if progress_callback:
        progress_callback(88, "preparing_decisions")

    explanation = sanitize_for_json(
        {
            "top_model_rows": leaderboard,
            "calibrated_threshold": calibrated_threshold,
            "explanation_method": (
                "AutoGluon Tabular scored synthetic KYC/KYB onboarding packages with deterministic "
                "document extraction and policy-rule features. Validation rows tune the manual-review "
                "threshold and provide startup metrics."
            ),
            "evaluation": val_evaluation.model_dump(),
        }
    )
    return predictor, val_evaluation, explanation


def evaluate_test(
    test_rows: list[dict[str, Any]],
    *,
    progress_callback: ProgressCallback | None = None,
) -> tuple[KycKybSplitEvaluation, dict[str, Any]]:
    if progress_callback:
        progress_callback(10, "loading_kyc_kyb_model")
    adapter = AutoGluonTabularAdapter(artifact_dir=get_model_dir())
    predictor = adapter.load_predictor()

    if progress_callback:
        progress_callback(45, "scoring_test_packages")
    test_evaluation = evaluate_split(predictor, test_rows, split_name="test")

    if progress_callback:
        progress_callback(64, "computing_kyc_kyb_metrics")
    explanation = sanitize_for_json(
        {
            "explanation_method": "Held-out synthetic KYC/KYB package scoring with the validation-calibrated review threshold.",
            "evaluation": test_evaluation.model_dump(),
        }
    )
    return test_evaluation, explanation


def evaluation_payload_for_db(
    evaluation: KycKybSplitEvaluation,
    *,
    summary: dict[str, Any],
    packages: list[KycKybPackageRecord],
    documents: list[KycKybExtractedDocument],
    findings: list[KycKybRuleFinding],
    warnings: list[str],
) -> dict[str, Any]:
    return sanitize_for_json(
        {
            "split": evaluation.split,
            "summary": summary,
            "evaluation": evaluation.model_dump(),
            "packages": [item.model_dump() for item in packages],
            "extracted_documents": [item.model_dump() for item in documents],
            "rule_findings": [item.model_dump() for item in findings],
            "risk_decisions": [item.model_dump() for item in evaluation.records],
            "warnings": warnings,
        }
    )
