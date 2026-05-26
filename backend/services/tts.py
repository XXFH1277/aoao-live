from __future__ import annotations

import asyncio
import base64
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import aiohttp

from backend.config import INTEGRATIONS_PATH, SECRETS_PATH, TTS_OUTPUT_DIR, load_json, save_json

# Maximum number of TTS files to keep; older ones are cleaned up
TTS_MAX_FILES = 200
# Maximum age in seconds (2 hours)
TTS_MAX_AGE = 7200


class TTSService:
    def __init__(self, integrations: dict[str, Any]) -> None:
        self.integrations = integrations
        self._gen_lock = asyncio.Lock()  # serialize TTS generation

    def config(self) -> dict[str, Any]:
        tts = self.integrations.setdefault("tts", {})
        tts.setdefault("status", "placeholder")
        tts.setdefault("active_provider", "windows_sapi")
        tts.setdefault("rate", 0)
        tts.setdefault("volume", 100)
        tts.setdefault("preferred", "GPT-SoVITS or CosyVoice")
        tts.setdefault("notes", "Start with Windows SAPI/system voice, then replace with cloned Aoao voice.")

        providers = tts.setdefault("providers", {})
        providers.setdefault(
            "windows_sapi",
            {
                "label": "Windows 系统语音",
                "type": "windows_sapi",
                "base_url": "",
                "model": "",
                "voice": "",
                "api_key_required": False,
            },
        )
        providers.setdefault(
            "gpt_sovits",
            {
                "label": "本地 GPT-SoVITS",
                "type": "gpt_sovits_api",
                "base_url": "http://127.0.0.1:9880",
                "model": "",
                "voice": "",
                "api_key_required": False,
                "extra": {
                    "ref_audio_path": "",
                    "prompt_text": "",
                    "text_lang": "zh",
                    "prompt_lang": "zh",
                    "text_split_method": "cut5",
                    "batch_size": 1,
                    "media_type": "wav",
                    "streaming_mode": False,
                },
            },
        )
        providers.setdefault(
            "minimax",
            {
                "label": "MiniMax T2A",
                "type": "minimax_t2a",
                "base_url": "https://api.minimax.io/v1/t2a_v2",
                "model": "speech-2.8-hd",
                "voice": "",
                "api_key_required": True,
            },
        )
        providers.setdefault(
            "mimo",
            {
                "label": "MiMo TTS",
                "type": "mimo_tts_chat",
                "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
                "model": "mimo-v2.5-tts",
                "voice": "mimo_default",
                "api_key_required": True,
            },
        )
        providers.setdefault(
            "custom_openai",
            {
                "label": "自定义 OpenAI 兼容语音",
                "type": "openai_audio_speech",
                "base_url": "",
                "model": "",
                "voice": "",
                "api_key_required": True,
            },
        )
        providers.setdefault(
            "custom_http",
            {
                "label": "自定义 HTTP TTS",
                "type": "http_audio_or_json",
                "base_url": "",
                "model": "",
                "voice": "",
                "api_key_required": False,
            },
        )
        return tts

    def provider_config(self, provider_id: str = "") -> tuple[str, dict[str, Any]]:
        cfg = self.config()
        providers = cfg.get("providers", {})
        pid = provider_id or cfg.get("active_provider", "windows_sapi")
        provider = providers.get(pid) or providers.get("windows_sapi", {})
        return str(pid), provider

    def api_key_for(self, provider_id: str) -> str:
        secrets = load_json(SECRETS_PATH)
        return secrets.get("tts_api_keys", {}).get(provider_id, "")

    def status(self) -> dict[str, Any]:
        cfg = self.config()
        TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        generated = len(list(TTS_OUTPUT_DIR.glob("*.wav"))) + len(list(TTS_OUTPUT_DIR.glob("*.mp3")))
        providers = cfg.get("providers", {})
        sanitized = {}
        for pid, provider in providers.items():
            needs_key = bool(provider.get("api_key_required", False))
            has_key = bool(self.api_key_for(pid))
            sanitized[pid] = {
                "label": provider.get("label", pid),
                "type": provider.get("type", ""),
                "base_url": provider.get("base_url", ""),
                "model": provider.get("model", ""),
                "voice": provider.get("voice", ""),
                "extra": provider.get("extra", {}),
                "api_key_required": needs_key,
                "api_key_saved": has_key,
                "ready": not needs_key or has_key,
            }
        return {
            "status": cfg.get("status", "placeholder"),
            "active_provider": cfg.get("active_provider", "windows_sapi"),
            "rate": cfg.get("rate", 0),
            "volume": cfg.get("volume", 100),
            "preferred": cfg.get("preferred", ""),
            "notes": cfg.get("notes", ""),
            "generated_count": generated,
            "providers": sanitized,
        }

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        cfg = self.config()
        provider_id = str(payload.get("provider_id") or payload.get("active_provider") or cfg.get("active_provider", "windows_sapi"))
        providers = cfg.setdefault("providers", {})
        provider = providers.setdefault(provider_id, {"label": provider_id, "type": "http_audio_or_json", "api_key_required": False})
        cfg["active_provider"] = provider_id

        for key in ("preferred", "notes"):
            if key in payload:
                cfg[key] = str(payload.get(key) or "").strip()
        for key in ("base_url", "model", "voice", "label", "type"):
            if key in payload:
                provider[key] = str(payload.get(key) or "").strip()
        if "extra" in payload and isinstance(payload["extra"], dict):
            provider["extra"] = payload["extra"]
        if "extra_json" in payload:
            raw_extra = str(payload.get("extra_json") or "").strip()
            if raw_extra:
                try:
                    parsed_extra = json.loads(raw_extra)
                    if isinstance(parsed_extra, dict):
                        provider["extra"] = parsed_extra
                        provider.pop("extra_error", None)
                except json.JSONDecodeError:
                    provider["extra_error"] = "invalid_extra_json"
            else:
                provider["extra"] = {}
                provider.pop("extra_error", None)
        for key in ("rate", "volume"):
            if key in payload:
                try:
                    cfg[key] = int(payload[key])
                except (TypeError, ValueError):
                    pass
        cfg["rate"] = max(-10, min(10, int(cfg.get("rate", 0))))
        cfg["volume"] = max(0, min(100, int(cfg.get("volume", 100))))
        save_json(INTEGRATIONS_PATH, self.integrations)

        api_key = str(payload.get("api_key") or "").strip()
        if api_key:
            secrets = load_json(SECRETS_PATH) or {"tts_api_keys": {}}
            secrets.setdefault("tts_api_keys", {})[provider_id] = api_key
            save_json(SECRETS_PATH, secrets)
        return self.status()

    def cleanup_old_files(self) -> int:
        """Remove old TTS files beyond max count or max age. Returns number deleted."""
        if not TTS_OUTPUT_DIR.exists():
            return 0
        files = sorted(TTS_OUTPUT_DIR.glob("tts-*"), key=lambda f: f.stat().st_mtime)
        now = time.time()
        removed = 0
        # Remove files older than TTS_MAX_AGE
        for f in files:
            try:
                if now - f.stat().st_mtime > TTS_MAX_AGE:
                    f.unlink()
                    removed += 1
            except OSError:
                pass
        # If still over limit, remove oldest
        files = sorted(TTS_OUTPUT_DIR.glob("tts-*"), key=lambda f: f.stat().st_mtime)
        while len(files) > TTS_MAX_FILES:
            try:
                files[0].unlink()
                removed += 1
            except OSError:
                pass
            files = files[1:]
        return removed

    async def speak(
        self,
        text: str,
        provider: str = "",
        voice: str = "",
        rate: int | None = None,
        volume: int | None = None,
    ) -> dict[str, Any]:
        async with self._gen_lock:
            return await self._speak_impl(text, provider, voice, rate, volume)

    async def _speak_impl(
        self,
        text: str,
        provider: str = "",
        voice: str = "",
        rate: int | None = None,
        volume: int | None = None,
    ) -> dict[str, Any]:
        cfg = self.config()
        text = text.strip()
        if not text:
            return {"ok": False, "error": "empty_text"}
        if len(text) > 300:
            text = text[:300]

        provider_id, provider_cfg = self.provider_config(provider)
        selected_voice = voice if voice != "" else str(provider_cfg.get("voice", ""))
        selected_rate = int(rate if rate is not None else cfg.get("rate", 0))
        selected_volume = int(volume if volume is not None else cfg.get("volume", 100))
        selected_rate = max(-10, min(10, selected_rate))
        selected_volume = max(0, min(100, selected_volume))

        # Periodic cleanup
        self.cleanup_old_files()

        provider_type = provider_cfg.get("type", "windows_sapi")
        if provider_type == "minimax_t2a":
            return await self._speak_minimax(text, provider_id, provider_cfg, selected_voice, selected_rate, selected_volume)
        if provider_type == "gpt_sovits_api":
            return await self._speak_gpt_sovits(text, provider_id, provider_cfg, selected_voice)
        if provider_type == "openai_audio_speech":
            return await self._speak_openai_audio(text, provider_id, provider_cfg, selected_voice)
        if provider_type == "mimo_tts_chat":
            return await self._speak_mimo_tts_chat(text, provider_id, provider_cfg, selected_voice)
        if provider_type == "http_audio_or_json":
            return await self._speak_http(text, provider_id, provider_cfg, selected_voice)
        return await self._speak_windows_sapi(text, selected_voice, selected_rate, selected_volume)

    async def _speak_windows_sapi(self, text: str, voice: str, rate: int, volume: int) -> dict[str, Any]:
        TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"tts-{int(time.time())}-{uuid.uuid4().hex[:8]}.wav"
        output_path = TTS_OUTPUT_DIR / filename

        text_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        safe_path = str(output_path).replace("'", "''")
        safe_voice = voice.replace("'", "''")
        # If no voice specified, auto-select a Chinese voice if available
        if safe_voice:
            select_voice_block = f"try {{ $synth.SelectVoice('{safe_voice}') }} catch {{ }}"
        else:
            select_voice_block = (
                "$zhVoice = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'zh-*' } | Select-Object -First 1\n"
                "if ($zhVoice) { try { $synth.SelectVoice($zhVoice.VoiceInfo.Name) } catch { } }"
            )
        script = (
            f"$text = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{text_b64}'))\n"
            f"$out = '{safe_path}'\n"
            "Add-Type -AssemblyName System.Speech\n"
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
            f"$synth.Volume = {volume}\n"
            f"$synth.Rate = {rate}\n"
            f"{select_voice_block}\n"
            "$synth.SetOutputToWaveFile($out)\n"
            "$synth.Speak($text)\n"
            "$synth.Dispose()\n"
        )
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")

        try:
            await asyncio.to_thread(
                subprocess.run,
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
                check=True,
                capture_output=True,
                text=True,
                timeout=45,
            )
        except subprocess.CalledProcessError as exc:
            return {"ok": False, "provider": "windows_sapi", "error": exc.stderr.strip() or str(exc)}
        except Exception as exc:
            return {"ok": False, "provider": "windows_sapi", "error": str(exc)}

        if not output_path.exists() or output_path.stat().st_size == 0:
            return {"ok": False, "provider": "windows_sapi", "error": "audio_not_created"}
        if output_path.stat().st_size < 1024:
            return {
                "ok": False,
                "provider": "windows_sapi",
                "error": "audio_too_small_or_voice_missing",
                "hint": "Windows 系统语音可能没有安装中文语音；可切换 MiniMax/MiMo/API TTS 或安装中文 SAPI 语音。",
            }

        return {
            "ok": True,
            "provider": "windows_sapi",
            "filename": filename,
            "audio_url": f"/media/tts/{filename}",
            "bytes": output_path.stat().st_size,
            "text": text,
        }

    def _write_audio(self, audio: bytes, suffix: str) -> dict[str, Any]:
        TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"tts-{int(time.time())}-{uuid.uuid4().hex[:8]}{suffix}"
        output_path = TTS_OUTPUT_DIR / filename
        output_path.write_bytes(audio)
        return {
            "filename": filename,
            "audio_url": f"/media/tts/{filename}",
            "bytes": output_path.stat().st_size,
        }

    async def _speak_minimax(
        self,
        text: str,
        provider_id: str,
        provider: dict[str, Any],
        voice: str,
        rate: int,
        volume: int,
    ) -> dict[str, Any]:
        api_key = self.api_key_for(provider_id)
        if not api_key:
            return {"ok": False, "provider": provider_id, "error": "missing_api_key"}
        service_url = str(provider.get("base_url", "")).strip()
        if not service_url:
            return {"ok": False, "provider": provider_id, "error": "missing_base_url"}
        model = str(provider.get("model", "speech-2.8-hd") or "speech-2.8-hd")
        voice_id = voice or "Chinese_Mandarin_Young_Female"
        speed = max(0.5, min(2.0, 1 + rate * 0.08))
        vol = max(0.1, min(10.0, volume / 100))
        body = {
            "model": model,
            "text": text,
            "stream": False,
            "language_boost": "auto",
            "output_format": "hex",
            "voice_setting": {"voice_id": voice_id, "speed": speed, "vol": vol, "pitch": 0},
            "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1},
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    service_url,
                    json=body,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    data = await resp.json()
        except Exception as exc:
            return {"ok": False, "provider": provider_id, "error": str(exc)}

        audio_hex = data.get("data", {}).get("audio", "")
        if not audio_hex:
            base_resp = data.get("base_resp", {})
            return {"ok": False, "provider": provider_id, "error": base_resp.get("status_msg", "missing_audio")}
        try:
            audio = bytes.fromhex(audio_hex)
        except ValueError:
            return {"ok": False, "provider": provider_id, "error": "invalid_hex_audio"}
        result = self._write_audio(audio, ".mp3")
        return {"ok": True, "provider": provider_id, "text": text, **result}

    async def _speak_openai_audio(self, text: str, provider_id: str, provider: dict[str, Any], voice: str) -> dict[str, Any]:
        api_key = self.api_key_for(provider_id)
        if not api_key:
            return {"ok": False, "provider": provider_id, "error": "missing_api_key"}
        base_url = str(provider.get("base_url", "")).rstrip("/")
        model = str(provider.get("model", "")).strip()
        if not base_url or not model:
            return {"ok": False, "provider": provider_id, "error": "missing_base_url_or_model"}
        body = {"model": model, "input": text, "voice": voice or "default", "response_format": "mp3"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/audio/speech",
                    json=body,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    content_type = resp.headers.get("Content-Type", "")
                    if content_type.startswith("audio/"):
                        audio = await resp.read()
                    else:
                        data = await resp.json()
                        return {"ok": False, "provider": provider_id, "error": data.get("error", data)}
        except Exception as exc:
            return {"ok": False, "provider": provider_id, "error": str(exc)}
        result = self._write_audio(audio, ".mp3")
        return {"ok": True, "provider": provider_id, "text": text, **result}

    async def _speak_mimo_tts_chat(self, text: str, provider_id: str, provider: dict[str, Any], voice: str) -> dict[str, Any]:
        api_key = self.api_key_for(provider_id)
        if not api_key:
            return {"ok": False, "provider": provider_id, "error": "missing_api_key"}
        base_url = str(provider.get("base_url", "")).rstrip("/")
        model = str(provider.get("model", "")).strip()
        if not base_url or not model:
            return {"ok": False, "provider": provider_id, "error": "missing_base_url_or_model"}
        voice_id = voice or "mimo_default"
        body = {
            "model": model,
            "messages": [
                {"role": "user", "content": "用亲切自然的中文电商主播语气播报。"},
                {"role": "assistant", "content": text},
            ],
            "audio": {"format": "wav", "voice": voice_id},
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/chat/completions",
                    json=body,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "api-key": api_key,
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=90),
                ) as resp:
                    try:
                        data = await resp.json()
                    except Exception:
                        data = {"raw": (await resp.text())[:500]}
                    if resp.status >= 400:
                        return {"ok": False, "provider": provider_id, "error": str(data)[:500], "http_status": resp.status}
        except Exception as exc:
            return {"ok": False, "provider": provider_id, "error": str(exc)}

        message = data.get("choices", [{}])[0].get("message", {})
        audio_data = (message.get("audio") or {}).get("data", "")
        if not audio_data:
            return {"ok": False, "provider": provider_id, "error": str(data)[:500]}
        try:
            audio = base64.b64decode(audio_data)
        except Exception:
            return {"ok": False, "provider": provider_id, "error": "invalid_base64_audio"}
        result = self._write_audio(audio, ".wav")
        return {"ok": True, "provider": provider_id, "text": text, **result}

    async def _speak_gpt_sovits(self, text: str, provider_id: str, provider: dict[str, Any], voice: str) -> dict[str, Any]:
        base_url = str(provider.get("base_url", "http://127.0.0.1:9880")).rstrip("/")
        if not base_url:
            return {"ok": False, "provider": provider_id, "error": "missing_base_url"}

        extra = provider.get("extra", {})
        if not isinstance(extra, dict):
            extra = {}
        ref_audio_path = str(extra.get("ref_audio_path") or voice or "").strip()
        prompt_text = str(extra.get("prompt_text") or "").strip()
        text_lang = str(extra.get("text_lang") or "zh").strip().lower()
        prompt_lang = str(extra.get("prompt_lang") or "zh").strip().lower()
        media_type = str(extra.get("media_type") or "wav").strip().lower()
        if not ref_audio_path:
            return {
                "ok": False,
                "provider": provider_id,
                "error": "missing_ref_audio_path",
                "hint": "GPT-SoVITS 需要参考音频路径；把 ref_audio_path 填到高级参数 JSON，或临时填在 voice 字段。",
            }
        if not prompt_lang or not text_lang:
            return {"ok": False, "provider": provider_id, "error": "missing_language"}

        payload: dict[str, Any] = {
            "text": text,
            "text_lang": text_lang,
            "ref_audio_path": ref_audio_path,
            "prompt_text": prompt_text,
            "prompt_lang": prompt_lang,
            "text_split_method": str(extra.get("text_split_method") or "cut5"),
            "batch_size": int(extra.get("batch_size") or 1),
            "media_type": media_type,
            "streaming_mode": extra.get("streaming_mode", False),
        }
        for key in (
            "aux_ref_audio_paths",
            "top_k",
            "top_p",
            "temperature",
            "batch_threshold",
            "split_bucket",
            "speed_factor",
            "fragment_interval",
            "seed",
            "parallel_infer",
            "repetition_penalty",
            "sample_steps",
            "super_sampling",
            "overlap_length",
            "min_chunk_length",
        ):
            if key in extra:
                payload[key] = extra[key]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/tts",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    content_type = resp.headers.get("Content-Type", "")
                    if resp.status >= 400:
                        try:
                            data = await resp.json()
                        except Exception:
                            data = {"message": await resp.text()}
                        return {"ok": False, "provider": provider_id, "error": data.get("message", data)}
                    if content_type.startswith("audio/"):
                        audio = await resp.read()
                    else:
                        try:
                            data = await resp.json()
                        except Exception:
                            data = {"message": await resp.text()}
                        return {"ok": False, "provider": provider_id, "error": data.get("message", data)}
        except aiohttp.ClientConnectorError:
            return {
                "ok": False,
                "provider": provider_id,
                "error": "gpt_sovits_not_running",
                "hint": "请先启动 GPT-SoVITS API：scripts/start_gpt_sovits_api.ps1",
            }
        except Exception as exc:
            return {"ok": False, "provider": provider_id, "error": str(exc)}

        suffix = f".{media_type}" if media_type in {"wav", "ogg", "aac", "raw"} else ".wav"
        result = self._write_audio(audio, suffix)
        return {"ok": True, "provider": provider_id, "text": text, "ref_audio_path": ref_audio_path, **result}

    async def _speak_http(self, text: str, provider_id: str, provider: dict[str, Any], voice: str) -> dict[str, Any]:
        service_url = str(provider.get("base_url", "")).strip()
        if not service_url:
            return {"ok": False, "provider": provider_id, "error": "missing_base_url"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    service_url,
                    json={"text": text, "voice": voice, "model": provider.get("model", "")},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    content_type = resp.headers.get("Content-Type", "")
                    if content_type.startswith("audio/"):
                        suffix = ".mp3" if "mpeg" in content_type or "mp3" in content_type else ".wav"
                        result = self._write_audio(await resp.read(), suffix)
                        return {"ok": True, "provider": provider_id, "text": text, **result}
                    data = await resp.json()
        except Exception as exc:
            return {"ok": False, "provider": provider_id, "error": str(exc)}

        if data.get("audio_url"):
            return {"ok": True, "provider": provider_id, "audio_url": data["audio_url"], "text": text}
        if data.get("audio"):
            try:
                audio = base64.b64decode(data["audio"])
            except Exception:
                return {"ok": False, "provider": provider_id, "error": "invalid_base64_audio"}
            result = self._write_audio(audio, ".mp3")
            return {"ok": True, "provider": provider_id, "text": text, **result}
        return {"ok": False, "provider": provider_id, "error": data.get("error", "unsupported_response")}
