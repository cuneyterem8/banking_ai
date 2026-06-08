from app.ai.base import AdapterHealth
from app.config import get_settings


class OpenAIGPT4oAdapter:
    name = "OpenAI GPT-4o"
    provider = "openai"

    def health_check(self) -> AdapterHealth:
        settings = get_settings()
        available = bool(settings.openai_api_key)
        return AdapterHealth(
            name=self.name,
            available=available,
            provider=self.provider,
            model_name=settings.openai_model,
            message="OpenAI API key is configured." if available else "OpenAI API key is not configured.",
            setup_hint=None if available else "Set OPENAI_API_KEY in .env before using GPT-4o fallback.",
        )
