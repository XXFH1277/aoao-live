# 接入路线图：OBS、Ollama、数字人、声音

更新日期：2026-05-24

## 当前已接入

| 模块 | 状态 | 说明 |
|---|---|---|
| OBS 浏览器源 | 已接入 | `/overlay` 可作为 OBS 字幕和 AI 标识源 |
| OBS WebSocket | 已接入 | 页面内可连接 OBS、创建/刷新字幕源 |
| Ollama 本地模型 | 已接入 | 默认模型 `gemma4:e4b`，用于模拟弹幕的非高风险回复 |
| 规则兜底 | 已接入 | 身份、售后、价格、库存、发货等问题优先走模板或真人接管 |

## Ollama 使用边界

本机 `gemma4:e4b` 可用，但实测一次短回答约 47 秒，不适合实时弹幕抢答。

推荐用法：

- 常见问题：走模板，立即答。
- 高风险问题：走真人助理接管。
- Ollama：用于离线生成话术、FAQ、复盘建议，或不追求实时的弹幕回复。

配置文件：`configs/integrations.json`

```json
{
  "ollama": {
    "enabled": true,
    "base_url": "http://127.0.0.1:11434",
    "model": "gemma4:e4b",
    "timeout_seconds": 60
  }
}
```

## 数字人接入

推荐路线：Duix Avatar / HeyGem successor。

当前缺口：

- 需要 Docker Desktop。
- 需要下载数字人服务镜像。
- 需要准备螯螯形象素材。
- 需要确定输出方式：预生成视频、虚拟摄像头、窗口采集、RTMP/WebRTC。

第一阶段最稳方案：

1. 安装 Docker Desktop 并确认 `docker --version` 可用。
2. 部署 Duix Avatar 服务。
3. 先用一段固定台词生成螯螯视频。
4. OBS 用“媒体源”或“窗口采集”接数字人画面。
5. 现有 `/overlay` 继续负责 AI 标识、字幕和真人监管提示。

不要一开始追实时数字人。先跑通“台词 → 声音 → 数字人视频 → OBS 画面”。

## 声音接入

推荐两步：

1. 占位声音：先用 Duix 自带声音能力、系统 TTS 或预生成音频，让链路跑通。
2. 克隆声音：再接 GPT-SoVITS 或 CosyVoice。

声音服务最终需要提供一个本地 HTTP 接口：

```text
POST /tts
输入：文本
输出：wav/mp3 文件路径或音频流
```

中控台后续接法：

```text
弹幕/话术
→ 规则或 Ollama 生成回复
→ TTS 生成音频
→ 数字人服务生成口型/视频
→ OBS 展示画面和字幕
```

## 推荐下一步

1. 先确认 OBS WebSocket 能在中控台显示“已连接”。
2. 用“创建字幕源”自动把 overlay 加到 OBS。
3. 安装 Docker Desktop。
4. 部署 Duix Avatar，先生成一条“螯螯开场白”视频。
5. 把视频源加到 OBS，形成第一个可录屏 Demo。
