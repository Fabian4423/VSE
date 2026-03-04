from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import (
    get_applio_service,
    get_llm_service,
    get_settings,
    get_storage_service,
    get_stt_service,
    get_tts_service,
    get_voice_catalog_service,
)
from app.api.schemas import AssistantResponse
from app.core.config import Settings
from app.services.applio_service import ApplioService
from app.services.llm_service import LLMService
from app.services.storage_service import StorageService
from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from app.services.voice_catalog import VoiceCatalogService

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/respond", response_model=AssistantResponse)
async def respond(
    voice_id: str = Form(...),
    text: str | None = Form(default=None),
    audio_file: UploadFile | None = File(default=None),
    tts_provider: str | None = Form(default=None),
    tts_voice: str = Form(default="de-DE-KatjaNeural"),
    tts_rate: int = Form(default=0),
    settings: Settings = Depends(get_settings),
    voice_catalog: VoiceCatalogService = Depends(get_voice_catalog_service),
    storage: StorageService = Depends(get_storage_service),
    stt: STTService = Depends(get_stt_service),
    llm: LLMService = Depends(get_llm_service),
    tts: TTSService = Depends(get_tts_service),
    applio: ApplioService = Depends(get_applio_service),
) -> AssistantResponse:
    provider = (tts_provider or settings.tts_provider).lower()

    try:
        voice_paths = voice_catalog.resolve_voice(voice_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    input_text = (text or "").strip()
    transcript = None

    if audio_file is not None:
        input_path = await storage.save_upload(audio_file, bucket="input")
        try:
            transcript = stt.transcribe(input_path)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"STT failed: {exc}",
            ) from exc
        input_text = transcript

    if not input_text:
        raise HTTPException(status_code=422, detail="Provide either text or audio_file.")

    response_text = llm.generate_reply(input_text)

    output_tts_path = storage.build_path(bucket="intermediate", suffix=".wav")
    output_rvc_path = storage.build_path(bucket="output", suffix=".wav")

    try:
        if provider == "edge":
            # Fast path: Applio can do TTS + RVC in one command.
            applio.tts_and_infer(
                text=response_text,
                tts_voice=tts_voice,
                tts_rate=tts_rate,
                output_tts_path=output_tts_path,
                output_rvc_path=output_rvc_path,
                pth_path=voice_paths.pth_path,
                index_path=voice_paths.index_path,
            )
        else:
            tts.synthesize(
                text=response_text,
                output_path=output_tts_path,
                provider=provider,
                voice=tts_voice,
                speaker_id=voice_id,
                rate=tts_rate,
            )
            applio.infer(
                input_path=output_tts_path,
                output_path=output_rvc_path,
                pth_path=voice_paths.pth_path,
                index_path=voice_paths.index_path,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    metadata = {
        "tts_provider": provider,
        "has_index": voice_paths.index_path is not None,
    }
    if transcript:
        metadata["transcript"] = transcript

    return AssistantResponse(
        input_text=input_text,
        response_text=response_text,
        voice_id=voice_id,
        output_audio_url=storage.to_public_url(output_rvc_path),
        output_audio_path=str(output_rvc_path),
        metadata=metadata,
    )

