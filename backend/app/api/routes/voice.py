from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import (
    get_applio_service,
    get_storage_service,
    get_voice_catalog_service,
)
from app.api.schemas import ConvertResponse
from app.services.applio_service import ApplioService
from app.services.storage_service import StorageService
from app.services.voice_catalog import VoiceCatalogService

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/convert", response_model=ConvertResponse)
async def convert_voice(
    audio_file: UploadFile = File(...),
    voice_id: str = Form(...),
    voice_catalog: VoiceCatalogService = Depends(get_voice_catalog_service),
    storage: StorageService = Depends(get_storage_service),
    applio: ApplioService = Depends(get_applio_service),
) -> ConvertResponse:
    try:
        voice_paths = voice_catalog.resolve_voice(voice_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    input_path = await storage.save_upload(audio_file, bucket="input")
    output_path = storage.build_path(bucket="output", suffix=".wav")

    try:
        applio.infer(
            input_path=input_path,
            output_path=output_path,
            pth_path=voice_paths.pth_path,
            index_path=voice_paths.index_path,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ConvertResponse(
        voice_id=voice_id,
        output_audio_url=storage.to_public_url(output_path),
        output_audio_path=str(output_path),
        metadata={"has_index": voice_paths.index_path is not None},
    )

