from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import aiohttp

from backend.config import DB_PATH, PRODUCTS_PATH, PERSONA_PATH, FORBIDDEN_PATH
from backend.utils.text import tokenize


@dataclass
class KnowledgeHit:
    title: str
    kind: str
    content: str
    score: int


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'demo',
                audience TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS knowledge_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                safe_level TEXT NOT NULL DEFAULT 'safe',
                FOREIGN KEY(product_id) REFERENCES products(id)
            );
            CREATE TABLE IF NOT EXISTS guardrails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                content TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS interaction_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                kind TEXT NOT NULL,
                message TEXT NOT NULL,
                reply TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'new'
            );
            CREATE TABLE IF NOT EXISTS knowledge_embeddings (
                knowledge_id INTEGER PRIMARY KEY,
                embedding_json TEXT NOT NULL,
                model TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY(knowledge_id) REFERENCES knowledge_items(id)
            );
            """
        )


def _parse_simple_products_yaml(text: str) -> list[dict]:
    products: list[dict] = []
    current: dict | None = None
    current_list: str | None = None

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.strip() == "products:":
            continue
        if raw_line.startswith("  - id:"):
            if current:
                products.append(current)
            current = {
                "id": raw_line.split(":", 1)[1].strip(),
                "selling_points": [],
                "safe_claims": [],
                "risky_claims": [],
            }
            current_list = None
            continue
        if current is None:
            continue
        stripped = raw_line.strip()
        if stripped.endswith(":") and not stripped.startswith("- "):
            current_list = stripped[:-1]
            current.setdefault(current_list, [])
            continue
        if stripped.startswith("- ") and current_list:
            current[current_list].append(stripped[2:].strip())
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = value.strip()
            current_list = None

    if current:
        products.append(current)
    return products


def rebuild_from_configs() -> None:
    init_db()
    products = _parse_simple_products_yaml(PRODUCTS_PATH.read_text(encoding="utf-8"))
    persona = json.loads(PERSONA_PATH.read_text(encoding="utf-8"))
    forbidden_terms = [
        line.strip()
        for line in FORBIDDEN_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    with _connect() as conn:
        conn.execute("DELETE FROM knowledge_items")
        conn.execute("DELETE FROM products")
        conn.execute("DELETE FROM guardrails")
        conn.execute("DELETE FROM knowledge_embeddings")

        for product in products:
            conn.execute(
                "INSERT INTO products (id, name, status, audience, raw_json) VALUES (?, ?, ?, ?, ?)",
                (
                    product["id"],
                    product.get("name", product["id"]),
                    product.get("status", "demo"),
                    product.get("audience", ""),
                    json.dumps(product, ensure_ascii=False),
                ),
            )
            for kind in ("selling_points", "safe_claims", "risky_claims"):
                safe_level = "risky" if kind == "risky_claims" else "safe"
                for item in product.get(kind, []):
                    conn.execute(
                        "INSERT INTO knowledge_items (product_id, kind, title, content, safe_level) VALUES (?, ?, ?, ?, ?)",
                        (product["id"], kind, product.get("name", product["id"]), item, safe_level),
                    )
            if product.get("audience"):
                conn.execute(
                    "INSERT INTO knowledge_items (product_id, kind, title, content, safe_level) VALUES (?, ?, ?, ?, ?)",
                    (product["id"], "audience", product.get("name", product["id"]), f"适合人群和场景：{product['audience']}", "safe"),
                )

        for claim in persona.get("do_not_claim", []):
            conn.execute("INSERT INTO guardrails (kind, content) VALUES (?, ?)", ("do_not_claim", claim))
        for term in forbidden_terms:
            conn.execute("INSERT INTO guardrails (kind, content) VALUES (?, ?)", ("forbidden_term", term))


def search_knowledge(query: str, limit: int = 5) -> list[KnowledgeHit]:
    init_db()
    tokens = tokenize(query)
    if not tokens:
        return []

    with _connect() as conn:
        rows = conn.execute(
            "SELECT k.kind, k.title, k.content, k.safe_level, p.name AS product_name "
            "FROM knowledge_items k LEFT JOIN products p ON p.id = k.product_id"
        ).fetchall()

    scored: list[KnowledgeHit] = []
    for row in rows:
        haystack = f"{row['kind']} {row['title']} {row['content']} {row['product_name'] or ''}".lower()
        score = sum(1 for token in tokens if token and token.lower() in haystack)
        if row["safe_level"] == "risky" and score > 0:
            score -= 1
        if score > 0:
            scored.append(KnowledgeHit(title=row["title"], kind=row["kind"], content=row["content"], score=score))

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:limit]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


async def _embed_text(text: str, base_url: str, model: str, timeout: int = 30) -> list[float]:
    url = f"{base_url.rstrip('/')}/api/embeddings"
    payload = {"model": model, "prompt": text}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            data = await resp.json()
    return [float(v) for v in data.get("embedding", [])]


async def rebuild_embeddings(base_url: str, model: str, timeout: int = 30) -> int:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, kind, content, safe_level FROM knowledge_items WHERE safe_level != 'risky' ORDER BY id"
        ).fetchall()
        count = 0
        for row in rows:
            text = f"{row['title']} {row['kind']} {row['content']}"
            embedding = await _embed_text(text, base_url, model, timeout)
            conn.execute(
                "INSERT INTO knowledge_embeddings (knowledge_id, embedding_json, model, updated_at) "
                "VALUES (?, ?, ?, datetime('now', 'localtime')) "
                "ON CONFLICT(knowledge_id) DO UPDATE SET embedding_json=excluded.embedding_json, model=excluded.model, updated_at=excluded.updated_at",
                (row["id"], json.dumps(embedding), model),
            )
            count += 1
    return count


async def search_knowledge_rag(query: str, base_url: str, model: str, limit: int = 5, timeout: int = 30) -> list[KnowledgeHit]:
    init_db()
    try:
        query_embedding = await _embed_text(query, base_url, model, timeout)
    except Exception:
        return search_knowledge(query, limit)

    with _connect() as conn:
        rows = conn.execute(
            "SELECT k.kind, k.title, k.content, e.embedding_json "
            "FROM knowledge_embeddings e JOIN knowledge_items k ON k.id = e.knowledge_id WHERE e.model = ?",
            (model,),
        ).fetchall()

    if not rows:
        return search_knowledge(query, limit)

    hits: list[KnowledgeHit] = []
    for row in rows:
        embedding = json.loads(row["embedding_json"])
        score = _cosine_similarity(query_embedding, embedding)
        if score > 0:
            hits.append(KnowledgeHit(title=row["title"], kind=row["kind"], content=row["content"], score=int(score * 10000)))

    hits.sort(key=lambda item: item.score, reverse=True)
    return hits[:limit]


def load_guardrails(limit: int = 20) -> list[str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT content FROM guardrails ORDER BY id LIMIT ?", (limit,)).fetchall()
    return [row["content"] for row in rows]


def list_products() -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT id, name, status, audience FROM products ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def list_knowledge_items(limit: int = 12) -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, product_id, kind, title, content, safe_level FROM knowledge_items ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_knowledge_item(product_id: str, kind: str, title: str, content: str, safe_level: str = "safe") -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO knowledge_items (product_id, kind, title, content, safe_level) VALUES (?, ?, ?, ?, ?)",
            (product_id or None, kind, title, content, safe_level),
        )


def log_interaction(kind: str, message: str, reply: str = "", source: str = "", status: str = "new") -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO interaction_events (kind, message, reply, source, status) VALUES (?, ?, ?, ?, ?)",
            (kind, message, reply, source, status),
        )


def list_interactions(limit: int = 10) -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, kind, message, reply, source, status FROM interaction_events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def stats() -> dict:
    init_db()
    with _connect() as conn:
        product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        knowledge_count = conn.execute("SELECT COUNT(*) FROM knowledge_items").fetchone()[0]
        guardrail_count = conn.execute("SELECT COUNT(*) FROM guardrails").fetchone()[0]
        interaction_count = conn.execute("SELECT COUNT(*) FROM interaction_events").fetchone()[0]
        embedding_count = conn.execute("SELECT COUNT(*) FROM knowledge_embeddings").fetchone()[0]
    return {
        "path": str(DB_PATH),
        "products": product_count,
        "knowledge_items": knowledge_count,
        "guardrails": guardrail_count,
        "interactions": interaction_count,
        "embeddings": embedding_count,
    }
