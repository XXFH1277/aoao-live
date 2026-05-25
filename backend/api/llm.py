from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/llm")

_state = None


def set_state(state: object) -> None:
    global _state
    _state = state


class ProviderUpdateRequest(BaseModel):
    provider_id: str = "ollama"
    base_url: str = ""
    model: str = ""
    api_key: str = ""


@router.put("/provider")
async def update_provider(req: ProviderUpdateRequest) -> dict:
    await _state.update_llm_provider(req.provider_id, req.base_url, req.model, req.api_key)
    return {"ok": True, "provider_id": req.provider_id}


@router.get("/status")
async def llm_status() -> dict:
    ollama = await _state.get_ollama_status()
    router_snap = _state.llm_router.router_snapshot()
    return {"ollama": ollama, "llm_router": router_snap}
