from __future__ import annotations

import html
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib import error, request

from knowledge_base import (
    add_knowledge_item,
    list_interactions,
    list_knowledge_items,
    list_products,
    load_guardrails,
    log_interaction,
    rebuild_from_configs,
    rebuild_embeddings,
    search_knowledge,
    search_knowledge_rag,
    stats as kb_stats,
)


ROOT = Path(__file__).resolve().parents[1]
PERSONA_PATH = ROOT / "configs" / "persona.json"
SCRIPT_PATH = ROOT / "scripts" / "aoao_mainline.txt"
FORBIDDEN_PATH = ROOT / "configs" / "forbidden_terms.txt"
INTEGRATIONS_PATH = ROOT / "configs" / "integrations.json"
SECRETS_PATH = ROOT / "configs" / "secrets.local.json"


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class LiveState:
    def __init__(self) -> None:
        self.persona = load_json(PERSONA_PATH)
        self.integrations = load_json(INTEGRATIONS_PATH)
        rebuild_from_configs()
        self.rebuild_rag_index()
        self.script_lines = load_lines(SCRIPT_PATH)
        self.forbidden_terms = load_lines(FORBIDDEN_PATH)
        self.lock = threading.Lock()
        self.running = True
        self.index = 0
        self.current_line = self.persona.get("compliance_opening", "")
        self.last_danmaku = ""
        self.assistant_reply = ""
        self.last_reply_source = "script"
        self.warning = ""
        self.started_at = time.time()
        self.updated_at = time.time()
        self.hold_until = 0.0

    def rebuild_rag_index(self) -> None:
        config = self.integrations.get("ollama", {})
        if not config.get("enabled", False):
            return
        base_url = config.get("base_url", "http://127.0.0.1:11434")
        model = config.get("embedding_model", "nomic-embed-text")
        try:
            rebuild_embeddings(base_url, model, timeout=60)
        except Exception:
            pass

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "running": self.running,
                "index": self.index,
                "current_line": self.current_line,
                "last_danmaku": self.last_danmaku,
                "assistant_reply": self.assistant_reply,
                "last_reply_source": self.last_reply_source,
                "warning": self.warning,
                "visible_label": self.persona.get("visible_label", "AI 主播 / AI 生成"),
                "ollama": self.ollama_status(),
                "llm_router": self.llm_router_snapshot(),
                "knowledge": kb_stats(),
                "products": list_products(),
                "knowledge_items": list_knowledge_items(),
                "interactions": list_interactions(),
                "uptime_seconds": int(time.time() - self.started_at),
                "updated_at": self.updated_at,
            }

    def next_line(self) -> None:
        with self.lock:
            if time.time() < self.hold_until:
                return
            if not self.script_lines:
                self.current_line = "话术池为空，请检查 scripts/aoao_mainline.txt。"
                self.warning = "script_empty"
                return
            self.current_line = self.script_lines[self.index % len(self.script_lines)]
            self.index += 1
            self.assistant_reply = ""
            self.last_reply_source = "script"
            self.warning = self.scan_warning(self.current_line)
            self.updated_at = time.time()

    def set_running(self, value: bool) -> None:
        with self.lock:
            self.running = value
            self.updated_at = time.time()

    def set_danmaku(self, text: str) -> None:
        answer, source = self.answer_danmaku(text)
        status = "handoff" if source == "handoff" else "answered"
        log_interaction("danmaku", text, answer, source, status)
        with self.lock:
            self.last_danmaku = text
            self.current_line = answer
            self.assistant_reply = ""
            self.last_reply_source = source
            self.warning = self.scan_warning(answer)
            self.hold_until = time.time() + 12
            self.updated_at = time.time()

    def set_assistant_reply(self, text: str) -> None:
        log_interaction("assistant", text, f"真人助理接管：{text}", "human", "handled")
        with self.lock:
            self.assistant_reply = text
            self.current_line = f"真人助理接管：{text}"
            self.last_reply_source = "human"
            self.warning = self.scan_warning(text)
            self.hold_until = time.time() + 18
            self.updated_at = time.time()

    def answer_danmaku(self, text: str) -> tuple[str, str]:
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
        answer = self.ask_ollama(text)
        if answer:
            return answer, self.active_provider_id()
        return "这个问题我先记下来，请真人助理确认后再回复，避免说错。", "fallback"

    def scan_warning(self, text: str) -> str:
        hits = [term for term in self.forbidden_terms if term and term in text]
        return "命中禁忌词：" + "、".join(hits) if hits else ""

    def ollama_config(self) -> dict:
        return self.integrations.get("ollama", {})

    def llm_router_config(self) -> dict:
        return self.integrations.get("llm_router", {"active_provider": "ollama", "providers": {}})

    def active_provider_id(self) -> str:
        return self.llm_router_config().get("active_provider", "ollama")

    def active_provider(self) -> dict:
        router = self.llm_router_config()
        provider_id = router.get("active_provider", "ollama")
        return router.get("providers", {}).get(provider_id, router.get("providers", {}).get("ollama", {}))

    def api_key_for(self, provider_id: str) -> str:
        secrets = load_json(SECRETS_PATH)
        return secrets.get("llm_api_keys", {}).get(provider_id, "")

    def llm_router_snapshot(self) -> dict:
        router = self.llm_router_config()
        providers = router.get("providers", {})
        sanitized = {}
        for provider_id, provider in providers.items():
            sanitized[provider_id] = {
                "label": provider.get("label", provider_id),
                "type": provider.get("type", ""),
                "base_url": provider.get("base_url", ""),
                "model": provider.get("model", ""),
                "api_key_required": bool(provider.get("api_key_required", False)),
                "api_key_saved": bool(self.api_key_for(provider_id)),
            }
        return {
            "active_provider": router.get("active_provider", "ollama"),
            "providers": sanitized,
        }

    def update_llm_provider(self, provider_id: str, base_url: str, model: str, api_key: str = "") -> None:
        router = self.integrations.setdefault("llm_router", {"active_provider": "ollama", "providers": {}})
        providers = router.setdefault("providers", {})
        provider = providers.setdefault(provider_id, {"type": "openai_compatible", "label": provider_id})
        if base_url:
            provider["base_url"] = base_url
        if model:
            provider["model"] = model
        router["active_provider"] = provider_id
        if provider_id == "ollama":
            ollama_config = self.integrations.setdefault("ollama", {})
            if base_url:
                ollama_config["base_url"] = base_url
            if model:
                ollama_config["model"] = model
        save_json(INTEGRATIONS_PATH, self.integrations)

        if api_key:
            secrets = load_json(SECRETS_PATH) or {"llm_api_keys": {}}
            secrets.setdefault("llm_api_keys", {})[provider_id] = api_key
            save_json(SECRETS_PATH, secrets)

    def update_persona(self, positioning: str, tone: str, rules_text: str, max_chars: str, max_sentences: str) -> None:
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

    def ollama_status(self) -> dict:
        config = self.ollama_config()
        if not config.get("enabled", False):
            return {"enabled": False, "online": False, "model": config.get("model", "")}
        base_url = config.get("base_url", "http://127.0.0.1:11434").rstrip("/")
        try:
            with request.urlopen(f"{base_url}/api/tags", timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            model = config.get("model", "")
            names = [item.get("name") for item in payload.get("models", [])]
            return {"enabled": True, "online": True, "model": model, "model_found": model in names}
        except Exception:
            return {"enabled": True, "online": False, "model": config.get("model", ""), "model_found": False}

    def ask_ollama(self, danmaku: str) -> str:
        provider_id = self.active_provider_id()
        provider = self.active_provider()
        if provider.get("type") == "openai_compatible":
            return self.ask_openai_compatible(danmaku, provider_id, provider)

        config = self.ollama_config()
        if not config.get("enabled", False):
            return ""
        base_url = config.get("base_url", "http://127.0.0.1:11434").rstrip("/")
        model = config.get("model", "gemma4:e4b")
        embedding_model = config.get("embedding_model", "nomic-embed-text")
        timeout = int(config.get("timeout_seconds", 20))
        hits = search_knowledge_rag(danmaku, base_url, embedding_model, limit=5, timeout=min(timeout, 30))
        if not hits:
            hits = search_knowledge(danmaku, limit=5)
        style = self.persona.get("reply_style", {})
        style_rules = "\n".join(f"- {rule}" for rule in style.get("rules", []))
        messages = self.build_chat_messages(danmaku, hits)

        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "keep_alive": "10m",
            "options": {
                "temperature": 0.4,
                "num_predict": 50
            }
        }
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        try:
            req = request.Request(
                f"{base_url}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            answer = str(payload.get("message", {}).get("content", "")).strip().replace("\n", " ")
            answer = self.clean_reply(answer)
            if self.scan_warning(answer):
                return ""
            return answer[:160]
        except (error.URLError, TimeoutError, json.JSONDecodeError):
            return ""

    def build_chat_messages(self, danmaku: str, hits: list) -> list[dict]:
        style = self.persona.get("reply_style", {})
        style_rules = "\n".join(f"- {rule}" for rule in style.get("rules", []))
        knowledge_context = "\n".join(
            f"- [{hit.kind}] {hit.title}: {hit.content}"
            for hit in hits
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

    def ask_openai_compatible(self, danmaku: str, provider_id: str, provider: dict) -> str:
        config = self.ollama_config()
        base_url = provider.get("base_url", "").rstrip("/")
        model = provider.get("model", "")
        api_key = self.api_key_for(provider_id)
        if not base_url or not model or not api_key:
            return ""

        embedding_model = config.get("embedding_model", "nomic-embed-text")
        timeout = int(config.get("timeout_seconds", 20))
        hits = search_knowledge_rag(danmaku, config.get("base_url", "http://127.0.0.1:11434"), embedding_model, limit=5, timeout=min(timeout, 30))
        if not hits:
            hits = search_knowledge(danmaku, limit=5)
        messages = self.build_chat_messages(danmaku, hits)
        body = {
            "model": model,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 120,
            "stream": False,
        }
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        try:
            req = request.Request(
                f"{base_url}/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with request.urlopen(req, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            answer = str(payload.get("choices", [{}])[0].get("message", {}).get("content", "")).strip().replace("\n", " ")
            answer = self.clean_reply(answer)
            if self.scan_warning(answer):
                return ""
            return answer[:160]
        except (error.URLError, TimeoutError, json.JSONDecodeError):
            return ""

    def clean_reply(self, answer: str) -> str:
        replacements = {
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
        cleaned = answer.strip().strip("“”\"")
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)
        return cleaned.strip()


STATE = LiveState()


def ticker() -> None:
    while True:
        time.sleep(8)
        if STATE.snapshot()["running"]:
            STATE.next_line()


class Handler(BaseHTTPRequestHandler):
    server_version = "AoaoLiveConsole/0.1"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self.send_html(self.dashboard_html())
        elif path == "/overlay":
            self.send_html(self.overlay_html())
        elif path == "/obs.js":
            self.send_javascript(self.obs_js())
        elif path == "/api/state":
            self.send_json(STATE.snapshot())
        elif path == "/api/next":
            STATE.next_line()
            self.redirect("/")
        elif path == "/api/pause":
            STATE.set_running(False)
            self.redirect("/")
        elif path == "/api/resume":
            STATE.set_running(True)
            self.redirect("/")
        else:
            self.send_error(404, "Not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        form = parse_qs(body)
        text = form.get("text", [""])[0].strip()
        if path == "/api/danmaku":
            if text:
                STATE.set_danmaku(text)
            self.redirect("/")
        elif path == "/api/assistant":
            if text:
                STATE.set_assistant_reply(text)
            self.redirect("/")
        elif path == "/api/knowledge/add":
            product_id = form.get("product_id", [""])[0].strip()
            title = form.get("title", [""])[0].strip() or "临时知识"
            kind = form.get("kind", ["safe_claims"])[0].strip()
            safe_level = form.get("safe_level", ["safe"])[0].strip()
            if text:
                add_knowledge_item(product_id, kind, title, text, safe_level)
            self.redirect("/#knowledge")
        elif path == "/api/rag/rebuild":
            config = STATE.ollama_config()
            base_url = config.get("base_url", "http://127.0.0.1:11434")
            model = config.get("embedding_model", "nomic-embed-text")
            try:
                count = rebuild_embeddings(base_url, model, timeout=60)
                log_interaction("system", f"RAG 索引完成：{count} 条", "", "rag", "handled")
            except Exception as exc:
                log_interaction("system", f"RAG 索引失败：{exc}", "", "rag", "handoff")
            self.redirect("/#knowledge")
        elif path == "/api/model/update":
            provider_id = form.get("provider_id", ["ollama"])[0].strip() or "ollama"
            base_url = form.get("base_url", [""])[0].strip()
            model = form.get("model", [""])[0].strip()
            api_key = form.get("api_key", [""])[0].strip()
            STATE.update_llm_provider(provider_id, base_url, model, api_key)
            log_interaction("system", f"模型供应商已切换：{provider_id} / {model or '沿用原模型'}", "", "model", "handled")
            self.redirect("/#settings")
        elif path == "/api/persona/update":
            positioning = form.get("positioning", [""])[0].strip()
            tone = form.get("tone", [""])[0].strip()
            rules_text = form.get("rules", [""])[0].strip()
            max_chars = form.get("max_chars", ["90"])[0].strip()
            max_sentences = form.get("max_sentences", ["3"])[0].strip()
            STATE.update_persona(positioning, tone, rules_text, max_chars, max_sentences)
            log_interaction("system", "数字人人设已更新", "", "persona", "handled")
            self.redirect("/#digital-human")
        else:
            self.send_error(404, "Not found")

    def dashboard_html(self) -> str:
        state = STATE.snapshot()
        status = "运行中" if state["running"] else "已暂停"
        status_class = "live" if state["running"] else "paused"
        ollama = state["ollama"]
        llm_router = state.get("llm_router", {})
        llm_providers = llm_router.get("providers", {})
        active_provider_id = llm_router.get("active_provider", "ollama")
        active_provider = llm_providers.get(active_provider_id, llm_providers.get("ollama", {}))
        active_provider_label = active_provider.get("label", active_provider_id)
        active_model = active_provider.get("model", ollama.get("model", ""))
        knowledge = state["knowledge"]
        products = state["products"]
        knowledge_items = state["knowledge_items"]
        interactions = state["interactions"]
        ollama_label = "已连接" if ollama.get("online") and ollama.get("model_found") else "待检查"
        ollama_class = "ok" if ollama.get("online") and ollama.get("model_found") else "todo"
        rag_label = f'{knowledge.get("embeddings", 0)} 条索引' if knowledge.get("embeddings", 0) else "未索引"
        rag_class = "ok" if knowledge.get("embeddings", 0) else "todo"
        warning = f'<div class="warning">{html.escape(state["warning"])}</div>' if state["warning"] else ""
        product_options = "".join(
            f'<option value="{html.escape(product["id"])}">{html.escape(product["name"])}</option>'
            for product in products
        )
        knowledge_rows = "".join(
            f"""
            <tr>
              <td>{html.escape(item["title"])}</td>
              <td>{html.escape(item["kind"])}</td>
              <td>{html.escape(item["content"])}</td>
              <td><span class="tag {"no" if item["safe_level"] == "risky" else "ok"}">{html.escape(item["safe_level"])}</span></td>
            </tr>
            """
            for item in knowledge_items
        ) or '<tr><td colspan="4">暂无知识条目</td></tr>'
        interaction_rows = "".join(
            f"""
            <div class="queue-item">
              <div class="queue-head">
                <strong>{html.escape(item["message"])}</strong>
                <span class="tag {"ok" if item["status"] == "answered" else "todo" if item["status"] == "new" else "no" if item["status"] == "handoff" else "ok"}">{html.escape(item["status"])}</span>
              </div>
              <p>{html.escape(item["reply"] or "等待处理")}</p>
              <div class="queue-meta">{html.escape(item["created_at"])} · {html.escape(item["source"] or item["kind"])}</div>
            </div>
            """
            for item in interactions
        ) or '<div class="queue-empty">暂无互动记录</div>'
        persona_rules_text = "\n".join(STATE.persona.get("reply_style", {}).get("rules", []))
        persona_style = STATE.persona.get("reply_style", {})
        persona_voice = STATE.persona.get("voice_style", {})
        provider_options = "".join(
            f'<option value="{html.escape(provider_id)}"{" selected" if provider_id == active_provider_id else ""}>{html.escape(provider.get("label", provider_id))}</option>'
            for provider_id, provider in llm_providers.items()
        )
        provider_chips = "".join(
            f"""
            <div class="provider-chip">
              <div>
                <strong>{html.escape(provider.get("label", provider_id))}</strong>
                <span>{html.escape(provider.get("model", "未配置"))}</span>
              </div>
              <span class="tag {"ok" if provider_id == active_provider_id else "todo"}">{"当前" if provider_id == active_provider_id else "可选"}</span>
            </div>
            """
            for provider_id, provider in llm_providers.items()
        )
        providers_json = json.dumps(llm_providers, ensure_ascii=False).replace("</", "<\\/")
        api_key_status = "本地模型无需密钥"
        api_key_class = "ok"
        if active_provider.get("api_key_required"):
            api_key_status = "密钥已保存" if active_provider.get("api_key_saved") else "等待填写密钥"
            api_key_class = "ok" if active_provider.get("api_key_saved") else "todo"
        provider_type_label = "本地 Ollama" if active_provider.get("type") == "ollama" else "OpenAI 兼容接口"
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>螯螯直播助理控制台</title>
  <style>
    :root {{
      --ink: #17211f;
      --muted: #63716d;
      --line: #dbe3df;
      --paper: #ffffff;
      --wash: #f3f6f4;
      --green: #138a5b;
      --green-soft: #dff5ea;
      --coral: #cf4d32;
      --coral-soft: #fde8df;
      --teal: #0c7c86;
      --teal-soft: #dff3f5;
      --amber: #a66b00;
      --amber-soft: #fff2d8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: #eef3f1;
      color: var(--ink);
      font-family: Arial, "Microsoft YaHei", sans-serif;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      padding: 12px 0 22px;
      border-bottom: 1px solid var(--line);
      margin-bottom: 22px;
    }}
    h1 {{ font-size: 28px; line-height: 1.2; margin: 0; letter-spacing: 0; }}
    .subtitle {{ margin-top: 8px; color: var(--muted); font-size: 14px; }}
    .layout {{ display: grid; grid-template-columns: minmax(0, 1.35fr) 360px; gap: 18px; align-items: start; }}
    .panel {{ background: var(--paper); border: 1px solid var(--line); border-radius: 8px; padding: 18px; margin-bottom: 16px; box-shadow: 0 1px 2px rgba(20, 32, 28, .04); }}
    .hero {{ min-height: 310px; display: flex; flex-direction: column; justify-content: space-between; }}
    .panel-title {{ color: var(--muted); font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0; margin-bottom: 12px; }}
    .status {{ display: inline-flex; align-items: center; gap: 8px; padding: 7px 10px; border-radius: 999px; font-weight: 700; font-size: 13px; }}
    .status.live {{ background: var(--green-soft); color: var(--green); }}
    .status.paused {{ background: var(--coral-soft); color: var(--coral); }}
    .dot {{ width: 8px; height: 8px; border-radius: 50%; background: currentColor; }}
    .line {{ font-size: 30px; line-height: 1.45; margin: 18px 0; max-width: 760px; }}
    .meta-row {{ display: flex; gap: 10px; flex-wrap: wrap; color: var(--muted); font-size: 13px; }}
    .pill {{ display: inline-flex; align-items: center; border: 1px solid var(--line); border-radius: 999px; padding: 6px 9px; background: #fbfcfb; }}
    .warning {{ margin-top: 12px; padding: 12px; background: var(--amber-soft); border: 1px solid #e8c06f; border-radius: 6px; color: var(--amber); font-weight: 700; }}
    .controls {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }}
    a.button, button {{ border: 0; background: var(--teal); color: white; min-height: 42px; padding: 10px 14px; border-radius: 6px; text-decoration: none; cursor: pointer; font-size: 14px; font-weight: 700; text-align: center; }}
    a.secondary {{ background: #53645f; }}
    a.danger {{ background: var(--coral); }}
    form {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; margin-top: 10px; }}
    input {{ min-width: 0; padding: 12px; border: 1px solid #c8d4cf; border-radius: 6px; font-size: 14px; }}
    code {{ background: #edf2ef; padding: 3px 6px; border-radius: 4px; }}
    .stack {{ display: grid; gap: 10px; }}
    .check {{ display: flex; justify-content: space-between; gap: 12px; padding: 11px 0; border-bottom: 1px solid #edf1ef; font-size: 14px; }}
    .check:last-child {{ border-bottom: 0; }}
    .tag {{ flex: none; border-radius: 999px; padding: 4px 8px; font-size: 12px; font-weight: 700; }}
    .tag.ok {{ background: var(--green-soft); color: var(--green); }}
    .tag.todo {{ background: var(--amber-soft); color: var(--amber); }}
    .tag.no {{ background: var(--coral-soft); color: var(--coral); }}
    .small {{ color: var(--muted); font-size: 13px; line-height: 1.5; }}
    .obs-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
    .obs-log {{ min-height: 74px; max-height: 120px; overflow: auto; background: #f7faf8; border: 1px solid var(--line); border-radius: 6px; padding: 10px; color: var(--muted); font-size: 12px; line-height: 1.45; }}
    .app-shell {{ min-height: 100vh; display: grid; grid-template-columns: 212px minmax(0, 1fr); }}
    .sidebar {{ background: #101817; color: #e7f0ed; padding: 18px 14px; display: flex; flex-direction: column; gap: 24px; }}
    .brand {{ display: flex; gap: 12px; align-items: center; padding: 6px; }}
    .brand-mark {{ width: 46px; height: 46px; display: grid; place-items: center; border-radius: 8px; background: #1fa37a; color: #fff; font-weight: 800; font-size: 22px; }}
    .brand strong {{ display: block; font-size: 15px; }}
    .brand span {{ display: block; margin-top: 3px; color: #90a19b; font-size: 12px; }}
    .nav {{ display: grid; gap: 6px; }}
    .nav a {{ display: flex; align-items: center; gap: 10px; min-height: 42px; padding: 0 12px; color: #b9c8c3; text-decoration: none; border-radius: 6px; font-weight: 700; font-size: 14px; }}
    .nav a.active, .nav a:hover {{ background: #1b2826; color: #ffffff; }}
    .nav span {{ width: 18px; text-align: center; color: inherit; }}
    .sidebar-foot {{ margin-top: auto; padding: 12px; border-radius: 8px; background: #182321; color: #91a39d; font-size: 12px; }}
    .sidebar-foot strong {{ display: block; color: #fff; margin-top: 4px; }}
    .workspace {{ max-width: none; margin: 0; padding: 0 0 72px; min-width: 0; }}
    .topbar {{ margin: 0; padding: 22px 30px; background: #f9fbfa; border-bottom: 1px solid var(--line); align-items: center; }}
    .top-actions {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
    .room-grid {{ display: grid; grid-template-columns: repeat(2, minmax(220px, 280px)); gap: 16px; padding: 18px 30px; }}
    .room-card {{ background: #fff; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; box-shadow: 0 8px 22px rgba(29, 44, 39, .06); }}
    .room-card.selected {{ border-color: #a9d2f7; }}
    .room-preview {{ height: 150px; display: grid; place-items: center; background: #f1f5f9; color: #708090; font-size: 24px; font-weight: 800; }}
    .room-preview.muted {{ color: #9aa7b2; font-size: 32px; }}
    .room-body {{ padding: 14px; display: grid; gap: 4px; text-align: center; }}
    .room-body span, .room-meta {{ color: var(--muted); font-size: 12px; }}
    .studio-grid {{ display: grid; grid-template-columns: 320px minmax(0, 1fr) 300px; gap: 16px; padding: 0 30px; align-items: start; }}
    .left-rail, .right-rail {{ display: grid; gap: 14px; }}
    .back {{ color: var(--muted); text-decoration: none; font-size: 13px; }}
    .stage-preview {{ background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .stage-screen {{ position: relative; aspect-ratio: 9 / 14; background: linear-gradient(160deg, #06100e, #0b1d19 55%, #07100e); border-radius: 7px; overflow: hidden; box-shadow: inset 0 0 0 1px rgba(255,255,255,.08); }}
    .stage-screen::before {{ content: ""; position: absolute; left: 19%; right: 19%; top: 18%; height: 44%; border-radius: 48% 48% 42% 42%; background: linear-gradient(#173a33, #0d2722); border: 1px solid rgba(121,218,190,.22); }}
    .stage-screen::after {{ content: "螯螯数字人待接入"; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: rgba(255,255,255,.42); font-weight: 800; }}
    .stage-badge {{ position: absolute; top: 12px; left: 12px; background: rgba(255,255,255,.88); color: #12322f; padding: 5px 8px; border-radius: 5px; font-size: 12px; font-weight: 800; }}
    .stage-caption {{ position: absolute; left: 12px; right: 12px; bottom: 12px; background: rgba(255,255,255,.9); color: #10201e; padding: 10px; border-radius: 6px; font-size: 13px; line-height: 1.45; max-height: 120px; overflow: hidden; }}
    .asset-card {{ background: #f7faf8; border: 1px solid var(--line); border-radius: 8px; padding: 12px; }}
    .asset-row {{ display: flex; justify-content: space-between; padding: 7px 0; border-bottom: 1px solid #e7ece9; font-size: 13px; }}
    .asset-row:last-child {{ border-bottom: 0; }}
    .asset-row span {{ color: var(--muted); }}
    .asset-actions {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .main-panels {{ display: grid; gap: 14px; min-width: 0; }}
    .module {{ background: #fff; border: 1px solid #d8e2de; border-radius: 8px; padding: 16px; box-shadow: 0 8px 24px rgba(18, 31, 27, .05); }}
    .module h2 {{ margin: 0; font-size: 17px; }}
    .module p {{ margin: 6px 0 0; }}
    .module-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 14px; }}
    .success-note {{ background: #e6f6e9; color: #278044; border-radius: 6px; padding: 9px 14px; font-weight: 700; font-size: 13px; }}
    .step-bar {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }}
    .step {{ padding: 9px 13px; border-radius: 6px; background: #eef2f6; color: #66727d; font-size: 13px; font-weight: 800; }}
    .step.done {{ background: #e7f2ff; color: #1d74bd; }}
    .step.active {{ background: #e9f7e7; color: #2e8b44; }}
    .script-card {{ border: 1px solid #e6ece9; border-radius: 8px; padding: 16px; background: #fbfcfb; }}
    .script-title {{ font-weight: 800; margin-bottom: 10px; }}
    .script-text {{ border: 1px solid #cbdceb; background: #fff; border-radius: 6px; padding: 14px; min-height: 150px; max-height: 260px; overflow: auto; line-height: 1.7; color: #394843; }}
    .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    .sub-panel {{ border: 1px solid #e8eeee; border-radius: 8px; padding: 14px; }}
    .metric-row {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 12px 0; }}
    .metric-row div {{ background: #f5f8f7; border-radius: 7px; padding: 12px; }}
    .metric-row strong {{ display: block; font-size: 22px; }}
    .metric-row span {{ color: var(--muted); font-size: 12px; }}
    .data-table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }}
    .data-table th, .data-table td {{ border-bottom: 1px solid #e9eeeb; padding: 10px 8px; text-align: left; vertical-align: top; }}
    .data-table th {{ color: var(--muted); font-size: 12px; background: #f7faf8; }}
    .data-table td:nth-child(3) {{ color: #3b4b47; line-height: 1.45; }}
    .knowledge-form {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }}
    .knowledge-form textarea {{ grid-column: 1 / -1; min-height: 78px; resize: vertical; padding: 12px; border: 1px solid #c8d4cf; border-radius: 6px; font-family: inherit; }}
    .knowledge-form button {{ justify-self: start; }}
    .queue-list {{ display: grid; gap: 10px; margin-top: 12px; }}
    .queue-item {{ border: 1px solid #e6ece9; border-radius: 8px; padding: 12px; background: #fbfcfb; }}
    .queue-head {{ display: flex; justify-content: space-between; gap: 10px; align-items: center; }}
    .queue-item p {{ margin: 8px 0; line-height: 1.5; color: #364642; }}
    .queue-meta, .queue-empty {{ color: var(--muted); font-size: 12px; }}
    .controls.compact {{ display: flex; grid-template-columns: none; }}
    .right-rail .module {{ padding: 14px; }}
    .field-label {{ display: block; margin: 12px 0 6px; color: var(--muted); font-size: 13px; font-weight: 700; }}
    select {{ width: 100%; min-height: 38px; border: 1px solid #c8d4cf; border-radius: 6px; padding: 0 10px; background: #fff; }}
    .launchbar {{ position: fixed; left: 180px; right: 0; bottom: 0; height: 58px; display: flex; align-items: center; gap: 10px; padding: 10px 28px; background: rgba(255,255,255,.96); border-top: 1px solid var(--line); box-shadow: 0 -5px 18px rgba(18, 30, 26, .06); }}
    .launchbar span {{ background: #f2f5f3; border: 1px solid var(--line); border-radius: 6px; padding: 10px 14px; font-weight: 700; }}
    .launchbar input {{ max-width: 280px; }}
    .muted-button {{ background: #f2bd74; }}
    .green-button {{ background: #42a63f; }}
    .section-page {{ padding: 18px 30px; border-top: 1px solid #dfe8e4; }}
    .section-title {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 14px; }}
    .section-title h2 {{ margin: 0; font-size: 22px; }}
    .section-title p {{ margin: 6px 0 0; color: var(--muted); }}
    .flow-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }}
    .flow-card {{ background: #fff; border: 1px solid #d8e2de; border-radius: 8px; padding: 16px; min-height: 170px; }}
    .flow-card h3 {{ margin: 0 0 10px; font-size: 16px; }}
    .settings-grid {{ display: grid; grid-template-columns: minmax(360px, 1.45fr) minmax(260px, .85fr); gap: 14px; align-items: start; }}
    .settings-grid .flow-card {{ min-height: 0; }}
    .provider-summary {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px; border: 1px solid #dce6e2; border-radius: 8px; background: #f7faf8; margin: 10px 0 12px; }}
    .provider-summary strong {{ display: block; font-size: 15px; }}
    .provider-summary span {{ display: block; margin-top: 3px; color: var(--muted); font-size: 12px; }}
    form.model-form {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 0; }}
    .form-field {{ display: grid; gap: 6px; }}
    .form-field.full {{ grid-column: 1 / -1; }}
    .form-field label {{ color: var(--muted); font-size: 12px; font-weight: 800; }}
    .model-form input, .model-form select {{ width: 100%; }}
    .form-actions {{ grid-column: 1 / -1; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
    .form-actions button {{ width: auto; }}
    .provider-list {{ display: grid; gap: 8px; margin-top: 10px; }}
    .provider-chip {{ display: flex; justify-content: space-between; gap: 10px; align-items: center; padding: 10px 11px; border-radius: 8px; border: 1px solid #e1e9e5; background: #fbfcfb; font-size: 13px; }}
    .provider-chip strong {{ display: block; }}
    .provider-chip span {{ color: var(--muted); font-size: 12px; }}
    .settings-note {{ margin-top: 12px; padding: 10px 12px; border-radius: 8px; background: #f1f6f3; color: #4d5e58; font-size: 13px; line-height: 1.55; }}
    .option-list {{ display: grid; gap: 8px; }}
    .option {{ border: 1px solid #dce6e2; border-radius: 7px; padding: 10px; background: #fbfcfb; }}
    .option strong {{ display: block; }}
    .option span {{ display: block; margin-top: 3px; color: var(--muted); font-size: 12px; }}
    .avatar-grid {{ display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 14px; }}
    .avatar-preview {{ background: #fff; border: 1px solid #d8e2de; border-radius: 8px; padding: 14px; }}
    .avatar-box {{ aspect-ratio: 1; border-radius: 8px; background: linear-gradient(160deg, #07110f, #14362f); display: grid; place-items: center; color: rgba(255,255,255,.6); font-weight: 800; }}
    .persona-editor {{ background: #fff; border: 1px solid #d8e2de; border-radius: 8px; padding: 16px; }}
    .persona-editor textarea {{ width: 100%; min-height: 90px; border: 1px solid #c8d4cf; border-radius: 6px; padding: 10px; font-family: inherit; }}
    form.persona-form {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }}
    .persona-form .full {{ grid-column: 1 / -1; }}
    .persona-form input {{ width: 100%; }}
    .persona-form textarea[name="rules"] {{ min-height: 150px; }}
    .rule-list {{ margin: 10px 0 0; padding-left: 18px; color: #3a4a45; line-height: 1.7; }}
    .tabs {{ display: flex; gap: 8px; margin: 12px 0 14px; flex-wrap: wrap; }}
    .tab {{ padding: 8px 12px; border-radius: 6px; border: 1px solid #d8e2de; background: #fff; color: #40524c; text-decoration: none; font-weight: 700; }}
    .tab.active {{ background: #10201e; color: #fff; border-color: #10201e; }}
    @media (max-width: 920px) {{
      main {{ padding: 18px; }}
      header {{ align-items: flex-start; flex-direction: column; }}
      .layout {{ grid-template-columns: 1fr; }}
      .line {{ font-size: 24px; }}
      .controls {{ grid-template-columns: 1fr; }}
      form {{ grid-template-columns: 1fr; }}
      .obs-grid {{ grid-template-columns: 1fr; }}
      .app-shell {{ grid-template-columns: 1fr; }}
      .sidebar {{ display: none; }}
      .workspace {{ padding: 0 0 130px; }}
      .topbar, .room-grid, .studio-grid {{ padding-left: 16px; padding-right: 16px; }}
      .room-grid, .studio-grid, .two-col, .settings-grid, form.model-form, form.persona-form {{ grid-template-columns: 1fr; }}
      .launchbar {{ left: 0; height: auto; flex-wrap: wrap; }}
    }}
  </style>
</head>
<body>
<div class="app-shell">
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">螯</div>
      <div>
        <strong>螯螯直播</strong>
        <span>AI 数字人中控</span>
      </div>
    </div>
    <nav class="nav">
      <a class="active" href="#rooms"><span>▣</span>工作台</a>
      <a href="#create-room"><span>＋</span>创建直播间</a>
      <a href="#room-detail"><span>▤</span>直播间详情</a>
      <a href="#digital-human"><span>◉</span>数字人资产</a>
      <a href="#knowledge"><span>▥</span>商品知识</a>
      <a href="#settings"><span>◇</span>全局设置</a>
    </nav>
    <div class="sidebar-foot">
      <div>当前版本</div>
      <strong>Phase 1 Demo</strong>
    </div>
  </aside>

  <main class="workspace">
    <header class="topbar">
      <div>
        <h1>我的直播间</h1>
        <div class="subtitle">有人值守的 AI 主播工作台：商品知识、脚本、互动、合规和 OBS 统一管理。</div>
      </div>
      <div class="top-actions">
        <span class="status {status_class}"><span class="dot"></span>{status}</span>
        <a class="button" href="/api/resume">开始值守</a>
      </div>
    </header>

    <section id="rooms" class="room-grid">
      <article class="room-card selected">
        <div class="room-preview">AI</div>
        <div class="room-body">
          <strong>螯螯测试直播间</strong>
          <span>抖音 · 数字人直播间</span>
          <div class="room-meta">ID: AOAO-0001</div>
        </div>
      </article>
      <article class="room-card">
        <div class="room-preview muted">+</div>
        <div class="room-body">
          <strong>新建直播间</strong>
          <span>复制当前配置快速起号</span>
          <div class="room-meta">待创建</div>
        </div>
      </article>
    </section>

    <section id="create-room" class="section-page">
      <div class="section-title">
        <div>
          <h2>创建直播间</h2>
          <p>按流程配置：直播类型、商品、数字人、直播参数。这里才是新直播间的入口。</p>
        </div>
        <button type="button">新建直播间</button>
      </div>
      <div class="flow-grid">
        <div class="flow-card">
          <h3>1. 选择直播类型</h3>
          <div class="option-list">
            <div class="option"><strong>数字人带货</strong><span>商品讲解、弹幕问答、真人助理监管</span></div>
            <div class="option"><strong>文旅咨询</strong><span>路线、房态、交通信息，敏感信息人工确认</span></div>
            <div class="option"><strong>试播 Demo</strong><span>只用于本机测试和 OBS 合成</span></div>
          </div>
        </div>
        <div class="flow-card">
          <h3>2. 选择商品/知识库</h3>
          <div class="option-list">
            <div class="option"><strong>舟山海鲜礼盒 Demo</strong><span>家庭聚餐、节日送礼、本地特产</span></div>
            <div class="option"><strong>舟山文旅线路 Demo</strong><span>普陀山、朱家尖、东极岛</span></div>
          </div>
        </div>
        <div class="flow-card">
          <h3>3. 选择数字人和声音</h3>
          <div class="option-list">
            <div class="option"><strong>螯螯</strong><span>形象待接入，当前使用 OBS 字幕源占位</span></div>
            <div class="option"><strong>声音克隆</strong><span>待接 GPT-SoVITS / CosyVoice</span></div>
          </div>
        </div>
      </div>
    </section>

    <section id="room-detail" class="section-page">
      <div class="section-title">
        <div>
          <h2>直播间详情：螯螯测试直播间</h2>
          <p>这里才放脚本、互动、OBS 和开播控制；不是全局资产管理。</p>
        </div>
      </div>
      <div class="tabs">
        <a class="tab active" href="#script">脚本编排</a>
        <a class="tab" href="#interaction">互动队列</a>
        <a class="tab" href="#obs">OBS / 开播</a>
        <a class="tab" href="#guard">保护配置</a>
      </div>
    </section>

    <div class="studio-grid" id="script">
      <section class="left-rail" id="assets">
        <a class="back" href="#rooms">‹ 返回直播间</a>
        <div class="stage-preview">
          <div class="stage-screen">
            <div class="stage-badge">AI 主播 / AI 生成</div>
            <div class="stage-caption">{html.escape(state["current_line"])}</div>
          </div>
        </div>
        <div class="asset-card">
          <div class="asset-row"><span>数字人</span><strong>未选择</strong></div>
          <div class="asset-row"><span>声音</span><strong>未选择</strong></div>
          <div class="asset-row"><span>模型</span><strong>{html.escape(active_model)}</strong></div>
          <div class="asset-row"><span>输出模式</span><strong>OBS 浏览器源</strong></div>
        </div>
        <div class="asset-actions">
          <button type="button">选择数字人</button>
          <button type="button">选择声音</button>
        </div>
      </section>

      <section class="main-panels">
        <section id="script" class="module">
          <div class="module-head">
            <div>
              <h2>智能脚本</h2>
              <p>把商品知识、人设和合规边界喂给本地模型，生成可控回复。</p>
            </div>
            <span class="success-note">AI 知识库已加载</span>
          </div>
          <div class="step-bar">
            <span class="step done">1. 添加商品</span>
            <span class="step done">2. 生成话术</span>
            <span class="step done">3. 人设约束</span>
            <span class="step active">4. AI 回复</span>
            <span class="step">5. 去敏感词</span>
          </div>
          <div class="script-card">
            <div class="script-title">当前口播 / OBS 字幕</div>
            <div class="script-text">{html.escape(state["current_line"])}</div>
            {warning}
            <div class="meta-row">
              <span class="pill">运行 {state["uptime_seconds"]} 秒</span>
              <span class="pill">话术位置 #{state["index"]}</span>
              <span class="pill">回复来源：{html.escape(state["last_reply_source"])}</span>
              <span class="pill">AI 标识已显示</span>
            </div>
          </div>
        </section>

        <section class="module two-col">
          <div id="knowledge" class="sub-panel">
            <h2>商品知识库</h2>
            <div class="metric-row">
              <div><strong>{knowledge.get("products", 0)}</strong><span>商品/场景</span></div>
              <div><strong>{knowledge.get("knowledge_items", 0)}</strong><span>知识条目</span></div>
              <div><strong>{knowledge.get("embeddings", 0)}</strong><span>RAG 索引</span></div>
            </div>
            <form method="post" action="/api/rag/rebuild">
              <button type="submit">重建 RAG 语义索引</button>
              <span class="tag {rag_class}">{rag_label}</span>
            </form>
            <form class="knowledge-form" method="post" action="/api/knowledge/add">
              <select name="product_id">{product_options}</select>
              <select name="kind">
                <option value="selling_points">卖点</option>
                <option value="safe_claims">安全话术</option>
                <option value="faq">FAQ</option>
                <option value="risky_claims">禁用表达</option>
              </select>
              <input name="title" placeholder="标题，例如：礼盒送礼场景">
              <select name="safe_level">
                <option value="safe">可用于回复</option>
                <option value="risky">仅作风险提示</option>
              </select>
              <textarea name="text" placeholder="输入商品介绍、卖点、FAQ 或禁用表达"></textarea>
              <button type="submit">加入知识库</button>
            </form>
          </div>
          <div id="guard" class="sub-panel">
            <h2>保护配置</h2>
            <div class="check"><span>声明 AI 身份</span><span class="tag ok">已启用</span></div>
            <div class="check"><span>售后/价格/库存</span><span class="tag ok">真人接管</span></div>
            <div class="check"><span>禁忌词输出过滤</span><span class="tag ok">已启用</span></div>
            <div class="check"><span>隐式元数据标识</span><span class="tag no">待补齐</span></div>
          </div>
        </section>

        <section class="module" id="interaction">
          <div class="module-head">
            <div>
              <h2>知识条目</h2>
              <p>最近添加的商品资料会参与弹幕回复检索。</p>
            </div>
          </div>
          <table class="data-table">
            <thead>
              <tr><th>标题</th><th>类型</th><th>内容</th><th>级别</th></tr>
            </thead>
            <tbody>{knowledge_rows}</tbody>
          </table>
        </section>

        <section class="module">
          <div class="module-head">
            <div>
              <h2>主动互动控制</h2>
              <p>模拟弹幕、真人接管、话术切换都会同步到 OBS 字幕源。</p>
            </div>
            <div class="controls compact">
              <a class="button" href="/api/resume">继续</a>
              <a class="button danger" href="/api/pause">暂停</a>
              <a class="button secondary" href="/api/next">下一句</a>
            </div>
          </div>
          <form method="post" action="/api/danmaku">
            <input name="text" placeholder="模拟弹幕：这个海鲜礼盒适合送人吗 / 主播是真人吗 / 发货要多久">
            <button type="submit">模拟提问</button>
          </form>
          <form method="post" action="/api/assistant">
            <input name="text" placeholder="真人助理确认后的回复">
            <button type="submit">主动控制回复</button>
          </form>
          <p class="small">上一条弹幕：{html.escape(state["last_danmaku"] or "暂无")}</p>
          <div class="queue-list">{interaction_rows}</div>
        </section>

        <section id="obs" class="module">
          <div class="module-head">
            <div>
              <h2>OBS 与开播工具</h2>
              <p>连接 OBS 后可自动创建字幕源、刷新 overlay，后续可扩展切场景和录制。</p>
            </div>
            <span id="obs-status-tag" class="tag todo">待连接</span>
          </div>
          <div class="obs-grid">
            <input id="obs-password" type="password" autocomplete="current-password" placeholder="输入 OBS WebSocket 密码">
            <button id="obs-connect" type="button">连接 OBS</button>
            <button id="obs-create-overlay" type="button">创建字幕源</button>
            <button id="obs-refresh-overlay" type="button">刷新字幕源</button>
          </div>
          <div id="obs-log" class="obs-log">等待连接 OBS...</div>
        </section>
      </section>

      <aside class="right-rail">
        <section class="module">
          <h2>接入状态</h2>
          <div class="check"><span>助理控制台</span><span class="tag ok">已完成</span></div>
          <div class="check"><span>OBS 字幕源</span><span class="tag ok">已完成</span></div>
          <div class="check"><span>本地 Ollama</span><span class="tag {ollama_class}">{ollama_label}</span></div>
          <div class="check"><span>商品知识库</span><span class="tag ok">{knowledge.get("knowledge_items", 0)} 条</span></div>
          <div class="check"><span>RAG 语义索引</span><span class="tag {rag_class}">{rag_label}</span></div>
          <div class="check"><span>数字人形象</span><span class="tag todo">待接入</span></div>
          <div class="check"><span>声音克隆</span><span class="tag todo">待接入</span></div>
        </section>
        <section class="module">
          <h2>直播设置</h2>
          <label class="field-label">播报频率</label>
          <select><option>中频率</option><option>低频率</option><option>高频率</option></select>
          <label class="field-label">平台</label>
          <select><option>抖音</option></select>
          <label class="field-label">直播间地址</label>
          <input placeholder="请输入直播间地址">
        </section>
      </aside>
    </div>

    <section id="digital-human" class="section-page">
      <div class="section-title">
        <div>
          <h2>数字人资产</h2>
          <p>数字人是独立资产：形象、人设、声音、输出方式，多个直播间可以复用。</p>
        </div>
        <button type="button">创建数字人</button>
      </div>
      <div class="avatar-grid">
        <div class="avatar-preview">
          <div class="avatar-box">螯螯形象待接入</div>
          <div class="asset-card">
            <div class="asset-row"><span>形象状态</span><strong>待接入</strong></div>
            <div class="asset-row"><span>声音状态</span><strong>待接入</strong></div>
            <div class="asset-row"><span>人设状态</span><strong>已配置</strong></div>
          </div>
        </div>
        <div class="persona-editor">
          <h3>螯螯人设</h3>
          <form class="persona-form" method="post" action="/api/persona/update">
            <div class="full">
              <label class="field-label" for="persona-positioning">定位</label>
              <textarea id="persona-positioning" name="positioning">{html.escape(STATE.persona.get("positioning", ""))}</textarea>
            </div>
            <div class="full">
              <label class="field-label" for="persona-tone">说话口吻</label>
              <textarea id="persona-tone" name="tone">{html.escape(persona_voice.get("tone", ""))}</textarea>
            </div>
            <div>
              <label class="field-label" for="persona-max-chars">单次回复字数上限</label>
              <input id="persona-max-chars" name="max_chars" type="number" min="40" max="180" value="{html.escape(str(persona_style.get("max_chars", 90)))}">
            </div>
            <div>
              <label class="field-label" for="persona-max-sentences">句数上限</label>
              <input id="persona-max-sentences" name="max_sentences" type="number" min="1" max="5" value="{html.escape(str(persona_style.get("max_sentences", 3)))}">
            </div>
            <div class="full">
              <label class="field-label" for="persona-rules">回复规则（一行一条）</label>
              <textarea id="persona-rules" name="rules">{html.escape(persona_rules_text)}</textarea>
            </div>
            <div class="form-actions">
              <button type="submit">保存人设</button>
              <span class="tag ok">会进入模型系统提示词</span>
            </div>
          </form>
          <div class="two-col">
            <div class="sub-panel">
              <h2>形象</h2>
              <p class="small">后续接入 Duix Avatar / HeyGem，本区负责上传素材、训练/克隆、预览。</p>
            </div>
            <div class="sub-panel">
              <h2>声音</h2>
              <p class="small">后续接 GPT-SoVITS / CosyVoice，本区负责样本、音色、情绪标签。</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section id="settings" class="section-page">
      <div class="section-title">
        <div>
          <h2>全局设置</h2>
          <p>这里放跨直播间复用的配置：模型、OBS、平台、合规和日志。直播间自己的设置不放这里。</p>
        </div>
      </div>
      <div class="settings-grid">
        <div class="flow-card">
          <h3>模型路由</h3>
          <div class="provider-summary">
            <div>
              <strong id="provider-label">{html.escape(active_provider_label)}</strong>
              <span id="provider-meta">{html.escape(provider_type_label)} · {html.escape(active_model or "未配置模型")}</span>
            </div>
            <span class="tag {api_key_class}" id="provider-key-status">{api_key_status}</span>
          </div>
          <form class="model-form" method="post" action="/api/model/update">
            <div class="form-field">
              <label for="provider-id">供应商</label>
              <select id="provider-id" name="provider_id">{provider_options}</select>
            </div>
            <div class="form-field">
              <label for="provider-model">模型名</label>
              <input id="provider-model" name="model" value="{html.escape(active_model)}" placeholder="deepseek-chat / qwen-plus / gemma4:e4b">
            </div>
            <div class="form-field full">
              <label for="provider-base-url">Base URL</label>
              <input id="provider-base-url" name="base_url" value="{html.escape(active_provider.get("base_url", ""))}" placeholder="https://api.example.com/v1">
            </div>
            <div class="form-field full">
              <label for="provider-api-key">API Key</label>
              <input id="provider-api-key" name="api_key" type="password" autocomplete="off" placeholder="已保存则留空；本地 Ollama 不需要">
            </div>
            <div class="form-actions">
              <button type="submit">保存并切换</button>
              <span class="tag {rag_class}">RAG：{rag_label}</span>
              <span class="tag {ollama_class}">Embedding：本地 Ollama</span>
            </div>
          </form>
          <div class="settings-note">后续接 DeepSeek、Kimi、Qwen、MiMo 或中转站，只要它是 OpenAI 兼容的 <code>/chat/completions</code> 接口，就能走这里。商品知识仍由本地 RAG 检索后塞进提示词。</div>
        </div>
        <div class="flow-card">
          <h3>可用供应商</h3>
          <div class="provider-list">{provider_chips}</div>
        </div>
        <div class="flow-card">
          <h3>平台设置</h3>
          <div class="asset-row"><span>平台</span><strong>抖音</strong></div>
          <div class="asset-row"><span>弹幕捕获</span><strong>待接入</strong></div>
          <div class="asset-row"><span>推流方式</span><strong>OBS</strong></div>
        </div>
        <div class="flow-card">
          <h3>合规设置</h3>
          <div class="asset-row"><span>显式标识</span><strong>已启用</strong></div>
          <div class="asset-row"><span>真人监管</span><strong>已启用</strong></div>
          <div class="asset-row"><span>隐式标识</span><strong>待补齐</strong></div>
        </div>
      </div>
    </section>

    <footer class="launchbar">
      <span>平台：抖音</span>
      <input placeholder="请输入直播间地址">
      <button type="button" class="muted-button">开始弹幕捕获</button>
      <button type="button">保存</button>
      <button type="button" class="green-button">开始直播</button>
    </footer>
  </main>
</div>
<script>
(() => {{
  const providers = {providers_json};
  const providerSelect = document.getElementById("provider-id");
  const modelInput = document.getElementById("provider-model");
  const baseUrlInput = document.getElementById("provider-base-url");
  const keyInput = document.getElementById("provider-api-key");
  const labelEl = document.getElementById("provider-label");
  const metaEl = document.getElementById("provider-meta");
  const keyStatusEl = document.getElementById("provider-key-status");
  if (!providerSelect || !modelInput || !baseUrlInput) return;

  function syncProviderFields() {{
    const provider = providers[providerSelect.value] || {{}};
    modelInput.value = provider.model || "";
    baseUrlInput.value = provider.base_url || "";
    if (keyInput) {{
      keyInput.value = "";
      keyInput.placeholder = provider.api_key_required
        ? (provider.api_key_saved ? "密钥已保存，留空不改" : "粘贴 API Key，本地保存")
        : "本地 Ollama 不需要 API Key";
    }}
    if (labelEl) labelEl.textContent = provider.label || providerSelect.value;
    if (metaEl) {{
      const typeLabel = provider.type === "ollama" ? "本地 Ollama" : "OpenAI 兼容接口";
      metaEl.textContent = `${{typeLabel}} · ${{provider.model || "未配置模型"}}`;
    }}
    if (keyStatusEl) {{
      const needsKey = Boolean(provider.api_key_required);
      keyStatusEl.textContent = needsKey
        ? (provider.api_key_saved ? "密钥已保存" : "等待填写密钥")
        : "本地模型无需密钥";
      keyStatusEl.className = `tag ${{!needsKey || provider.api_key_saved ? "ok" : "todo"}}`;
    }}
  }}

  providerSelect.addEventListener("change", syncProviderFields);
}})();
</script>
<script src="/obs.js?v=5"></script>
</body>
</html>"""

    def overlay_html(self) -> str:
        state = STATE.snapshot()
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="2">
  <title>螯螯 OBS Overlay</title>
  <style>
    html, body {{ margin: 0; width: 100%; height: 100%; background: transparent; overflow: hidden; font-family: Arial, "Microsoft YaHei", sans-serif; }}
    .badge {{
      position: absolute;
      top: 30px;
      left: 34px;
      background: rgba(16, 28, 24, .78);
      color: #fff;
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 24px;
      font-weight: 800;
      border: 1px solid rgba(255,255,255,.3);
    }}
    .assist {{
      position: absolute;
      top: 30px;
      right: 34px;
      background: rgba(19, 138, 91, .82);
      color: #fff;
      padding: 10px 14px;
      border-radius: 6px;
      font-size: 22px;
      font-weight: 700;
    }}
    .caption-wrap {{
      position: absolute;
      left: 6%;
      right: 6%;
      bottom: 6%;
      display: grid;
      gap: 10px;
    }}
    .speaker {{
      justify-self: center;
      background: rgba(255, 255, 255, .92);
      color: #0f2e2f;
      padding: 7px 12px;
      border-radius: 999px;
      font-size: 20px;
      font-weight: 800;
    }}
    .caption {{
      background: rgba(13, 24, 22, .78);
      color: #fff;
      padding: 18px 24px;
      border-radius: 8px;
      font-size: 34px;
      line-height: 1.35;
      text-align: center;
      border: 1px solid rgba(255,255,255,.2);
      text-shadow: 0 1px 2px rgba(0,0,0,.42);
    }}
  </style>
</head>
<body>
  <div class="badge">{html.escape(state["visible_label"])}</div>
  <div class="assist">真人助理监管中</div>
  <div class="caption-wrap">
    <div class="speaker">螯螯</div>
    <div class="caption">{html.escape(state["current_line"])}</div>
  </div>
</body>
</html>"""

    def obs_js(self) -> str:
        return r"""(() => {
  const logEl = document.getElementById("obs-log");
  const obsStatusEl = document.getElementById("obs-status-tag");
  const passwordEl = document.getElementById("obs-password");
  const connectEl = document.getElementById("obs-connect");
  const createEl = document.getElementById("obs-create-overlay");
  const refreshEl = document.getElementById("obs-refresh-overlay");
  const OBS_URL = "ws://127.0.0.1:4455";
  const SOURCE_NAME = "AI字幕和合规角标";
  let ws = null;
  let requestSeq = 1;
  let currentSceneName = "";
  const pending = new Map();

  if (!logEl || !passwordEl) return;
  passwordEl.value = localStorage.getItem("aoao.obs.password") || "";

  function log(message) {
    const time = new Date().toLocaleTimeString();
    logEl.textContent = `[${time}] ${message}\n` + logEl.textContent;
  }

  function setObsStatus(label, className) {
    if (!obsStatusEl) return;
    obsStatusEl.textContent = label;
    obsStatusEl.className = `tag ${className}`;
  }

  function bytesToBase64(bytes) {
    let binary = "";
    bytes.forEach((byte) => binary += String.fromCharCode(byte));
    return btoa(binary);
  }

  async function sha256Base64(text) {
    const data = new TextEncoder().encode(text);
    const hash = await crypto.subtle.digest("SHA-256", data);
    return bytesToBase64(new Uint8Array(hash));
  }

  async function auth(password, salt, challenge) {
    const secret = await sha256Base64(password + salt);
    return sha256Base64(secret + challenge);
  }

  function send(payload) {
    ws.send(JSON.stringify(payload));
  }

  function request(requestType, requestData = {}) {
    return new Promise((resolve, reject) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        reject(new Error("OBS 未连接"));
        return;
      }
      const requestId = String(requestSeq++);
      pending.set(requestId, { resolve, reject, requestType });
      send({ op: 6, d: { requestType, requestId, requestData } });
    });
  }

  async function connect() {
    const password = passwordEl.value.trim();
    passwordEl.value = password;
    localStorage.setItem("aoao.obs.password", password);
    log("正在连接 OBS WebSocket...");
    ws = new WebSocket(OBS_URL, "obswebsocket.json");
    const helloTimer = setTimeout(() => {
      log("仍未收到 OBS Hello 包：请强制刷新页面，或确认不是在 OBS 的浏览器源里打开控制台。");
    }, 3000);
    ws.onopen = () => log("WebSocket 已打开，等待 OBS Hello 包...");
    ws.onerror = () => log("连接失败：请确认 OBS WebSocket 已启用，端口为 4455。");
    ws.onclose = (event) => {
      if (event.code === 4009) {
        setObsStatus("密码错误", "no");
        log("OBS 鉴权失败：密码不匹配。请重新复制 OBS WebSocket 设置里的服务器密码。");
        return;
      }
      setObsStatus("已断开", "todo");
      log(`OBS WebSocket 已断开。code=${event.code || "未知"}`);
    };
    ws.onmessage = async (event) => {
      clearTimeout(helloTimer);
      log("收到 OBS 协议消息。");
      const packet = JSON.parse(event.data);
      if (packet.op === 0) {
        const authInfo = packet.d.authentication;
        const identify = { rpcVersion: 1, eventSubscriptions: 0 };
        if (authInfo) {
          log("OBS 要求密码鉴权，正在计算认证信息...");
          identify.authentication = await auth(password, authInfo.salt, authInfo.challenge);
        }
        send({ op: 1, d: identify });
        log("已发送鉴权请求。");
      }
      if (packet.op === 2) {
        setObsStatus("已连接", "ok");
        log("鉴权成功。");
        const version = await request("GetVersion");
        log(`OBS ${version.obsVersion} / WebSocket ${version.obsWebSocketVersion}`);
        const scene = await request("GetCurrentProgramScene");
        currentSceneName = scene.currentProgramSceneName;
        log(`当前场景：${currentSceneName}`);
      }
      if (packet.op === 7) {
        const response = packet.d;
        const item = pending.get(response.requestId);
        if (!item) return;
        pending.delete(response.requestId);
        if (response.requestStatus && response.requestStatus.result) {
          item.resolve(response.responseData || {});
        } else {
          const comment = response.requestStatus?.comment || "请求失败";
          item.reject(new Error(`${item.requestType}: ${comment}`));
        }
      }
    };
  }

  async function createOverlay() {
    try {
      if (!currentSceneName) {
        const scene = await request("GetCurrentProgramScene");
        currentSceneName = scene.currentProgramSceneName;
      }
      try {
        await request("CreateInput", {
          sceneName: currentSceneName,
          inputName: SOURCE_NAME,
          inputKind: "browser_source",
          inputSettings: {
            url: `${location.origin}/overlay`,
            width: 1920,
            height: 1080,
            reroute_audio: false
          },
          sceneItemEnabled: true
        });
        log(`已在「${currentSceneName}」创建浏览器源：${SOURCE_NAME}`);
      } catch (error) {
        log("字幕源可能已存在，改为更新设置。");
        await request("SetInputSettings", {
          inputName: SOURCE_NAME,
          inputSettings: {
            url: `${location.origin}/overlay`,
            width: 1920,
            height: 1080,
            reroute_audio: false
          },
          overlay: true
        });
        log("已更新字幕源设置。");
      }
    } catch (error) {
      log(error.message);
    }
  }

  async function refreshOverlay() {
    try {
      await request("PressInputPropertiesButton", {
        inputName: SOURCE_NAME,
        propertyName: "refreshnocache"
      });
      log("已刷新 OBS 字幕源。");
    } catch (error) {
      log(error.message);
    }
  }

  connectEl?.addEventListener("click", connect);
  createEl?.addEventListener("click", createOverlay);
  refreshEl?.addEventListener("click", refreshOverlay);
})();"""

    def send_html(self, content: str) -> None:
        payload = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, data: dict) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_javascript(self, content: str) -> None:
        payload = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def redirect(self, target: str) -> None:
        self.send_response(303)
        self.send_header("Location", target)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        print("%s - %s" % (self.address_string(), format % args))


def main() -> None:
    threading.Thread(target=ticker, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", 8787), Handler)
    print("Aoao live console: http://127.0.0.1:8787")
    print("OBS overlay:        http://127.0.0.1:8787/overlay")
    server.serve_forever()


if __name__ == "__main__":
    main()
