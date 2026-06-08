from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.autogluon_runtime import apply_runtime_patches
from app.api.health import router as health_router
from app.api.use_cases import router as use_cases_router
from app.services.ml_job_queue import mark_api_ready
from app.services.ml_training_manager import start_all_training_background


@asynccontextmanager
async def lifespan(_app: FastAPI):
    apply_runtime_patches()
    start_all_training_background()
    mark_api_ready()
    yield


app = FastAPI(title="Banking AI Portal API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(use_cases_router, prefix="/api")
