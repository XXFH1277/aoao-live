from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

_state = None


def set_state(state: object) -> None:
    global _state
    _state = state


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    queue = _state.subscribe()
    snapshot = _state.snapshot()
    snapshot["ollama"] = await _state.get_ollama_status()
    snapshot["llm_router"] = _state.llm_router.router_snapshot()
    await ws.send_json({"event": "state_update", "data": snapshot})
    try:
        send_task = asyncio.create_task(_send_loop(ws, queue))
        recv_task = asyncio.create_task(_recv_loop(ws))
        done, pending = await asyncio.wait(
            {send_task, recv_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        _state.unsubscribe(queue)


async def _send_loop(ws: WebSocket, queue: asyncio.Queue) -> None:
    while True:
        msg = await queue.get()
        await ws.send_json(msg)


async def _recv_loop(ws: WebSocket) -> None:
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = data.get("action", "")
            if action == "danmaku":
                text = data.get("text", "").strip()
                if text:
                    asyncio.create_task(_state.handle_danmaku(text))
            elif action == "assistant_reply":
                text = data.get("text", "").strip()
                if text:
                    asyncio.create_task(_state.handle_assistant_reply(text))
            elif action == "next_line":
                asyncio.create_task(_state.next_line())
            elif action == "pause":
                asyncio.create_task(_state.set_running(False))
            elif action == "resume":
                asyncio.create_task(_state.set_running(True))
    except WebSocketDisconnect:
        return
