from fastapi import APIRouter, Depends

from app.api.deps import get_voice_catalog_service
from app.api.schemas import VoicesResponse
from app.services.voice_catalog import VoiceCatalogService

router = APIRouter(prefix="/voices", tags=["voices"])


@router.get("", response_model=VoicesResponse)
def list_voices(
    voice_catalog: VoiceCatalogService = Depends(get_voice_catalog_service),
) -> VoicesResponse:
    return VoicesResponse(voices=voice_catalog.list_voices())

