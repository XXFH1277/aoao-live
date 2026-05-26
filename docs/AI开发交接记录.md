---

## 2026-05-26 10:30｜Codex｜feature/api-first-mvp

### 本次修改

- 按顶层 4 份开发文档要求，将第一阶段方向调整为“本地 Web 原型 + LLM/TTS 优先走 API 测试”。
- 新增 LLM API 连通测试接口 `/api/v1/llm/test`，可在后台“全局设置”里保存模型配置后直接测试当前供应商。
- 修正 MiMo LLM 配置，使用接口实际返回的模型 ID：`mimo-v2.5-pro`。
- 新增 MiMo TTS 专用调用类型 `mimo_tts_chat`，按官方兼容接口从 `/chat/completions` 返回的 `message.audio.data` 解析音频。
- 修正 MiMo TTS 默认模型和音色为 `mimo-v2.5-tts`、`mimo_default`。
- 修复浏览器录音上传 `.webm` 文件被后端拒绝的问题。
- 更新密钥示例结构，区分 `llm_api_keys` 和 `tts_api_keys`。
- 将 `.venv/` 和 `frontend/node_modules/` 加入 `.gitignore`，避免提交本地依赖目录。

### 修改文件

- `.gitignore`
- `backend/api/llm.py`
- `backend/api/tts.py`
- `backend/core/live_state.py`
- `backend/core/llm_router.py`
- `backend/services/tts.py`
- `configs/integrations.json`
- `configs/secrets.local.example.json`
- `frontend/src/stores/liveStore.ts`
- `frontend/src/views/Settings.vue`

### 新增文件

- `docs/AI开发交接记录.md`

### 未提交到 Git 的本地文件

- `configs/secrets.local.json`：保存本机 API Key，已被 `.gitignore` 忽略，不能提交。
- `.venv/`：本机 Python 虚拟环境，已被 `.gitignore` 忽略。
- `data/tts/`：TTS 测试生成音频，已被 `.gitignore` 忽略。

### 测试结果

- `PYTHONPYCACHEPREFIX=/private/tmp/aoao_pycache .venv/bin/python -m compileall backend`：通过。
- `npm install --cache /private/tmp/aoao-npm-cache`：通过。
- `npm run build`：通过。
- 本地后端 `.venv/bin/python -m backend.main`：通过，需允许绑定 `127.0.0.1:8787`。
- MiMo LLM API 测试：通过，`mimo-v2.5-pro` 返回可播报短回复。
- MiMo TTS API 测试：通过，生成 `tts-1779763668-b10e7092.wav`，约 307KB。
- Kimi API 测试：失败，接口返回 `Invalid Authentication`，疑似当前 Kimi Key 无效或权限不对。

### GitHub 状态

- 当前分支：`feature/api-first-mvp`
- 计划提交信息：`feat: add api-first llm and tts testing`
- 是否合并到 `main`：否

### 下一步

- 回家后先运行 `git fetch origin`，再切到 `feature/api-first-mvp` 继续。
- 建议下一步补“模型配置/调用日志”页面里的调用记录展示。
- 暂时不要把 `configs/secrets.local.json` 提交到 GitHub。
- 如果要继续用 Kimi，需要重新生成或检查 Kimi API Key。
