from app.ai.base import AdapterHealth
from app.config import get_settings


class WebSearchAdapter:
    name = "OpenAI Web Search"
    provider = "openai-web-search"

    def health_check(self) -> AdapterHealth:
        settings = get_settings()
        if not settings.market_live_search_enabled:
            return AdapterHealth(
                name=self.name,
                available=False,
                provider=self.provider,
                model_name=settings.market_research_model,
                message="Live market web search is disabled by MARKET_LIVE_SEARCH_ENABLED.",
                setup_hint="Set MARKET_LIVE_SEARCH_ENABLED=1 to enable real web-search runs.",
            )
        if not settings.openai_api_key:
            return AdapterHealth(
                name=self.name,
                available=False,
                provider=self.provider,
                model_name=settings.market_research_model,
                message="OpenAI web search is not configured. Market Intelligence startup can use synthetic corpus fallback.",
                setup_hint="Set OPENAI_API_KEY to enable live web search.",
            )
        return AdapterHealth(
            name=self.name,
            available=True,
            provider=self.provider,
            model_name=settings.market_research_model,
            message="OpenAI Responses web_search is configured for Market Intelligence.",
            setup_hint=None,
        )
