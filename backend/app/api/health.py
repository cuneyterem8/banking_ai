from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel import Session

from app.ai.autogluon_adapter import AutoGluonTabularAdapter
from app.ai.autogluon_timeseries_adapter import AutoGluonTimeSeriesAdapter
from app.ai.ocr_adapter import LocalOCRAdapter
from app.ai.ollama_qwen_adapter import OllamaQwenAdapter
from app.ai.openai_gpt4o_adapter import OpenAIGPT4oAdapter
from app.ai.web_search_adapter import WebSearchAdapter
from app.config import get_settings
from app.db.session import get_session
from app.services.ml_training_manager import get_platform_readiness, get_startup_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    session.exec(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}


@router.get("/ready")
def ready(session: Session = Depends(get_session)) -> dict:
    """API is up and can serve the portal. ML startup may still be running in the background."""
    session.exec(text("SELECT 1"))
    readiness = get_platform_readiness()
    body = {
        "status": "ready" if readiness["ready"] else "starting",
        **readiness,
    }
    if readiness["ready"]:
        return body
    return JSONResponse(status_code=503, content=body)


@router.get("/ml-ready")
def ml_ready(session: Session = Depends(get_session)) -> dict:
    """All background startup processing has finished or was skipped."""
    session.exec(text("SELECT 1"))
    readiness = get_platform_readiness()
    body = {
        "status": "ready" if readiness["ml_training_ready"] else "training",
        **readiness,
    }
    if readiness["ml_training_ready"]:
        return body
    return JSONResponse(status_code=503, content=body)


@router.get("/startup/status")
def startup_status(session: Session = Depends(get_session)) -> dict:
    session.exec(text("SELECT 1"))
    return get_startup_status()


@router.get("/ai/health")
def ai_health() -> dict:
    settings = get_settings()
    autogluon_dir = settings.storage_dir / "fraud-detection" / "autogluon"
    checks = [
        AutoGluonTabularAdapter(artifact_dir=autogluon_dir).health_check(),
        AutoGluonTimeSeriesAdapter().health_check(),
        LocalOCRAdapter().health_check(),
        OllamaQwenAdapter().health_check(),
        OpenAIGPT4oAdapter().health_check(),
        WebSearchAdapter().health_check(),
    ]
    return {"adapters": [item.__dict__ for item in checks]}
