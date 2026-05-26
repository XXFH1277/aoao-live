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


class LLMTestRequest(BaseModel):
    prompt: str = "你好，介绍一下你是谁。"
    provider_id: str = ""


@router.put("/provider")
async def update_provider(req: ProviderUpdateRequest) -> dict:
    await _state.update_llm_provider(req.provider_id, req.base_url, req.model, req.api_key)
    return {"ok": True, "provider_id": req.provider_id}


@router.post("/test")
async def test_provider(req: LLMTestRequest) -> dict:
    prompt = req.prompt.strip()
    if not prompt:
        return {"ok": False, "error": "empty_prompt"}
    return await _state.test_llm_provider(prompt, req.provider_id)


@router.get("/status")
async def llm_status() -> dict:
    ollama = await _state.get_ollama_status()
    router_snap = _state.llm_router.router_snapshot()
    return {"ollama": ollama, "llm_router": router_snap}
