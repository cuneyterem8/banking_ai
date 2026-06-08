from sqlmodel import Session

from app.api.use_cases import get_raw_data
from app.db.models import ModelRun, ProcessedResult, UseCase
from app.services.seeding import seed_liquidity_forecast
from app.use_cases.liquidity_forecast.forecasting import run_liquidity_forecast
from app.use_cases.liquidity_forecast.service import LIQUIDITY_FORECAST_RESULT_TYPE, get_liquidity_latest
from app.use_cases.registry import get_use_case


def _ensure_liquidity_use_case(session: Session) -> None:
    item = get_use_case("liquidity-forecast")
    assert item is not None
    session.merge(
        UseCase(
            slug=item.slug,
            title=item.title,
            category=item.category,
            description=item.description,
            adapter_type=item.adapter_type,
            model_family=item.model_family,
            status=item.status,
            implementation_order=item.implementation_order,
        )
    )
    session.commit()


def test_seed_liquidity_forecast_raw_api_payload(session: Session) -> None:
    _ensure_liquidity_use_case(session)
    seed_liquidity_forecast(session)

    payload = get_raw_data("liquidity-forecast", session)

    assert len(payload["datasets"]) == 1
    assert payload["datasets"][0]["dataset_key"] == "cash_timeseries"
    assert payload["datasets"][0]["payload"]["location_count"] == 6
    assert payload["datasets"][0]["payload"]["history_record_count"] == 1080
    assert payload["datasets"][0]["payload"]["holdout_record_count"] == 84
    assert len(payload["artifacts"]) == 6


def test_run_liquidity_forecast_baseline_returns_metrics() -> None:
    payload = run_liquidity_forecast(prefer_autogluon=False)

    assert payload.summary.provider_used == "local-seasonal-baseline"
    assert payload.summary.series_count == 6
    assert payload.summary.forecast_horizon_days == 14
    assert payload.summary.forecast_count == 84
    assert payload.summary.mae > 0
    assert 0 <= payload.summary.p10_p90_coverage <= 1
    assert payload.forecasts[0].reason_codes
    assert payload.series_profiles[0].history_days == 180


def test_get_liquidity_latest_returns_persisted_result(session: Session) -> None:
    _ensure_liquidity_use_case(session)
    run = ModelRun(
        use_case_slug="liquidity-forecast",
        adapter_type="autogluon-timeseries",
        provider_used="local-seasonal-baseline",
        model_name="seasonal_day_of_week_baseline",
        status="completed",
        metrics={"forecast_count": 84},
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    session.add(
        ProcessedResult(
            run_id=run.id,
            use_case_slug="liquidity-forecast",
            result_type=LIQUIDITY_FORECAST_RESULT_TYPE,
            payload={
                "summary": {"forecast_count": 84, "provider_used": "local-seasonal-baseline"},
                "forecasts": [],
                "series_profiles": [],
                "calendar_events": [],
                "warnings": [],
            },
            explanation={},
        )
    )
    session.commit()

    payload = get_liquidity_latest(session)

    assert payload["latest"] is not None
    assert payload["latest"]["run"]["id"] == run.id
    assert payload["latest"]["payload"]["summary"]["provider_used"] == "local-seasonal-baseline"
