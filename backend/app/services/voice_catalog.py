from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.api.schemas import VoiceItem
from app.core.config import Settings


@dataclass(frozen=True)
class VoicePaths:
    voice_id: str
    pth_path: Path
    index_path: Path | None


class VoiceCatalogService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def list_voices(self) -> list[VoiceItem]:
        root = self.settings.rvc_model_root
        if not root.exists():
            return []

        items: list[VoiceItem] = []
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            voice_id = entry.name
            pth = self._resolve_model_path(entry)
            index = self._resolve_index_path(entry)
            meta = self._load_meta(entry / "meta.json")
            xtts_dir = self.settings.xtts_speaker_root / voice_id

            items.append(
                VoiceItem(
                    voice_id=voice_id,
                    has_model=pth is not None,
                    model_path=str(pth) if pth else None,
                    has_index=index is not None,
                    index_path=str(index) if index else None,
                    xtts_speaker_available=xtts_dir.exists(),
                    meta=meta,
                )
            )

        return items

    def resolve_voice(self, voice_id: str) -> VoicePaths:
        voice_dir = self.settings.rvc_model_root / voice_id
        if not voice_dir.exists():
            raise ValueError(f"Unknown voice_id '{voice_id}'.")

        pth_path = self._resolve_model_path(voice_dir)
        if pth_path is None:
            raise ValueError(
                f"Voice '{voice_id}' has no .pth model. "
                f"Expected {voice_dir / 'model.pth'} or any .pth file."
            )

        return VoicePaths(
            voice_id=voice_id,
            pth_path=pth_path,
            index_path=self._resolve_index_path(voice_dir),
        )

    def resolve_xtts_reference(self, speaker_id: str) -> Path:
        speaker_dir = self.settings.xtts_speaker_root / speaker_id
        if not speaker_dir.exists():
            raise ValueError(
                f"No XTTS speaker profile for '{speaker_id}' under {speaker_dir}."
            )

        reference = speaker_dir / "reference.wav"
        if reference.exists():
            return reference

        wav_files = sorted(speaker_dir.glob("*.wav"))
        if not wav_files:
            raise ValueError(
                f"XTTS speaker '{speaker_id}' has no reference .wav file."
            )
        return wav_files[0]

    @staticmethod
    def _resolve_model_path(voice_dir: Path) -> Path | None:
        default = voice_dir / "model.pth"
        if default.exists():
            return default
        pth_files = sorted(voice_dir.glob("*.pth"))
        return pth_files[0] if pth_files else None

    @staticmethod
    def _resolve_index_path(voice_dir: Path) -> Path | None:
        default = voice_dir / "model.index"
        if default.exists():
            return default
        idx_files = sorted(voice_dir.glob("*.index"))
        return idx_files[0] if idx_files else None

    @staticmethod
    def _load_meta(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

