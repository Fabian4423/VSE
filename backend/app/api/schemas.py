from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VoiceItem(BaseModel):
    voice_id: str
    has_model: bool
    model_path: str | None = None
    has_index: bool
    index_path: str | None = None
    xtts_speaker_available: bool
    meta: dict[str, Any] = Field(default_factory=dict)


class VoicesResponse(BaseModel):
    voices: list[VoiceItem]


class ConvertResponse(BaseModel):
    voice_id: str
    output_audio_url: str
    output_audio_path: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssistantResponse(BaseModel):
    input_text: str
    response_text: str
    voice_id: str
    output_audio_url: str
    output_audio_path: str
    metadata: dict[str, Any] = Field(default_factory=dict)

