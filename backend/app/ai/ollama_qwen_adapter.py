import httpx

from app.ai.base import AdapterHealth
from app.config import get_settings


class OllamaQwenAdapter:
    name = "Ollama Qwen"
    provider = "local-ollama"

    def health_check(self) -> AdapterHealth:
        settings = get_settings()
        try:
            response = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=2.0)
            response.raise_for_status()
            models = response.json().get("models", [])
            names = {item.get("name") for item in models}
            available = settings.ollama_model in names
            return AdapterHealth(
                name=self.name,
                available=available,
                provider=self.provider,
                model_name=settings.ollama_model,
                message="Ollama model is available." if available else "Ollama is running, but the configured Qwen model was not found.",
                setup_hint=None if available else f"Run: ollama pull {settings.ollama_model}",
            )
        except Exception as exc:
            return AdapterHealth(
                name=self.name,
                available=False,
                provider=self.provider,
                model_name=settings.ollama_model,
                message=f"Ollama health check failed: {exc}",
                setup_hint="Install Ollama and start it before local LLM use cases.",
            )
