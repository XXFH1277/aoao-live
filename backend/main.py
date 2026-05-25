from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import dashboard, danmaku, knowledge, live, llm, persona, tts, ws
from backend.config import FRONTEND_DIST, HOST, OVERLAY_DIR, PORT, TTS_OUTPUT_DIR, VOICE_SAMPLES_DIR
from backend.core.live_state import LiveState

state = LiveState()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    asyncio.create_task(state.ticker_loop())
    asyncio.create_task(state.warm_rag_index())
    yield


app = FastAPI(title="螯螯直播助理", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (dashboard, danmaku, knowledge, live, llm, persona, tts, ws):
    module.set_state(state)
    app.include_router(module.router)

TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media/tts", StaticFiles(directory=str(TTS_OUTPUT_DIR)), name="tts-media")

VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media/voice_samples", StaticFiles(directory=str(VOICE_SAMPLES_DIR)), name="voice-samples-media")

if OVERLAY_DIR.exists():
    app.mount("/overlay", StaticFiles(directory=str(OVERLAY_DIR), html=True), name="overlay")

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


def main() -> None:
    print(f"螯螯直播助理: http://{HOST}:{PORT}")
    print(f"OBS overlay:   http://{HOST}:{PORT}/overlay")
    print(f"API 文档:      http://{HOST}:{PORT}/docs")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
