from __future__ import annotations

from typing import Any

import aiohttp

from backend.config import INTEGRATIONS_PATH, SECRETS_PATH, load_json, save_json
from backend.core.guardrails import Guardrails
from backend.core.knowledge_base import (
    KnowledgeHit,
    load_guardrails,
    search_knowledge,
    search_knowledge_rag,
)


class LLMRouter:
    def __init__(self, integrations: dict, guardrails: Guardrails) -> None:
        self.integrations = integrations
        self.guardrails = guardrails

    def ollama_config(self) -> dict:
        return self.integrations.get("ollama", {})

    def router_config(self) -> dict:
        return self.integrations.get("llm_router", {"active_provider": "ollama", "providers": {}})

    def active_provider_id(self) -> str:
        return self.router_config().get("active_provider", "ollama")

    def active_provider(self) -> dict:
        router = self.router_config()
        pid = router.get("active_provider", "ollama")
        return router.get("providers", {}).get(pid, router.get("providers", {}).get("ollama", {}))

    def api_key_for(self, provider_id: str) -> str:
        secrets = load_json(SECRETS_PATH)
        return secrets.get("llm_api_keys", {}).get(provider_id, "")

    def router_snapshot(self) -> dict:
        router = self.router_config()
        providers = router.get("providers", {})
        sanitized = {}
        for pid, provider in providers.items():
            sanitized[pid] = {
                "label": provider.get("label", pid),
                "type": provider.get("type", ""),
                "base_url": provider.get("base_url", ""),
                "model": provider.get("model", ""),
                "api_key_required": bool(provider.get("api_key_required", False)),
                "api_key_saved": bool(self.api_key_for(pid)),
            }
        return {"active_provider": router.get("active_provider", "ollama"), "providers": sanitized}

    def update_provider(self, provider_id: str, base_url: str, model: str, api_key: str = "") -> None:
        router = self.integrations.setdefault("llm_router", {"active_provider": "ollama", "providers": {}})
        providers = router.setdefault("providers", {})
        provider = providers.setdefault(provider_id, {"type": "openai_compatible", "label": provider_id})
        if base_url:
            provider["base_url"] = base_url
        if model:
            provider["model"] = model
        router["active_provider"] = provider_id
        if provider_id == "ollama":
            ollama_cfg = self.integrations.setdefault("ollama", {})
            if base_url:
                ollama_cfg["base_url"] = base_url
            if model:
                ollama_cfg["model"] = model
        save_json(INTEGRATIONS_PATH, self.integrations)
        if api_key:
            secrets = load_json(SECRETS_PATH) or {"llm_api_keys": {}}
            secrets.setdefault("llm_api_keys", {})[provider_id] = api_key
            save_json(SECRETS_PATH, secrets)

    async def ollama_status(self) -> dict:
        config = self.ollama_config()
        if not config.get("enabled", False):
            return {"enabled": False, "online": False, "model": config.get("model", "")}
        base_url = config.get("base_url", "http://127.0.0.1:11434").rstrip("/")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    payload = await resp.json()
            model = config.get("model", "")
            names = [item.get("name") for item in payload.get("models", [])]
            return {"enabled": True, "online": True, "model": model, "model_found": model in names}
        except Exception:
            return {"enabled": True, "online": False, "model": config.get("model", ""), "model_found": False}

    def _build_chat_messages(self, danmaku: str, hits: list[KnowledgeHit], persona: dict) -> list[dict]:
        style = persona.get("reply_style", {})
        style_rules = "\n".join(f"- {rule}" for rule in style.get("rules", []))
        knowledge_context = "\n".join(
            f"- [{hit.kind}] {hit.title}: {hit.content}" for hit in hits
        ) or "- 暂无匹配商品知识。"
        guardrail_context = "\n".join(f"- {item}" for item in load_guardrails(limit=12))

        return [
            {
                "role": "system",
                "content": (
                    "你是螯螯，一个舟山本地海鲜/文旅直播间的 AI 数字人主播。"
                    "你必须承认自己是 AI 主播，并且说明有真人助理监管。"
                    f"回答弹幕要像直播间里的人话，最多 {style.get('max_chars', 90)} 个中文字符，最多 {style.get('max_sentences', 3)} 句。"
                    "不要展示思考过程。"
                    "不要承诺最低价、库存、疗效、退款结果、船班天气房态。"
                    "不确定或涉及售后/价格/库存/投诉时，请交给真人助理确认。"
                    "只能基于给定商品知识回答；商品知识没有的信息，不要编造。"
                    "如果命中了商品知识，回答里必须带上至少一个具体注意点，例如规格、重量、发货时间、保存方式、官方公告。"
                    "不要用'作为AI'、'根据资料显示'、'综上'、'建议您'这种模型腔。"
                    f"\n\n说话风格：\n{style_rules}"
                    f"\n\n人设与合规边界：\n{guardrail_context}"
                    f"\n\n商品知识：\n{knowledge_context}"
                ),
            },
            {"role": "user", "content": danmaku},
        ]

    async def _retrieve_knowledge(self, danmaku: str) -> list[KnowledgeHit]:
        config = self.ollama_config()
        base_url = config.get("base_url", "http://127.0.0.1:11434")
        embedding_model = config.get("embedding_model", "nomic-embed-text")
        timeout = int(config.get("timeout_seconds", 20))
        hits = await search_knowledge_rag(danmaku, base_url, embedding_model, limit=5, timeout=min(timeout, 30))
        if not hits:
            hits = search_knowledge(danmaku, limit=5)
        return hits

    async def ask(self, danmaku: str, persona: dict) -> str:
        provider_id = self.active_provider_id()
        provider = self.active_provider()
        if provider.get("type") == "openai_compatible":
            return await self._ask_openai_compatible(danmaku, provider_id, provider, persona)
        return await self._ask_ollama(danmaku, persona)

    async def _ask_ollama(self, danmaku: str, persona: dict) -> str:
        config = self.ollama_config()
        if not config.get("enabled", False):
            return ""
        base_url = config.get("base_url", "http://127.0.0.1:11434").rstrip("/")
        model = config.get("model", "gemma4:e4b")
        timeout = int(config.get("timeout_seconds", 20))
        hits = await self._retrieve_knowledge(danmaku)
        messages = self._build_chat_messages(danmaku, hits, persona)

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "keep_alive": "10m",
            "options": {"temperature": 0.4, "num_predict": 50},
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/api/chat",
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    payload = await resp.json()
            answer = str(payload.get("message", {}).get("content", "")).strip().replace("\n", " ")
            answer = self.guardrails.clean_reply(answer)
            if self.guardrails.scan_warning(answer):
                return ""
            return answer[:160]
        except Exception:
            return ""

    async def _ask_openai_compatible(self, danmaku: str, provider_id: str, provider: dict, persona: dict) -> str:
        base_url = provider.get("base_url", "").rstrip("/")
        model = provider.get("model", "")
        api_key = self.api_key_for(provider_id)
        if not base_url or not model or not api_key:
            return ""

        config = self.ollama_config()
        timeout = int(config.get("timeout_seconds", 20))
        hits = await self._retrieve_knowledge(danmaku)
        messages = self._build_chat_messages(danmaku, hits, persona)

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 120,
            "stream": False,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    payload = await resp.json()
            answer = str(payload.get("choices", [{}])[0].get("message", {}).get("content", "")).strip().replace("\n", " ")
            answer = self.guardrails.clean_reply(answer)
            if self.guardrails.scan_warning(answer):
                return ""
            return answer[:160]
        except Exception:
            return ""
