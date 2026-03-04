from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


class STTService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def transcribe(self, audio_path: Path) -> str:
        if self.settings.stt_provider != "openai" or not self.settings.openai_api_key:
            raise RuntimeError("STT provider is not configured. Set OPENAI_API_KEY.")

        from openai import OpenAI

        client = OpenAI(api_key=self.settings.openai_api_key)
        with audio_path.open("rb") as f:
            result = client.audio.transcriptions.create(
                model=self.settings.openai_stt_model,
                file=f,
            )
        text = getattr(result, "text", "") or ""
        return text.strip()

