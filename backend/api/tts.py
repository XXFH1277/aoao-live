from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

from backend.config import VOICE_SAMPLES_DIR

router = APIRouter(prefix="/api/v1/tts")

_state = None


def set_state(state: object) -> None:
    global _state
    _state = state


class TTSRequest(BaseModel):
    text: str
    provider: str = ""
    voice: str = ""
    rate: int | None = None
    volume: int | None = None


class TTSConfigRequest(BaseModel):
    provider_id: str = "windows_sapi"
    active_provider: str = "windows_sapi"
    base_url: str = ""
    model: str = ""
    voice: str = ""
    api_key: str = ""
    extra_json: str = ""
    rate: int = 0
    volume: int = 100


@router.get("/status")
async def status() -> dict:
    return _state.tts_status()


@router.put("/config")
async def update_config(req: TTSConfigRequest) -> dict:
    return _state.update_tts_config(req.model_dump())


@router.post("/speak")
async def speak(req: TTSRequest) -> dict:
    return await _state.speak_tts(req.text, req.provider, req.voice, req.rate, req.volume)


@router.post("/cleanup")
async def cleanup() -> dict:
    removed = _state.tts_service.cleanup_old_files()
    return {"removed": removed, "status": _state.tts_status()}


@router.get("/voice-samples")
async def list_voice_samples() -> dict:
    """List all uploaded voice sample files."""
    VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    samples = []
    for f in sorted(VOICE_SAMPLES_DIR.iterdir()):
        if f.suffix.lower() in (".wav", ".mp3", ".ogg", ".flac", ".m4a"):
            samples.append({
                "filename": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "url": f"/media/voice_samples/{f.name}",
            })
    return {"samples": samples}


@router.post("/voice-samples/upload")
async def upload_voice_sample(file: UploadFile = File(...)) -> dict:
    """Upload a reference audio file for voice cloning (GPT-SoVITS)."""
    VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    # Validate file type
    allowed = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".webm"}
    ext = Path(file.filename or "sample.wav").suffix.lower()
    if ext not in allowed:
        return {"ok": False, "error": f"不支持的文件格式: {ext}，请上传 WAV/MP3/OGG/FLAC/M4A"}
    # Validate file size (max 20MB)
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        return {"ok": False, "error": "文件过大（上限20MB）"}
    # Save with original name (sanitized)
    safe_name = f"{Path(file.filename or 'sample').stem}_{uuid.uuid4().hex[:6]}{ext}"
    dest = VOICE_SAMPLES_DIR / safe_name
    dest.write_bytes(content)
    return {
        "ok": True,
        "filename": safe_name,
        "path": str(dest),
        "size": len(content),
        "url": f"/media/voice_samples/{safe_name}",
    }


@router.delete("/voice-samples/{filename}")
async def delete_voice_sample(filename: str) -> dict:
    """Delete a voice sample file."""
    VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    target = VOICE_SAMPLES_DIR / filename
    if not target.exists() or not target.is_relative_to(VOICE_SAMPLES_DIR):
        return {"ok": False, "error": "文件不存在"}
    target.unlink()
    return {"ok": True, "deleted": filename}
