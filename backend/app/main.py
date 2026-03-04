from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import assistant_router, health_router, voice_router, voices_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.request_context import request_id_var
from app.services.storage_service import StorageService

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="VSE Backend",
    version="0.1.0",
    description="Voice assistant backend with Applio voice conversion.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex)
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
        )
    finally:
        request_id_var.reset(token)

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["x-request-id"] = request_id
    response.headers["x-duration-ms"] = str(duration_ms)
    return response


app.include_router(health_router)
app.include_router(voices_router)
app.include_router(voice_router)
app.include_router(assistant_router)

# Ensure storage dirs exist and expose outputs via static route.
storage = StorageService(settings=settings)
app.mount("/storage", StaticFiles(directory=storage.settings.storage_root), name="storage")

