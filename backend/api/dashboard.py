from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

_state = None


def set_state(state: object) -> None:
    global _state
    _state = state


@router.get("/state")
async def get_state() -> dict:
    snapshot = _state.snapshot()
    ollama = await _state.get_ollama_status()
    llm_router = _state.llm_router.router_snapshot()
    snapshot["ollama"] = ollama
    snapshot["llm_router"] = llm_router
    return snapshot


@router.post("/script/next")
async def next_line() -> dict:
    await _state.next_line()
    return {"ok": True}
