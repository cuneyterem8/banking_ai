from app.ai.base import AdapterHealth


class WebSearchAdapter:
    name = "Web Search"
    provider = "external-web-search"

    def health_check(self) -> AdapterHealth:
        return AdapterHealth(
            name=self.name,
            available=False,
            provider=self.provider,
            model_name=None,
            message="Web search is planned for the Market Intelligence stage.",
            setup_hint="Configure the selected web-search provider when stage 9 starts.",
        )
