from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.applio_service import ApplioService
from app.services.llm_service import LLMService
from app.services.storage_service import StorageService
from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from app.services.voice_catalog import VoiceCatalogService


@lru_cache(maxsize=1)
def get_voice_catalog_service() -> VoiceCatalogService:
    return VoiceCatalogService(settings=get_settings())


@lru_cache(maxsize=1)
def get_storage_service() -> StorageService:
    return StorageService(settings=get_settings())


@lru_cache(maxsize=1)
def get_applio_service() -> ApplioService:
    return ApplioService(settings=get_settings())


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    return LLMService(settings=get_settings())


@lru_cache(maxsize=1)
def get_stt_service() -> STTService:
    return STTService(settings=get_settings())


@lru_cache(maxsize=1)
def get_tts_service() -> TTSService:
    return TTSService(settings=get_settings(), voice_catalog=get_voice_catalog_service())


def settings_dependency() -> Settings:
    return get_settings()

