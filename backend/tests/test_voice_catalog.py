from pathlib import Path

from app.core.config import Settings
from app.services.voice_catalog import VoiceCatalogService


def test_list_voices_handles_missing_root(tmp_path: Path):
    settings = Settings(
        app_env="test",
        host="0.0.0.0",
        port=8000,
        cors_origins=["*"],
        stt_provider="openai",
        llm_provider="openai",
        tts_provider="edge",
        openai_api_key="",
        openai_llm_model="gpt-4o-mini",
        openai_stt_model="gpt-4o-mini-transcribe",
        openai_tts_model="gpt-4o-mini-tts",
        openai_tts_voice="alloy",
        applio_root=tmp_path,
        applio_python=tmp_path / "python",
        applio_timeout_seconds=60,
        storage_root=tmp_path / "storage",
        rvc_model_root=tmp_path / "missing",
        xtts_speaker_root=tmp_path / "xtts",
        xtts_model_name="xtts",
        xtts_device="cpu",
    )
    service = VoiceCatalogService(settings=settings)
    assert service.list_voices() == []

