# Phase 2 TTS 语音合成交接文档

**项目**：螯螯数字人直播系统  
**阶段**：Phase 2 TTS 主链路集成  
**日期**：2026-05-25 21:00  
**状态**：✅ 核心链路已完成

---

## 一、完成内容

### 1.1 TTS 服务层（协作者已完成）

`backend/services/tts.py` — 6 种供应商适配器：

| 供应商 | 类型 | 状态 |
|---|---|---|
| Windows SAPI | 本地系统语音 | ✅ 可用（自动选择中文语音） |
| GPT-SoVITS | 本地 API | ✅ 适配器就绪，需启动 api_v2.py |
| MiniMax T2A | 云端 API | ✅ 适配器就绪，需 API Key |
| MiMo TTS | 云端 API | ✅ 适配器就绪，需 API Key |
| 自定义 OpenAI | 云端 API | ✅ 适配器就绪 |
| 自定义 HTTP | 通用 | ✅ 适配器就绪 |

### 1.2 主链路自动 TTS（本轮完成）

| 触发点 | 行为 | 状态 |
|---|---|---|
| 话术轮播 `next_line()` | 自动调 TTS → WebSocket 广播 `tts_audio` | ✅ |
| 弹幕回复 `handle_danmaku()` | 回复后自动调 TTS（handoff 跳过） | ✅ |
| 真人助理接管 `handle_assistant_reply()` | 接管文本自动 TTS | ✅ |
| 试听 `POST /api/v1/tts/speak` | 手动触发，返回 audio_url | ✅ |

### 1.3 前端音频播放（本轮完成）

| 功能 | 说明 | 状态 |
|---|---|---|
| WebSocket 接收 `tts_audio` 事件 | `liveStore.ts` 自动播放 | ✅ |
| TTS 开关 | ScriptPanel 中可切换 `ttsAutoPlay` | ✅ |
| 音频播放器 | ScriptPanel 显示当前音频 `<audio>` 控件 | ✅ |
| 试听自动播放 | Persona 页面 `<audio autoplay>` | ✅ |
| OBS Overlay 音频 | overlay 接收 `tts_audio` 自动播放 | ✅ |

### 1.4 Bug 修复

| 问题 | 修复 |
|---|---|
| Windows SAPI 空 voice 时默认选英文语音 | 自动检测并选择 `zh-*` 语音 |
| Vite proxy 不转发 `/media` 路径 | vite.config.ts 加 `/media` proxy |

---

## 二、修改的文件清单

| 文件 | 变更 |
|---|---|
| `backend/core/live_state.py` | 新增 `tts_enabled`、`_auto_tts()`；`next_line()`、`handle_danmaku()`、`handle_assistant_reply()` 末尾调用 `_auto_tts()` |
| `backend/services/tts.py` | `_speak_windows_sapi()` 修复：无 voice 时自动选择中文语音 |
| `frontend/vite.config.ts` | proxy 加 `'/media': 'http://127.0.0.1:8787'` |
| `frontend/src/stores/liveStore.ts` | 新增 `lastAudioUrl`、`ttsAutoPlay`、`_playAudio()`；WebSocket 处理 `tts_audio` 事件 |
| `frontend/src/components/ScriptPanel.vue` | 新增 TTS 开关 + 音频播放器 |
| `frontend/src/views/Persona.vue` | `<audio>` 加 `autoplay` |
| `overlay/index.html` | 处理 `tts_audio` 事件自动播放 |

---

## 三、验证结果

| 验证项 | 结果 |
|---|---|
| `npm run build` 零错误 | ✅ 183ms |
| Windows SAPI 中文语音生成 | ✅ 53-581KB WAV |
| next_line 自动触发 TTS | ✅ generated_count 递增 |
| 弹幕回复自动触发 TTS | ✅ generated_count 递增 |
| WebSocket 推送 `tts_audio` 到前端 | ✅ `lastAudioUrl` 有值 |
| 前端 audio 控件显示 | ✅ `hasAudioPlayer: true` |
| TTS 开关可切换 | ✅ `hasTtsToggle: true` |
| `/media/tts/*.wav` 通过 proxy 可访问 | ✅ 200, audio/wav |
| 后端直接托管也可访问 | ✅ :8787/media/tts/ |

---

## 四、已知限制

1. **浏览器自动播放策略**：首次访问页面时浏览器可能阻止自动播放音频，需用户先交互（点击任意按钮）后才能 autoplay
2. **Windows SAPI 音质一般**：系统自带 Huihui 语音仅做过渡，正式环境应切 GPT-SoVITS 或云端 TTS
3. **TTS 是同步阻塞**：每句话术要等 TTS 生成完再广播，长文本可能有 3-5 秒延迟
4. **无音频队列**：如果话术轮播过快，新音频会打断上一段。后续应加播放队列

---

## 五、下一步

| 任务 | 说明 |
|---|---|
| Phase 3 数字人渲染 | 音频驱动唇形同步（HeyGem / DH_live） |
| TTS 队列机制 | 播放队列 + 等上一段播完再推下一句 |
| GPT-SoVITS 实测 | 启动 api_v2.py，配置 ref_audio，测试克隆效果 |
| 云端 TTS 配通 | MiniMax / MiMo 填入 API Key 测试 |
