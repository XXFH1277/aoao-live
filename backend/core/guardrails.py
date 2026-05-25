from __future__ import annotations

from backend.config import FORBIDDEN_PATH, load_lines


_REPLY_REPLACEMENTS = {
    "您好呀，": "",
    "您好，": "",
    "宝子": "朋友",
    "亲亲": "朋友",
    "根据资料显示，": "",
    "根据商品知识，": "",
    "作为AI主播，": "",
    "作为 AI 主播，": "",
    "综上，": "",
    "建议您": "建议你",
}


class Guardrails:
    def __init__(self) -> None:
        self.forbidden_terms: list[str] = load_lines(FORBIDDEN_PATH)

    def reload(self) -> None:
        self.forbidden_terms = load_lines(FORBIDDEN_PATH)

    def scan_warning(self, text: str) -> str:
        hits = [term for term in self.forbidden_terms if term and term in text]
        return "命中禁忌词：" + "、".join(hits) if hits else ""

    def clean_reply(self, answer: str) -> str:
        cleaned = answer.strip().strip('“”"')
        for old, new in _REPLY_REPLACEMENTS.items():
            cleaned = cleaned.replace(old, new)
        return cleaned.strip()

    def is_safe(self, text: str) -> bool:
        return not self.scan_warning(text)
