from __future__ import annotations

import asyncio
import time
from typing import Any

from backend.config import (
    INTEGRATIONS_PATH,
    PERSONA_PATH,
    load_json,
    save_json,
)
from backend.core.danmaku_handler import DanmakuHandler
from backend.core.guardrails import Guardrails
from backend.core.knowledge_base import (
    list_interactions,
    list_knowledge_items,
    list_products,
    log_interaction,
    rebuild_embeddings,
    rebuild_from_configs,
    stats as kb_stats,
)
from backend.core.llm_router import LLMRouter
from backend.core.scheduler import ScriptScheduler
from backend.services.tts import TTSService


class LiveState:
    def __init__(self) -> None:
        self.persona: dict = load_json(PERSONA_PATH)
        self.integrations: dict = load_json(INTEGRATIONS_PATH)
        rebuild_from_configs()

        self.guardrails = Guardrails()
        self.llm_router = LLMRouter(self.integrations, self.guardrails)
        self.tts_service = TTSService(self.integrations)
        self.scheduler = ScriptScheduler()
        self.danmaku_handler = DanmakuHandler(self.persona, self.guardrails, self.llm_router)

        self.running: bool = True
        self.current_line: str = self.persona.get("compliance_opening", "")
        self.last_danmaku: str = ""
        self.assistant_reply: str = ""
        self.last_reply_source: str = "script"
        self.warning: str = ""
        self.started_at: float = time.time()
        self.updated_at: float = time.time()

        self._lock = asyncio.Lock()
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers = [s for s in self._subscribers if s is not q]

    async def _broadcast(self, event: str, data: dict | None = None) -> None:
        msg = {"event": event, "data": data or self.snapshot()}
        for q in self._subscribers:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    def snapshot(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "index": self.scheduler.current_position(),
            "current_line": self.current_line,
            "last_danmaku": self.last_danmaku,
            "assistant_reply": self.assistant_reply,
            "last_reply_source": self.last_reply_source,
            "warning": self.warning,
            "visible_label": self.persona.get("visible_label", "AI 主播 / AI 生成"),
            "knowledge": kb_stats(),
            "products": list_products(),
            "knowledge_items": list_knowledge_items(),
            "interactions": list_interactions(),
            "uptime_seconds": int(time.time() - self.started_at),
            "updated_at": self.updated_at,
        }

    @property
    def tts_enabled(self) -> bool:
        """TTS is enabled when active provider is configured and not placeholder status."""
        cfg = self.tts_service.config()
        return cfg.get("status") != "disabled"

    async def _auto_tts(self, text: str) -> None:
        """Fire-and-forget TTS for the current line, broadcast audio_url if successful."""
        if not self.tts_enabled or not text.strip():
            return
        try:
            result = await self.tts_service.speak(text)
            if result.get("ok") and result.get("audio_url"):
                await self._broadcast("tts_audio", {
                    "audio_url": result["audio_url"],
                    "text": text,
                    "provider": result.get("provider", ""),
                })
        except Exception:
            pass  # TTS failure should not break the main loop

    async def next_line(self) -> None:
        async with self._lock:
            line = self.scheduler.next_line()
            if line is None:
                if not self.scheduler.script_lines:
                    self.current_line = "话术池为空，请检查 scripts/aoao_mainline.txt。"
                    self.warning = "script_empty"
                return
            self.current_line = line
            self.assistant_reply = ""
            self.last_reply_source = "script"
            self.warning = self.guardrails.scan_warning(line)
            self.updated_at = time.time()
        await self._broadcast("state_update")
        await self._auto_tts(line)

    async def set_running(self, value: bool) -> None:
        async with self._lock:
            self.running = value
            self.updated_at = time.time()
        await self._broadcast("state_update")

    async def handle_danmaku(self, text: str) -> None:
        answer, source = await self.danmaku_handler.answer(text)
        status = "handoff" if source == "handoff" else "answered"
        log_interaction("danmaku", text, answer, source, status)
        async with self._lock:
            self.last_danmaku = text
            self.current_line = answer
            self.assistant_reply = ""
            self.last_reply_source = source
            self.warning = self.guardrails.scan_warning(answer)
            self.scheduler.hold(12)
            self.updated_at = time.time()
        await self._broadcast("danmaku_reply", {"question": text, "answer": answer, "source": source})
        if source != "handoff":
            await self._auto_tts(answer)

    async def handle_assistant_reply(self, text: str) -> None:
        log_interaction("assistant", text, f"真人助理接管：{text}", "human", "handled")
        async with self._lock:
            self.assistant_reply = text
            self.current_line = f"真人助理接管：{text}"
            self.last_reply_source = "human"
            self.warning = self.guardrails.scan_warning(text)
            self.scheduler.hold(18)
            self.updated_at = time.time()
        await self._broadcast("state_update")
        await self._auto_tts(text)

    async def update_llm_provider(self, provider_id: str, base_url: str, model: str, api_key: str = "") -> None:
        self.llm_router.update_provider(provider_id, base_url, model, api_key)
        log_interaction("system", f"模型供应商已切换：{provider_id} / {model or '沿用原模型'}", "", "model", "handled")

    async def test_llm_provider(self, prompt: str, provider_id: str = "") -> dict:
        result = await self.llm_router.test_provider(prompt, self.persona, provider_id)
        status = "handled" if result.get("ok") else "handoff"
        log_interaction("llm_test", prompt, result.get("answer", result.get("error", "")), result.get("provider_id", ""), status)
        return result

    async def update_persona(self, positioning: str, tone: str, rules_text: str, max_chars: str, max_sentences: str) -> None:
        if positioning:
            self.persona["positioning"] = positioning
        if tone:
            self.persona.setdefault("voice_style", {})["tone"] = tone
        reply_style = self.persona.setdefault("reply_style", {})
        rules = [line.strip(" -\t") for line in rules_text.splitlines() if line.strip(" -\t")]
        if rules:
            reply_style["rules"] = rules
        try:
            reply_style["max_chars"] = max(40, min(180, int(max_chars)))
        except ValueError:
            pass
        try:
            reply_style["max_sentences"] = max(1, min(5, int(max_sentences)))
        except ValueError:
            pass
        save_json(PERSONA_PATH, self.persona)
        log_interaction("system", "数字人人设已更新", "", "persona", "handled")

    async def rebuild_rag_index(self) -> int:
        config = self.llm_router.ollama_config()
        base_url = config.get("base_url", "http://127.0.0.1:11434")
        model = config.get("embedding_model", "nomic-embed-text")
        count = await rebuild_embeddings(base_url, model, timeout=60)
        log_interaction("system", f"RAG 索引完成：{count} 条", "", "rag", "handled")
        return count

    async def warm_rag_index(self) -> None:
        try:
            await self.rebuild_rag_index()
        except Exception as exc:
            log_interaction("system", f"RAG 启动预热失败：{exc}", "", "rag", "handoff")
        await self._broadcast("state_update")

    async def get_ollama_status(self) -> dict:
        return await self.llm_router.ollama_status()

    def tts_status(self) -> dict:
        return self.tts_service.status()

    def update_tts_config(self, payload: dict) -> dict:
        status = self.tts_service.update_config(payload)
        log_interaction("system", f"TTS 配置已更新：{status.get('active_provider', '')}", "", "tts", "handled")
        return status

    async def speak_tts(
        self,
        text: str,
        provider: str = "",
        voice: str = "",
        rate: int | None = None,
        volume: int | None = None,
    ) -> dict:
        result = await self.tts_service.speak(text, provider, voice, rate, volume)
        status = "handled" if result.get("ok") else "handoff"
        log_interaction("tts", text, result.get("audio_url", result.get("error", "")), result.get("provider", ""), status)
        return result

    async def ticker_loop(self) -> None:
        while True:
            await asyncio.sleep(8)
            if self.running:
                await self.next_line()
