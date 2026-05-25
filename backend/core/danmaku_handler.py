from __future__ import annotations

from backend.core.guardrails import Guardrails
from backend.core.llm_router import LLMRouter


class DanmakuHandler:
    def __init__(self, persona: dict, guardrails: Guardrails, llm_router: LLMRouter) -> None:
        self.persona = persona
        self.guardrails = guardrails
        self.llm_router = llm_router

    async def answer(self, text: str) -> tuple[str, str]:
        lowered = text.lower()

        if any(term in text for term in ["真人", "是不是人", "AI", "ai", "数字人"]):
            return "我是 AI 数字人主播螯螯，本直播间有真人助理实时监管。", "rule"

        if any(term in text for term in ["退", "退款", "售后", "坏了", "赔"]):
            return self.persona.get("assistant_policy", {}).get(
                "handoff_phrase", "这个问题我请真人助理帮你确认，避免说错。"
            ), "handoff"

        if any(term in text for term in ["多少钱", "价格", "库存", "发货"]):
            return "价格、库存和发货时间请以商品页和真人助理确认为准，螯螯不乱承诺。", "rule"

        if "关注" in text:
            return "谢谢关注螯螯，后面会继续测试 AI 主播讲解和真人助理接管。", "rule"

        if lowered.strip() in {"hi", "hello"} or "你好" in text:
            return "你好呀，螯螯在这里。本直播间是 AI 主播加真人助理监管。", "rule"

        answer = await self.llm_router.ask(text, self.persona)
        if answer:
            return answer, self.llm_router.active_provider_id()

        return "这个问题我先记下来，请真人助理确认后再回复，避免说错。", "fallback"
