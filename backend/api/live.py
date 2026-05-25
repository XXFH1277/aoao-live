from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/live")

_state = None


def set_state(state: object) -> None:
    global _state
    _state = state


@router.post("/pause")
async def pause() -> dict:
    await _state.set_running(False)
    return {"ok": True, "running": False}


@router.post("/resume")
async def resume() -> dict:
    await _state.set_running(True)
    return {"ok": True, "running": True}
