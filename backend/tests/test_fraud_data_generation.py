from app.data_paths import get_use_case_data_dir
from app.use_cases.fraud_detection.data_generation import (
    GENERATION_SEED,
    HEADERS,
    ML_TRAIN_COUNT,
    ML_VAL_COUNT,
    TEST_COUNT,
    TOTAL_COUNT,
    build_transactions,
    split_train_val_test,
    write_artifacts,
)


def test_fraud_transactions_are_deterministic() -> None:
    first = build_transactions(count=12, seed=GENERATION_SEED)
    second = build_transactions(count=12, seed=GENERATION_SEED)
    assert first == second
    assert set(first[0].keys()) == set(HEADERS)
    assert len(HEADERS) >= 20


def test_fraud_transactions_include_positive_labels() -> None:
    rows = build_transactions()
    assert len(rows) == TOTAL_COUNT
    fraud_count = sum(row["label_is_fraud"] for row in rows)
    fraud_rate = fraud_count / len(rows)
    assert fraud_count > 0
    assert 0.04 <= fraud_rate <= 0.18
    currencies = {row["currency"] for row in rows}
    assert len(currencies) > 1


def test_train_val_test_split_is_deterministic_and_disjoint() -> None:
    rows = build_transactions()
    train_a, val_a, test_a = split_train_val_test(rows)
    train_b, val_b, test_b = split_train_val_test(build_transactions())
    assert len(train_a) == ML_TRAIN_COUNT
    assert len(val_a) == ML_VAL_COUNT
    assert len(test_a) == TEST_COUNT
    assert train_a == train_b
    assert val_a == val_b
    assert test_a == test_b
    ids = {row["transaction_id"] for row in train_a + val_a + test_a}
    assert len(ids) == ML_TRAIN_COUNT + ML_VAL_COUNT + TEST_COUNT


def test_write_artifacts_targets_data_directory_xlsx_only() -> None:
    paths = write_artifacts()
    root = get_use_case_data_dir("fraud-detection")
    assert str(root.resolve()) in paths["train_xlsx"]
    assert str(root.resolve()) in paths["val_xlsx"]
    assert str(root.resolve()) in paths["test_xlsx"]
    assert set(paths.keys()) == {"metadata", "train_xlsx", "val_xlsx", "test_xlsx"}
