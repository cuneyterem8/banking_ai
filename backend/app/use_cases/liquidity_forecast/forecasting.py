from __future__ import annotations

import importlib.util
import math
import shutil
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Callable

from app.ai.autogluon_runtime import autogluon_fit_lock
from app.config import get_settings
from app.use_cases.liquidity_forecast.data_generation import (
    FORECAST_HORIZON_DAYS,
    HISTORY_DAYS,
    HISTORY_START_DATE,
    _day_factor,
    _payday_factor,
    _season_factor,
)
from app.use_cases.liquidity_forecast.raw_data import (
    load_calendar_events,
    load_history_records,
    load_holdout_records,
    load_locations,
)
from app.use_cases.liquidity_forecast.schemas import (
    LiquidityCalendarEvent,
    LiquidityForecastPayload,
    LiquidityForecastRecord,
    LiquidityForecastSummary,
    LiquidityLocation,
    LiquiditySeriesProfile,
    LiquidityTimeSeriesRecord,
)

ProgressCallback = Callable[[int, str], None]


def autogluon_timeseries_available() -> bool:
    try:
        return importlib.util.find_spec("autogluon.timeseries") is not None
    except ModuleNotFoundError:
        return False


def _event_applies(event: LiquidityCalendarEvent, location: LiquidityLocation, target_date: date) -> bool:
    start = date.fromisoformat(event.start_date)
    end = date.fromisoformat(event.end_date)
    return (
        start <= target_date <= end
        and event.affected_location_type in {"all", location.location_type}
        and event.affected_region in {"all", location.region}
    )


def _event_multiplier(events: list[LiquidityCalendarEvent], location: LiquidityLocation, target_date: date) -> tuple[float, list[str]]:
    multiplier = 1.0
    reason_codes: list[str] = []
    for event in events:
        if _event_applies(event, location, target_date):
            multiplier *= event.impact_multiplier
            reason_codes.append(event.name)
    return multiplier, reason_codes


def _records_by_series(records: list[LiquidityTimeSeriesRecord]) -> dict[str, list[LiquidityTimeSeriesRecord]]:
    grouped: dict[str, list[LiquidityTimeSeriesRecord]] = defaultdict(list)
    for record in records:
        grouped[record.series_id].append(record)
    for series_records in grouped.values():
        series_records.sort(key=lambda item: item.date)
    return grouped


def _series_profiles(history_by_series: dict[str, list[LiquidityTimeSeriesRecord]]) -> list[LiquiditySeriesProfile]:
    profiles: list[LiquiditySeriesProfile] = []
    for series_id, records in sorted(history_by_series.items()):
        recent = records[-28:] if len(records) >= 28 else records
        last = records[-1]
        profiles.append(
            LiquiditySeriesProfile(
                series_id=series_id,
                location_name=last.location_name,
                location_type=last.location_type,
                region=last.region,
                history_days=len(records),
                recent_average_demand=round(mean(record.net_cash_demand for record in recent), 2),
                recent_peak_demand=round(max(record.net_cash_demand for record in recent), 2),
                last_closing_cash=round(last.closing_cash, 2),
                cash_capacity=last.cash_capacity,
                minimum_cash_threshold=last.minimum_cash_threshold,
            )
        )
    return profiles


def _forecast_start(holdout: list[LiquidityTimeSeriesRecord]) -> date:
    if holdout:
        return min(date.fromisoformat(record.date) for record in holdout)
    return date.fromordinal(HISTORY_START_DATE.toordinal() + HISTORY_DAYS)


def _same_weekday_average(records: list[LiquidityTimeSeriesRecord], target_date: date) -> float:
    same_weekday = [record.net_cash_demand for record in records if date.fromisoformat(record.date).weekday() == target_date.weekday()]
    sample = same_weekday[-8:] if len(same_weekday) >= 8 else same_weekday
    if sample:
        return mean(sample)
    return mean(record.net_cash_demand for record in records[-28:])


def _quantiles(predicted: float, location_type: str) -> tuple[float, float, float]:
    spread = 0.16 if location_type == "branch" else 0.21
    return (
        round(max(0.0, predicted * (1 - spread)), 2),
        round(max(0.0, predicted), 2),
        round(max(0.0, predicted * (1 + spread * 1.18)), 2),
    )


