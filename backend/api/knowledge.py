from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.core.knowledge_base import add_knowledge_item, log_interaction

router = APIRouter(prefix="/api/v1/knowledge")

_state = None


def set_state(state: object) -> None:
    global _state
    _state = state


class KnowledgeAddRequest(BaseModel):
    product_id: str = ""
    kind: str = "safe_claims"
    title: str = "临时知识"
    text: str
    safe_level: str = "safe"


@router.post("")
async def add_item(req: KnowledgeAddRequest) -> dict:
    if not req.text.strip():
        return {"ok": False, "error": "empty text"}
    add_knowledge_item(req.product_id, req.kind, req.title, req.text.strip(), req.safe_level)
    return {"ok": True}


@router.post("/rag/rebuild")
async def rebuild_rag() -> dict:
    try:
        count = await _state.rebuild_rag_index()
        return {"ok": True, "count": count}
    except Exception as exc:
        log_interaction("system", f"RAG 索引失败：{exc}", "", "rag", "handoff")
        return {"ok": False, "error": str(exc)}
