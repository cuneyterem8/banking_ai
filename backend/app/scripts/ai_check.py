from pathlib import Path

from app.ai.autogluon_adapter import AutoGluonTabularAdapter
from app.ai.autogluon_timeseries_adapter import AutoGluonTimeSeriesAdapter
from app.ai.ocr_adapter import LocalOCRAdapter
from app.ai.ollama_qwen_adapter import OllamaQwenAdapter
from app.ai.openai_gpt4o_adapter import OpenAIGPT4oAdapter
from app.ai.web_search_adapter import WebSearchAdapter
from app.config import get_settings


def main() -> None:
    settings = get_settings()
    checks = [
        AutoGluonTabularAdapter(Path(settings.storage_dir) / "fraud-detection" / "autogluon").health_check(),
        AutoGluonTimeSeriesAdapter().health_check(),
        LocalOCRAdapter().health_check(),
        OllamaQwenAdapter().health_check(),
        OpenAIGPT4oAdapter().health_check(),
        WebSearchAdapter().health_check(),
    ]
    for item in checks:
        status = "OK" if item.available else "MISSING"
        print(f"[{status}] {item.name} ({item.provider}) - {item.message}")
        if item.setup_hint:
            print(f"       {item.setup_hint}")


if __name__ == "__main__":
    main()