def _stockout_risk(available_after_demand: float, threshold: float) -> float:
    scale = max(threshold * 0.22, 1.0)
    raw = 1 / (1 + math.exp((available_after_demand - threshold) / scale))
    return round(max(0.0, min(1.0, raw)), 4)


def _baseline_forecast(
    *,
    history: list[LiquidityTimeSeriesRecord],
    holdout: list[LiquidityTimeSeriesRecord],
    locations: list[LiquidityLocation],
    events: list[LiquidityCalendarEvent],
    warnings: list[str],
) -> list[LiquidityForecastRecord]:
    history_by_series = _records_by_series(history)
    holdout_by_key = {(record.series_id, record.date): record for record in holdout}
    horizon_start = _forecast_start(holdout)
    forecasts: list[LiquidityForecastRecord] = []
    for location in sorted(locations, key=lambda item: item.series_id):
        records = history_by_series[location.series_id]
        projected_cash = records[-1].closing_cash
        recent_average = mean(record.net_cash_demand for record in records[-28:])
        for step in range(1, FORECAST_HORIZON_DAYS + 1):
            target_date = date.fromordinal(horizon_start.toordinal() + step - 1)
            same_weekday = _same_weekday_average(records, target_date)
            event_multiplier, reason_codes = _event_multiplier(events, location, target_date)
            baseline = 0.72 * same_weekday + 0.28 * recent_average
            seasonal_adjustment = _season_factor(target_date) / max(_season_factor(date.fromisoformat(records[-1].date)), 0.01)
            payday_adjustment = _payday_factor(target_date)
            dow_adjustment = _day_factor(location.location_type, target_date) / max(_day_factor(location.location_type, date.fromisoformat(records[-1].date)), 0.01)
            predicted = baseline * event_multiplier * seasonal_adjustment * payday_adjustment * (0.88 + 0.12 * dow_adjustment)
            p10, p50, p90 = _quantiles(predicted, location.location_type)
            conservative_cash_after_demand = projected_cash - p90
            risk = _stockout_risk(conservative_cash_after_demand, location.minimum_cash_threshold)
            recommended = 0.0
            if risk >= 0.42:
                target_cash = location.cash_capacity * (0.8 if location.location_type == "branch" else 0.74)
                recommended = round(max(0.0, target_cash - (projected_cash - p50)), 2)
                if recommended > 0:
                    reason_codes.append("Projected p90 demand breaches liquidity buffer")
            projected_cash = min(location.cash_capacity, max(0.0, projected_cash - p50 + recommended))
            actual = holdout_by_key.get((location.series_id, target_date.isoformat()))
            actual_demand = actual.net_cash_demand if actual else None
            forecasts.append(
                LiquidityForecastRecord(
                    forecast_id=f"LF-{location.series_id}-{target_date.isoformat()}",
                    series_id=location.series_id,
                    location_id=location.location_id,
                    location_name=location.location_name,
                    location_type=location.location_type,
                    region=location.region,
                    date=target_date.isoformat(),
                    horizon_step=step,
                    actual_net_cash_demand=actual_demand,
                    predicted_mean=round(predicted, 2),
                    predicted_p10=p10,
                    predicted_p50=p50,
                    predicted_p90=p90,
                    absolute_error=round(abs(predicted - actual_demand), 2) if actual_demand is not None else None,
                    stockout_risk=risk,
                    recommended_replenishment=recommended,
                    projected_closing_cash=round(projected_cash, 2),
                    reason_codes=reason_codes or ["Seasonal day-of-week baseline"],
                )
            )
    warnings.append("AutoGluon TimeSeries was unavailable or skipped; local seasonal baseline was used.")
    return forecasts


