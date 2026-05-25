from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIGS_DIR = ROOT / "configs"
PERSONA_PATH = CONFIGS_DIR / "persona.json"
SCRIPT_PATH = ROOT / "scripts" / "aoao_mainline.txt"
FORBIDDEN_PATH = CONFIGS_DIR / "forbidden_terms.txt"
INTEGRATIONS_PATH = CONFIGS_DIR / "integrations.json"
SECRETS_PATH = CONFIGS_DIR / "secrets.local.json"
PRODUCTS_PATH = CONFIGS_DIR / "products.yaml"
DB_PATH = ROOT / "data" / "aoao_live.db"
TTS_OUTPUT_DIR = ROOT / "data" / "tts"
VOICE_SAMPLES_DIR = ROOT / "data" / "voice_samples"
OVERLAY_DIR = ROOT / "overlay"
FRONTEND_DIST = ROOT / "frontend" / "dist"

HOST = "127.0.0.1"
PORT = 8787


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
