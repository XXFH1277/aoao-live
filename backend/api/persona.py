from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/persona")

_state = None


def set_state(state: object) -> None:
    global _state
    _state = state


class PersonaUpdateRequest(BaseModel):
    positioning: str = ""
    tone: str = ""
    rules: str = ""
    max_chars: str = "90"
    max_sentences: str = "3"


@router.get("")
async def get_persona() -> dict:
    return _state.persona


@router.put("")
async def update_persona(req: PersonaUpdateRequest) -> dict:
    await _state.update_persona(req.positioning, req.tone, req.rules, req.max_chars, req.max_sentences)
    return {"ok": True}