def _try_autogluon_forecast(
    *,
    history: list[LiquidityTimeSeriesRecord],
    holdout: list[LiquidityTimeSeriesRecord],
    locations: list[LiquidityLocation],
    events: list[LiquidityCalendarEvent],
    artifact_dir: Path,
    progress_callback: ProgressCallback | None,
) -> tuple[list[LiquidityForecastRecord], str] | None:
    if not autogluon_timeseries_available():
        return None
    try:
        import pandas as pd
        from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor

        if progress_callback:
            progress_callback(25, "fitting_autogluon_timeseries")
        settings = get_settings()
        frame = pd.DataFrame(
            [
                {
                    "item_id": record.series_id,
                    "timestamp": pd.Timestamp(record.date),
                    "target": record.net_cash_demand,
                }
                for record in history
            ]
        )
        train_data = TimeSeriesDataFrame.from_data_frame(frame, id_column="item_id", timestamp_column="timestamp")
        if artifact_dir.exists():
            shutil.rmtree(artifact_dir)
        artifact_dir.parent.mkdir(parents=True, exist_ok=True)
        predictor = TimeSeriesPredictor(
            prediction_length=FORECAST_HORIZON_DAYS,
            target="target",
            eval_metric="MASE",
            path=str(artifact_dir),
            verbosity=0,
        )
        with autogluon_fit_lock():
            predictor.fit(
                train_data,
                presets="fast_training",
                time_limit=max(20, min(settings.local_model_timeout_seconds, 75)),
            )
        raw_predictions = predictor.predict(train_data)
        if progress_callback:
            progress_callback(60, "formatting_autogluon_forecasts")
        forecasts = _format_autogluon_predictions(
            raw_predictions=raw_predictions,
            history=history,
            holdout=holdout,
            locations=locations,
            events=events,
        )
        return forecasts, "autogluon.timeseries.TimeSeriesPredictor"
    except Exception:
        return None


def _prediction_value(row: object, key: str, fallback: float) -> float:
    try:
        value = row[key]  # type: ignore[index]
    except Exception:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _format_autogluon_predictions(
    *,
    raw_predictions: object,
    history: list[LiquidityTimeSeriesRecord],
    holdout: list[LiquidityTimeSeriesRecord],
    locations: list[LiquidityLocation],
    events: list[LiquidityCalendarEvent],
) -> list[LiquidityForecastRecord]:
    history_by_series = _records_by_series(history)
    holdout_by_key = {(record.series_id, record.date): record for record in holdout}
    horizon_start = _forecast_start(holdout)
    forecasts: list[LiquidityForecastRecord] = []
    for location in sorted(locations, key=lambda item: item.series_id):
        projected_cash = history_by_series[location.series_id][-1].closing_cash
        try:
            series_predictions = raw_predictions.loc[location.series_id]  # type: ignore[attr-defined]
        except Exception:
            series_predictions = []
        for step in range(1, FORECAST_HORIZON_DAYS + 1):
            target_date = date.fromordinal(horizon_start.toordinal() + step - 1)
            try:
                row = series_predictions.iloc[step - 1]  # type: ignore[attr-defined]
            except Exception:
                row = {}
            fallback = _same_weekday_average(history_by_series[location.series_id], target_date)
            predicted_mean = _prediction_value(row, "mean", fallback)
            predicted_p10 = _prediction_value(row, "0.1", predicted_mean * 0.84)
            predicted_p50 = _prediction_value(row, "0.5", predicted_mean)
            predicted_p90 = _prediction_value(row, "0.9", predicted_mean * 1.19)
            event_multiplier, reason_codes = _event_multiplier(events, location, target_date)
            if event_multiplier != 1.0:
                predicted_mean *= event_multiplier
                predicted_p10 *= event_multiplier
                predicted_p50 *= event_multiplier
                predicted_p90 *= event_multiplier
            risk = _stockout_risk(projected_cash - predicted_p90, location.minimum_cash_threshold)
            recommended = 0.0
            if risk >= 0.42:
                target_cash = location.cash_capacity * (0.8 if location.location_type == "branch" else 0.74)
                recommended = round(max(0.0, target_cash - (projected_cash - predicted_p50)), 2)
                if recommended > 0:
                    reason_codes.append("AutoGluon p90 demand breaches liquidity buffer")
            projected_cash = min(location.cash_capacity, max(0.0, projected_cash - predicted_p50 + recommended))
            actual = holdout_by_key.get((location.series_id, target_date.isoformat()))
            actual_demand = actual.net_cash_demand if actual else None
            forecasts.append(
                LiquidityForecastRecord(
                    forecast_id=f"LF-{location.series_id}-{target_date.isoformat()}",
                    series_id=location.series_id,
                    location_id=location.location_id,
                    location_name=location.location_name,
                    location_type=location.location_type,
                    region=location.region,
                    date=target_date.isoformat(),
                    horizon_step=step,
                    actual_net_cash_demand=actual_demand,
                    predicted_mean=round(predicted_mean, 2),
                    predicted_p10=round(max(0.0, predicted_p10), 2),
                    predicted_p50=round(max(0.0, predicted_p50), 2),
                    predicted_p90=round(max(0.0, predicted_p90), 2),
                    absolute_error=round(abs(predicted_mean - actual_demand), 2) if actual_demand is not None else None,
                    stockout_risk=risk,
                    recommended_replenishment=recommended,
                    projected_closing_cash=round(projected_cash, 2),
                    reason_codes=reason_codes or ["AutoGluon TimeSeries forecast"],
                )
            )
    return forecasts


