from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    app_env: str
    host: str
    port: int
    cors_origins: list[str]

    stt_provider: str
    llm_provider: str
    tts_provider: str

    openai_api_key: str
    openai_llm_model: str
    openai_stt_model: str
    openai_tts_model: str
    openai_tts_voice: str

    applio_root: Path
    applio_python: Path
    applio_timeout_seconds: int

    storage_root: Path
    rvc_model_root: Path
    xtts_speaker_root: Path
    xtts_model_name: str
    xtts_device: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "dev"),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        cors_origins=_csv_env("CORS_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500"),
        stt_provider=os.getenv("STT_PROVIDER", "openai").lower(),
        llm_provider=os.getenv("LLM_PROVIDER", "openai").lower(),
        tts_provider=os.getenv("TTS_PROVIDER", "edge").lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_llm_model=os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"),
        openai_stt_model=os.getenv("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe"),
        openai_tts_model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
        openai_tts_voice=os.getenv("OPENAI_TTS_VOICE", "alloy"),
        applio_root=Path(os.getenv("APPLIO_ROOT", "/Users/fabianprimus/applio/Applio")).expanduser().resolve(),
        applio_python=Path(
            os.getenv("APPLIO_PYTHON", "/Users/fabianprimus/applio/Applio/.venv/bin/python")
        )
        .expanduser()
        ,
        applio_timeout_seconds=int(os.getenv("APPLIO_TIMEOUT_SECONDS", "600")),
        storage_root=Path(os.getenv("STORAGE_ROOT", str(BACKEND_ROOT / "storage"))).expanduser().resolve(),
        rvc_model_root=Path(os.getenv("RVC_MODEL_ROOT", str(BACKEND_ROOT / "models" / "rvc")))
        .expanduser()
        .resolve(),
        xtts_speaker_root=Path(
            os.getenv("XTTS_SPEAKER_ROOT", str(BACKEND_ROOT / "models" / "xtts_speakers"))
        )
        .expanduser()
        .resolve(),
        xtts_model_name=os.getenv("XTTS_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2"),
        xtts_device=os.getenv("XTTS_DEVICE", "cpu"),
    )
