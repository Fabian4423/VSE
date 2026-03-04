from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.core.config import Settings
from app.services.voice_catalog import VoiceCatalogService

logger = logging.getLogger(__name__)


class TTSService:
    def __init__(self, settings: Settings, voice_catalog: VoiceCatalogService) -> None:
        self.settings = settings
        self.voice_catalog = voice_catalog
        self._xtts = None

    def synthesize(
        self,
        text: str,
        output_path: Path,
        provider: str,
        voice: str | None = None,
        speaker_id: str | None = None,
        rate: int = 0,
    ) -> None:
        provider = provider.lower()
        if provider == "openai":
            self._synthesize_openai(text=text, output_path=output_path, voice=voice)
            return
        if provider == "xtts":
            self._synthesize_xtts(
                text=text, output_path=output_path, speaker_id=speaker_id
            )
            return
        if provider == "edge":
            self._synthesize_edge(text=text, output_path=output_path, voice=voice, rate=rate)
            return
        raise ValueError(f"Unsupported tts_provider '{provider}'.")

    def _synthesize_openai(self, text: str, output_path: Path, voice: str | None) -> None:
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for openai TTS.")

        from openai import OpenAI

        client = OpenAI(api_key=self.settings.openai_api_key)
        result = client.audio.speech.create(
            model=self.settings.openai_tts_model,
            voice=voice or self.settings.openai_tts_voice,
            input=text,
        )

        # API clients expose either write_to_file or stream_to_file depending on version.
        if hasattr(result, "write_to_file"):
            result.write_to_file(str(output_path))
        else:
            result.stream_to_file(str(output_path))

    def _synthesize_xtts(self, text: str, output_path: Path, speaker_id: str | None) -> None:
        if not speaker_id:
            raise ValueError("speaker_id is required for XTTS synthesis.")

        try:
            from TTS.api import TTS
        except Exception as exc:
            raise RuntimeError(
                "XTTS provider requested but Coqui TTS is not installed."
            ) from exc

        if self._xtts is None:
            self._xtts = TTS(self.settings.xtts_model_name).to(self.settings.xtts_device)

        speaker_wav = self.voice_catalog.resolve_xtts_reference(speaker_id)
        self._xtts.tts_to_file(
            text=text,
            speaker_wav=str(speaker_wav),
            language="de",
            file_path=str(output_path),
        )

    @staticmethod
    def _synthesize_edge(text: str, output_path: Path, voice: str | None, rate: int) -> None:
        chosen_voice = voice or "de-DE-KatjaNeural"
        cmd = [
            "edge-tts",
            "--voice",
            chosen_voice,
            "--rate",
            f"{rate:+d}%",
            "--text",
            text,
            "--write-media",
            str(output_path),
        ]

        process = subprocess.run(cmd, capture_output=True, text=True)
        if process.returncode != 0:
            logger.error("edge-tts stdout:\n%s", process.stdout)
            logger.error("edge-tts stderr:\n%s", process.stderr)
            raise RuntimeError(
                "edge-tts failed. Install it or use tts_provider=edge via Applio fallback."
            )

