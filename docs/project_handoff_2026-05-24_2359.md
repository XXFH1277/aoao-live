# 螯螯数字人直播项目交接说明

**记录时间**：2026-05-24 23:59:33 +08:00  
**记录目的**：用于项目交接、恢复开发、核对当前进度。  
**当前浏览器页面**：`http://127.0.0.1:5173/#/persona`

---

## 一、当前状态

本轮已经停止继续开发。最后一次正在执行的 GPT-SoVITS 安装流程已被中止，停止点在 Miniforge 安装阶段。GPT-SoVITS 源码已下载，但运行环境、预训练模型和 API 服务尚未完成安装。

当前系统已经具备：

- FastAPI 后端：`http://127.0.0.1:8787`
- Vue/Vite 前端：`http://127.0.0.1:5173`
- OBS overlay：`http://127.0.0.1:8787/overlay`
- TTS provider 路由框架
- MiniMax、MiMo、自定义 OpenAI 兼容语音接口入口
- 本地 GPT-SoVITS provider 入口

---

## 二、已经完成的内容

### 1. GPT-SoVITS 官方依据核对

已参考官方仓库和 `api_v2.py`，确认当前本地 API 接入方式：

- 官方仓库：https://github.com/RVC-Boss/GPT-SoVITS
- 官方 API 文件：https://github.com/RVC-Boss/GPT-SoVITS/blob/main/api_v2.py
- API 启动示例：`python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml`
- TTS endpoint：`POST /tts`
- 必填字段：`text`、`text_lang`、`ref_audio_path`、`prompt_lang`
- 成功返回：音频流
- 失败返回：JSON 错误

### 2. 源码下载

已将官方 GPT-SoVITS 仓库克隆到：

```text
E:\数字人直播\vendor\GPT-SoVITS
```

该目录已加入 `.gitignore`，不作为当前控制台项目源码提交。

### 3. 后端接入

已新增 `gpt_sovits_api` 类型的 TTS provider。

后端现在可以：

- 在 `/api/v1/tts/status` 返回 `gpt_sovits` provider
- 保存 GPT-SoVITS 的 base URL、voice、extra JSON 配置
- 调用本地 GPT-SoVITS `/tts`
- 将返回音频保存到 `data/tts/`
- 在 GPT-SoVITS 未启动时返回明确错误：`gpt_sovits_not_running`

### 4. 前端接入

在 `#/persona` 的“声音”区域：

- 可以选择“本地 GPT-SoVITS”
- 选择后显示高级参数 JSON 输入框
- 可填写 `ref_audio_path`、`prompt_text`、`text_lang`、`prompt_lang`
- 可以点击“保存声音配置”
- 可以点击“生成试听”

### 5. 安装脚本和启动脚本

已新增：

```text
scripts/install_gpt_sovits_windows.ps1
scripts/start_gpt_sovits_api.ps1
```

安装脚本目标：

- 下载 Miniforge
- 创建 Python 3.10 Conda 环境
- 调用 GPT-SoVITS 官方 `install.ps1`
- 安装 PyTorch CUDA 12.8、依赖、预训练模型、G2PW 字典等

启动脚本目标：

- 使用独立 Python 环境启动 `api_v2.py`
- 监听 `http://127.0.0.1:9880`

### 6. 验证结果

已验证：

- `backend/services/tts.py`、`backend/api/tts.py` Python 编译通过
- `frontend` 执行 `npm run build` 通过
- 后端重启后 `/api/v1/tts/status` 能看到 `gpt_sovits`
- 前端代理 `/api/v1/tts/status` 正常
- 调用 GPT-SoVITS provider 时，在 API 未启动状态下返回预期错误

---

## 三、修改过的文件

```text
backend/services/tts.py
backend/api/tts.py
configs/integrations.json
frontend/src/views/Persona.vue
.gitignore
scripts/install_gpt_sovits_windows.ps1
scripts/start_gpt_sovits_api.ps1
docs/gpt_sovits_local.md
```

本次为交接新增：

```text
docs/project_handoff_2026-05-24_2359.md
```

---

## 四、还没完成的任务

### 1. GPT-SoVITS 本地安装未完成

安装命令已开始执行，但按用户要求停止继续开发后已中止：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_gpt_sovits_windows.ps1 -Device CU128 -Source ModelScope
```

停止点：

```text
[GPT-SoVITS] Installing Miniforge into C:\tmp\aoao-gpt-sovits\miniforge3 ...
Miniforge installer failed with exit code -1
```

这是因为安装进程被主动中止，不代表脚本逻辑已经验证失败。

### 2. GPT-SoVITS API 尚未启动

尚未能执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_gpt_sovits_api.ps1
```

因此当前还不能真正生成 GPT-SoVITS 语音。

### 3. 螯螯声音样本尚未接入

还需要准备：

- 参考音频文件，例如 `E:/voice/aoao.wav`
- 参考音频对应文本
- 语言参数：`zh`

### 4. 声音到数字人口型/OBS 的完整链路未完成

目前只做到 TTS provider 接入层。还没完成：

- GPT-SoVITS 实际合成
- 合成音频播放/队列
- 音频驱动数字人口型
- 数字人画面进入 OBS

---

## 五、下一步从哪里继续

推荐恢复顺序：

1. 检查并清理安装残留：

```powershell
Test-Path C:\tmp\aoao-gpt-sovits
Test-Path installer\Miniforge3-Windows-x86_64.exe
```

如果 Miniforge 安装不完整，删除 `C:\tmp\aoao-gpt-sovits` 后重装。

2. 重新执行 GPT-SoVITS 安装：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_gpt_sovits_windows.ps1 -Device CU128 -Source ModelScope
```

3. 启动 GPT-SoVITS API：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_gpt_sovits_api.ps1
```

4. 打开中控台：

```text
http://127.0.0.1:5173/#/persona
```

选择“本地 GPT-SoVITS”，填写高级参数：

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

5. 点击“生成试听”，确认能生成音频。

6. 如果启动慢或爆显存，优先卸载/停止 Ollama 当前模型。此前观察到 RTX 4070 Ti SUPER 16GB 显存中，Ollama 和其他进程占用较高。

---

## 六、项目交接规则

以后每次用户要求“停止继续开发”“暂停”“交接”“总结当前进度”时，必须输出并优先更新一份交接说明，包含：

1. 记录日期和时间，使用本机时区。
2. 当前完成内容。
3. 修改过的文件。
4. 尚未完成的任务。
5. 验证过的结果。
6. 失败/中断/风险点。
7. 下一步从哪里继续，给出可执行命令或具体页面。

交接文档建议放在：

```text
docs/project_handoff_YYYY-MM-DD_HHMM.md
```

如果只是小更新，也可以追加到最新的 `docs/project_handoff_*.md`。

---

## 七、重要注意事项

- 继续安装 GPT-SoVITS 会下载较大的依赖和模型，耗时可能较长。
- 当前机器没有系统级 `ffmpeg`，安装脚本计划通过 Conda 环境安装。
- 当前机器没有 Docker 命令，因此数字人形象层仍未接入。
- 普通 `python` / `py` 命令在当前 shell 中存在“指定的登录会话不存在”异常；当前项目后端使用的是 Codex bundled Python。
- GPT-SoVITS 建议使用独立 Conda/Miniforge 环境，不要污染当前 FastAPI 后端环境。
