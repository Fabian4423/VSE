from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.input_dir = settings.storage_root / "input"
        self.intermediate_dir = settings.storage_root / "intermediate"
        self.output_dir = settings.storage_root / "output"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.intermediate_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_path(self, bucket: str, suffix: str) -> Path:
        token = uuid.uuid4().hex
        directory = self.settings.storage_root / bucket
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{token}{suffix}"

    async def save_upload(self, file: UploadFile, bucket: str = "input") -> Path:
        suffix = Path(file.filename or "upload.bin").suffix or ".bin"
        target = self.build_path(bucket=bucket, suffix=suffix)
        content = await file.read()
        target.write_bytes(content)
        return target

    def to_public_url(self, absolute_path: Path) -> str:
        rel = absolute_path.resolve().relative_to(self.settings.storage_root.resolve())
        return f"/storage/{rel.as_posix()}"