def _summary(
    *,
    forecasts: list[LiquidityForecastRecord],
    provider_used: str,
    model_name: str,
    warnings: list[str],
    fallback_count: int,
    timeout_count: int,
) -> LiquidityForecastSummary:
    scored = [item for item in forecasts if item.actual_net_cash_demand is not None]
    errors = [abs(item.predicted_mean - float(item.actual_net_cash_demand)) for item in scored]
    squared_errors = [error * error for error in errors]
    percentage_errors = [
        error / max(float(item.actual_net_cash_demand), 1.0)
        for error, item in zip(errors, scored)
    ]
    coverage = [
        1
        if item.actual_net_cash_demand is not None
        and item.predicted_p10 <= float(item.actual_net_cash_demand) <= item.predicted_p90
        else 0
        for item in scored
    ]
    series_count = len({item.series_id for item in forecasts})
    return LiquidityForecastSummary(
        series_count=series_count,
        history_days=HISTORY_DAYS,
        forecast_horizon_days=FORECAST_HORIZON_DAYS,
        forecast_count=len(forecasts),
        provider_used=provider_used,
        model_name=model_name,
        mae=round(mean(errors), 2) if errors else 0,
        rmse=round(math.sqrt(mean(squared_errors)), 2) if squared_errors else 0,
        mape=round(mean(percentage_errors), 4) if percentage_errors else 0,
        p10_p90_coverage=round(sum(coverage) / len(coverage), 4) if coverage else 0,
        average_stockout_risk=round(mean(item.stockout_risk for item in forecasts), 4) if forecasts else 0,
        high_risk_forecast_count=sum(1 for item in forecasts if item.stockout_risk >= 0.55),
        recommended_replenishment_total=round(sum(item.recommended_replenishment for item in forecasts), 2),
        fallback_count=fallback_count,
        timeout_count=timeout_count,
        warning_count=len(warnings),
    )


def run_liquidity_forecast(
    *,
    progress_callback: ProgressCallback | None = None,
    prefer_autogluon: bool = True,
) -> LiquidityForecastPayload:
    if progress_callback:
        progress_callback(10, "loading_raw_timeseries")
    history = load_history_records()
    holdout = load_holdout_records()
    locations = load_locations()
    events = load_calendar_events()
    warnings: list[str] = []
    provider_used = "local-seasonal-baseline"
    model_name = "seasonal_day_of_week_baseline"
    fallback_count = 0
    timeout_count = 0
    forecasts: list[LiquidityForecastRecord] | None = None
    if prefer_autogluon:
        if progress_callback:
            progress_callback(18, "checking_autogluon_timeseries")
        settings = get_settings()
        autogluon_result = _try_autogluon_forecast(
            history=history,
            holdout=holdout,
            locations=locations,
            events=events,
            artifact_dir=Path(settings.storage_dir) / "liquidity-forecast" / "autogluon-timeseries",
            progress_callback=progress_callback,
        )
        if autogluon_result is not None:
            forecasts, model_name = autogluon_result
            provider_used = "autogluon-timeseries"
        else:
            fallback_count = 1
    if forecasts is None:
        if progress_callback:
            progress_callback(42, "running_seasonal_baseline")
        forecasts = _baseline_forecast(
            history=history,
            holdout=holdout,
            locations=locations,
            events=events,
            warnings=warnings,
        )
    if progress_callback:
        progress_callback(82, "calculating_metrics")
    profiles = _series_profiles(_records_by_series(history))
    summary = _summary(
        forecasts=forecasts,
        provider_used=provider_used,
        model_name=model_name,
        warnings=warnings,
        fallback_count=fallback_count,
        timeout_count=timeout_count,
    )
    return LiquidityForecastPayload(
        summary=summary,
        forecasts=forecasts,
        series_profiles=profiles,
        calendar_events=events,
        warnings=warnings,
    )
