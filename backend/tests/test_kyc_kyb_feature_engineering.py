from app.use_cases.kyc_kyb.data_generation import write_artifacts
from app.use_cases.kyc_kyb.extraction import extract_packages
from app.use_cases.kyc_kyb.feature_engineering import LABEL_COLUMN, build_feature_rows, prepare_ml_frame
from app.use_cases.kyc_kyb.raw_data import load_val_packages
from app.use_cases.kyc_kyb.rules import evaluate_all_rules
from app.use_cases.kyc_kyb.threshold_tuning import f1_at_threshold, find_operational_threshold
from sklearn.metrics import recall_score

from app.use_cases.kyc_kyb.metrics import MINIMUM_RECALL_TARGET


def test_kyc_kyb_feature_engineering_is_deterministic_and_drops_leakage_fields() -> None:
    write_artifacts()
    packages = load_val_packages()
    documents, _ = extract_packages(packages)
    findings = evaluate_all_rules(packages, documents)

    first = build_feature_rows(packages, documents, findings)
    second = build_feature_rows(packages, documents, findings)
    assert first == second
    assert any(row["hard_fail_rule_count"] > 0 for row in first)
    assert any(row["address_mismatch_flag"] == 1 or row["missing_beneficial_owner_flag"] == 1 for row in first)

    frame = prepare_ml_frame(first)
    for forbidden in (
        "package_id",
        "subject_name",
        "address",
        "expected_status",
        "expected_rule_flags",
        "failed_rule_ids",
        "missing_documents",
        "field_mismatches",
    ):
        assert forbidden not in frame.columns
    assert LABEL_COLUMN in frame.columns


def test_kyc_kyb_threshold_tuning_prefers_recall_biased_f1() -> None:
    labels = [0, 0, 1, 1, 1, 0, 1, 0]
    scores = [0.08, 0.22, 0.41, 0.68, 0.86, 0.37, 0.75, 0.18]

    threshold = find_operational_threshold(labels, scores)
    predictions = [1 if score >= threshold else 0 for score in scores]

    assert 0.0 <= threshold <= 1.0
    assert recall_score(labels, predictions, zero_division=0) >= MINIMUM_RECALL_TARGET
    assert f1_at_threshold(labels, scores, threshold) > 0
