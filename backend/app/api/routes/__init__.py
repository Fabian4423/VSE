from app.api.routes.assistant import router as assistant_router
from app.api.routes.health import router as health_router
from app.api.routes.voice import router as voice_router
from app.api.routes.voices import router as voices_router

__all__ = [
    "assistant_router",
    "health_router",
    "voice_router",
    "voices_router",
]

