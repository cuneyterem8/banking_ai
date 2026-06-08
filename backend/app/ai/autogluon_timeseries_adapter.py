import importlib.util

from app.ai.base import AdapterHealth


class AutoGluonTimeSeriesAdapter:
    name = "AutoGluon TimeSeries"
    provider = "local-autogluon-timeseries"
    model_name = "autogluon.timeseries.TimeSeriesPredictor"

    def health_check(self) -> AdapterHealth:
        try:
            available = importlib.util.find_spec("autogluon.timeseries") is not None
        except ModuleNotFoundError:
            available = False
        if available:
            return AdapterHealth(
                name=self.name,
                available=True,
                provider=self.provider,
                model_name=self.model_name,
                message="AutoGluon TimeSeries is available.",
            )
        return AdapterHealth(
            name=self.name,
            available=False,
            provider=self.provider,
            model_name=self.model_name,
            message="AutoGluon TimeSeries is not installed. Liquidity Forecast will use the local seasonal baseline.",
            setup_hint="Optional: install AutoGluon TimeSeries in .venv for the full local time-series adapter.",
        )
