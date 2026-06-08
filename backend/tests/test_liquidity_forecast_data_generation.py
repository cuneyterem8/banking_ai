from app.use_cases.liquidity_forecast.data_generation import (
    FORECAST_HORIZON_DAYS,
    GENERATION_SEED,
    HISTORY_DAYS,
    build_time_series,
    liquidity_data_root,
    write_artifacts,
)
from app.use_cases.liquidity_forecast.raw_data import (
    load_calendar_events,
    load_ground_truth,
    load_history_records,
    load_holdout_records,
    load_manifest,
)


def test_liquidity_generation_layout_and_manifest() -> None:
    paths = write_artifacts()
    manifest = load_manifest()
    ground_truth = load_ground_truth()

    assert set(paths.keys()) == {
        "raw_root",
        "timeseries_xlsx",
        "holiday_calendar",
        "campaign_calendar",
        "cash_policy_pdf",
        "metadata",
        "ground_truth",
    }
    assert manifest["generation_seed"] == GENERATION_SEED
    assert manifest["history_days"] == HISTORY_DAYS
    assert manifest["forecast_horizon_days"] == FORECAST_HORIZON_DAYS
    assert manifest["location_count"] == 6
    assert manifest["history_record_count"] == 1080
    assert manifest["holdout_record_count"] == ground_truth["holdout_actual_count"]
    assert (liquidity_data_root() / "raw" / "timeseries" / "synthetic_liquidity_cash_timeseries.xlsx").exists()
    assert (liquidity_data_root() / "raw" / "calendar" / "holiday_calendar.csv").exists()
    assert (liquidity_data_root() / "raw" / "policies" / "cash_inventory_policy.pdf").exists()


def test_liquidity_generation_is_deterministic_for_records() -> None:
    first_history, first_holdout = build_time_series()
    second_history, second_holdout = build_time_series()

    assert first_history[:5] == second_history[:5]
    assert first_holdout[:5] == second_holdout[:5]
    assert first_history[0]["series_id"] == "BR-CENTRAL-001"


def test_liquidity_raw_loaders_read_generated_artifacts() -> None:
    write_artifacts()
    history = load_history_records()
    holdout = load_holdout_records()
    events = load_calendar_events()

    assert len(history) == 1080
    assert len(holdout) == 84
    assert len(events) == 7
    assert history[0].net_cash_demand > 0
    assert holdout[0].date >= "2026-06-30"
