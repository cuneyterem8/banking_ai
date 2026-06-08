from app.data_paths import get_use_case_data_dir
from app.use_cases.credit_risk.data_generation import (
    GENERATION_SEED,
    HEADERS,
    ML_TRAIN_COUNT,
    ML_VAL_COUNT,
    TEST_COUNT,
    TOTAL_COUNT,
    build_applications,
    split_train_val_test,
    write_artifacts,
)


def test_credit_applications_are_deterministic() -> None:
    first = build_applications(count=12, seed=GENERATION_SEED)
    second = build_applications(count=12, seed=GENERATION_SEED)
    assert first == second
    assert set(first[0].keys()) == set(HEADERS)


def test_credit_applications_include_default_labels() -> None:
    rows = build_applications()
    assert len(rows) == TOTAL_COUNT
    default_count = sum(row["label_default_12m"] for row in rows)
    default_rate = default_count / len(rows)
    assert 0.06 <= default_rate <= 0.22


def test_credit_split_is_deterministic_and_disjoint() -> None:
    rows = build_applications()
    train_a, val_a, test_a = split_train_val_test(rows)
    train_b, val_b, test_b = split_train_val_test(build_applications())
    assert len(train_a) == ML_TRAIN_COUNT
    assert len(val_a) == ML_VAL_COUNT
    assert len(test_a) == TEST_COUNT
    assert train_a == train_b
    assert val_a == val_b
    assert test_a == test_b
    ids = {row["application_id"] for row in train_a + val_a + test_a}
    assert len(ids) == ML_TRAIN_COUNT + ML_VAL_COUNT + TEST_COUNT


def test_write_credit_artifacts_targets_data_directory_xlsx_only() -> None:
    paths = write_artifacts()
    root = get_use_case_data_dir("credit-risk")
    assert str(root.resolve()) in paths["train_xlsx"]
    assert str(root.resolve()) in paths["val_xlsx"]
    assert str(root.resolve()) in paths["test_xlsx"]
    assert set(paths.keys()) == {"metadata", "train_xlsx", "val_xlsx", "test_xlsx"}
