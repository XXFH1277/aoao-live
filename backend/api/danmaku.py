from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1")

_state = None


def set_state(state: object) -> None:
    global _state
    _state = state


class DanmakuRequest(BaseModel):
    text: str


class AssistantRequest(BaseModel):
    text: str


@router.post("/danmaku")
async def handle_danmaku(req: DanmakuRequest) -> dict:
    text = req.text.strip()
    if not text:
        return {"ok": False, "error": "empty text"}
    await _state.handle_danmaku(text)
    return {"ok": True}


@router.post("/assistant")
async def handle_assistant(req: AssistantRequest) -> dict:
    text = req.text.strip()
    if not text:
        return {"ok": False, "error": "empty text"}
    await _state.handle_assistant_reply(text)
    return {"ok": True}
