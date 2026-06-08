from pydantic import BaseModel, Field


class LiquidityLocation(BaseModel):
    series_id: str
    location_id: str
    location_name: str
    location_type: str
    region: str
    cash_capacity: float
    minimum_cash_threshold: float
    service_target: float


class LiquidityTimeSeriesRecord(BaseModel):
    series_id: str
    location_id: str
    location_name: str
    location_type: str
    region: str
    date: str
    day_of_week: str
    is_weekend: int
    holiday_flag: int
    holiday_name: str | None = None
    campaign_flag: int
    campaign_name: str | None = None
    cash_outflow: float
    cash_inflow: float
    net_cash_demand: float
    opening_cash: float
    closing_cash: float
    replenishment_amount: float
    stockout_event: int
    cash_capacity: float
    minimum_cash_threshold: float


class LiquidityCalendarEvent(BaseModel):
    event_id: str
    event_type: str
    name: str
    start_date: str
    end_date: str
    impact_multiplier: float
    affected_location_type: str = "all"
    affected_region: str = "all"


class LiquidityForecastRecord(BaseModel):
    forecast_id: str
    series_id: str
    location_id: str
    location_name: str
    location_type: str
    region: str
    date: str
    horizon_step: int
    actual_net_cash_demand: float | None = None
    predicted_mean: float
    predicted_p10: float
    predicted_p50: float
    predicted_p90: float
    absolute_error: float | None = None
    stockout_risk: float = Field(ge=0, le=1)
    recommended_replenishment: float
    projected_closing_cash: float
    reason_codes: list[str] = Field(default_factory=list)


class LiquiditySeriesProfile(BaseModel):
    series_id: str
    location_name: str
    location_type: str
    region: str
    history_days: int
    recent_average_demand: float
    recent_peak_demand: float
    last_closing_cash: float
    cash_capacity: float
    minimum_cash_threshold: float


class LiquidityForecastSummary(BaseModel):
    series_count: int
    history_days: int
    forecast_horizon_days: int
    forecast_count: int
    provider_used: str
    model_name: str
    mae: float
    rmse: float
    mape: float
    p10_p90_coverage: float
    average_stockout_risk: float
    high_risk_forecast_count: int
    recommended_replenishment_total: float
    fallback_count: int
    timeout_count: int
    warning_count: int


class LiquidityForecastPayload(BaseModel):
    summary: LiquidityForecastSummary
    forecasts: list[LiquidityForecastRecord]
    series_profiles: list[LiquiditySeriesProfile]
    calendar_events: list[LiquidityCalendarEvent]
    warnings: list[str] = Field(default_factory=list)
