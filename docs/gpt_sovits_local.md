# GPT-SoVITS Local Integration

Checked against the official `RVC-Boss/GPT-SoVITS` repository on 2026-05-24.

## Install

The source repo is expected at:

```powershell
E:\数字人直播\vendor\GPT-SoVITS
```

Install the isolated runtime:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_gpt_sovits_windows.ps1 -Device CU128 -Source ModelScope
```

This installs Miniforge into `C:\tmp\aoao-gpt-sovits\miniforge3`, creates a Python 3.10 env at `C:\tmp\aoao-gpt-sovits\envs\GPTSoVits`, then runs the official `install.ps1`.

## Start API

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_gpt_sovits_api.ps1
```

The API listens on:

```text
http://127.0.0.1:9880
```

## Console Settings

In the app, open `数字人资产 -> 声音`, choose `本地 GPT-SoVITS`, and set:

```json
{
  "ref_audio_path": "E:/voice/aoao.wav",
  "prompt_text": "参考音频里实际说的话",
  "text_lang": "zh",
  "prompt_lang": "zh",
  "text_split_method": "cut5",
  "batch_size": 1,
  "media_type": "wav",
  "streaming_mode": false
}
```

`ref_audio_path`, `text_lang`, and `prompt_lang` are required by GPT-SoVITS `api_v2.py`. `prompt_text` should match the reference audio as closely as possible.

## Runtime Notes

- Your RTX 4070 Ti SUPER is suitable, but GPT-SoVITS and Ollama compete for VRAM. If API startup is slow or crashes, unload Ollama models first.
- `ffmpeg` is not on your system `PATH`; the installer uses conda to install it inside the GPT-SoVITS environment.
- Do not put API keys in this file. The app stores speech provider API keys in `configs/secrets.local.json`.

## Handoff Rule

When project work is paused or handed off, create or update a dated handoff document under `docs/`.

Required fields:

- Date and time, with timezone.
- Completed work.
- Changed files.
- Verification results.
- Interrupted or failed tasks.
- Remaining work.
- The exact next step to resume from.

Latest handoff:

```text
docs/project_handoff_2026-05-24_2359.md
```
