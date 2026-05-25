# Phase 1 前端开发交接文档

**项目**：螯螯数字人直播系统  
**阶段**：Phase 1 前端（Vue3 + Vite + Tailwind）  
**日期**：2026-05-24 23:15（创建） / 2026-05-25 联调验证通过  
**状态**：✅ Phase 1 前端已完成，全部验收标准通过

---

## 一、背景

Phase 1 后端已完成（同日），将原单文件 `src/aoao_live_console.py`（1505行）拆分为 FastAPI 模块化架构，所有 API 端点 + WebSocket 已验证可用。

本轮任务是 Phase 1 前端：将原代码中嵌在 Python 字符串里的约 720 行 HTML/CSS/JS（`dashboard_html()` 方法，行 488-1209）迁移到独立的 Vue3 前端项目。

---

## 二、技术栈

| 技术 | 版本 | 用途 |
|---|---|---|
| Vue 3 | ^3.5.34 | 框架 |
| Vite | ^8.0.12 | 构建工具 |
| TypeScript | ~6.0.2 | 类型检查 |
| Pinia | ^3.0.4 | 状态管理 |
| vue-router | ^4.6.4 | 路由（Hash 模式） |
| Tailwind CSS | ^4.3.0 | 样式（v4 + @tailwindcss/vite 插件） |

---

## 三、已完成的文件清单

### 3.1 修改的文件

| 文件 | 变更说明 |
|---|---|
| `frontend/index.html` | lang 改 zh-CN，title 改"螯螯直播助理控制台" |
| `frontend/src/style.css` | 从 Vite 默认模板改为 Tailwind 导入 + 自定义主题色（ink/muted/line/paper/wash/green/coral/teal/amber 等） |
| `frontend/src/main.ts` | 加入 Pinia、vue-router，注册 5 条路由 |
| `frontend/src/App.vue` | 改为侧边栏 + router-view + StatusBar 布局 |

### 3.2 新建的文件

| 文件 | 说明 |
|---|---|
| **核心** | |
| `src/stores/liveStore.ts` | Pinia store：WebSocket 自动连接/重连、全局直播状态、所有 API 调用封装 |
| `src/composables/useApi.ts` | fetch 请求封装 |
| **组件** | |
| `src/components/Sidebar.vue` | 左侧导航栏：品牌标识 + 5 个路由 + 版本信息 |
| `src/components/StatusBar.vue` | 底部固定开播工具栏：平台、直播间地址、弹幕捕获、开播按钮 |
| `src/components/ScriptPanel.vue` | 话术面板：当前口播文本、步骤进度条、运行元信息 |
| `src/components/DanmakuQueue.vue` | 弹幕互动：模拟弹幕输入、真人接管输入、互动记录列表 |
| `src/components/OBSControl.vue` | OBS 控制：WebSocket 连接、字幕源操作、日志输出 |
| **页面** | |
| `src/views/Dashboard.vue` | 工作台：直播间卡片列表 + 创建直播间三步流程 |
| `src/views/LiveRoom.vue` | 直播间详情：三栏布局（左-预览资产 / 中-脚本互动OBS / 右-接入状态设置） |
| `src/views/Knowledge.vue` | 知识库管理：统计指标、添加条目表单、知识条目表格、RAG 重建 |
| `src/views/Persona.vue` | 数字人资产：形象预览 + 人设编辑表单（定位/口吻/字数/规则） |
| `src/views/Settings.vue` | 全局设置：模型路由表单 + 供应商列表 + 平台/合规信息 |

### 3.3 删除的文件

| 文件 | 说明 |
|---|---|
| `src/components/HelloWorld.vue` | Vite 脚手架模板文件，已清理 |

### 3.4 未清理（可后续处理）

| 文件 | 说明 |
|---|---|
| `src/assets/vite.svg` | Vite 模板遗留 |
| `src/assets/vue.svg` | Vite 模板遗留 |
| `src/assets/hero.png` | Vite 模板遗留 |

---

## 四、原 HTML 到 Vue 组件的映射关系

| 原 HTML section / id | 对应 Vue 文件 |
|---|---|
| `.sidebar` + `.nav` | `Sidebar.vue` |
| `.launchbar` | `StatusBar.vue` |
| `#rooms`（直播间卡片）| `Dashboard.vue` |
| `#create-room`（创建流程）| `Dashboard.vue`（下半部分）|
| `#script`（脚本编排）| `LiveRoom.vue` > `ScriptPanel.vue` |
| `#knowledge`（商品知识库指标）| `LiveRoom.vue`（内嵌）+ `Knowledge.vue` |
| `#guard`（保护配置）| `LiveRoom.vue`（内嵌）|
| `#interaction`（知识条目表格）| `Knowledge.vue` |
| 主动互动控制（弹幕/接管）| `DanmakuQueue.vue` |
| `#obs`（OBS 工具）| `OBSControl.vue` |
| 右侧栏（接入状态 + 直播设置）| `LiveRoom.vue`（内嵌 aside）|
| `#digital-human`（数字人资产）| `Persona.vue` |
| `#settings`（全局设置）| `Settings.vue` |

---

## 五、架构说明

### 5.1 路由（Hash 模式）

```
/           → Dashboard.vue    工作台
/room       → LiveRoom.vue     直播间详情
/knowledge  → Knowledge.vue    商品知识
/persona    → Persona.vue      数字人资产
/settings   → Settings.vue     全局设置
```

### 5.2 状态管理（liveStore）

- WebSocket 连接 `ws://host/ws`，自动重连（3秒间隔）
- 接收 `state_update` 和 `danmaku_reply` 事件，更新全局状态
- 发送 `danmaku` / `assistant_reply` / `next_line` / `pause` / `resume` 动作
- API 调用：`fetchState()`、`fetchPersona()`、`updateLlmProvider()`、`updatePersona()`、`addKnowledge()`、`rebuildRag()`

### 5.3 开发代理

```typescript
// vite.config.ts
proxy: {
  '/api': 'http://127.0.0.1:8787',
  '/ws': { target: 'ws://127.0.0.1:8787', ws: true },
  '/overlay': 'http://127.0.0.1:8787',
}
```

### 5.4 主题色系统

原 HTML 使用 CSS 变量（`--ink`、`--muted`、`--green` 等），已迁移为 Tailwind v4 `@theme` 自定义颜色，使用方式如 `text-muted`、`bg-green-soft`、`border-line`。

---

## 六、验证结果（2026-05-25）

### 6.1 构建验证 ✅

```
npm run build → vue-tsc -b && vite build
✓ 56 modules transformed
dist/index.html                   0.47 kB
dist/assets/index-DrfgZbLa.css   22.18 kB
dist/assets/index-Jjt2-wpv.js   141.16 kB
✓ built in 179ms — 零错误
```

### 6.2 联调验证 ✅

| 验证项 | 结果 |
|---|---|
| 后端启动 `python -m backend.main` | ✅ Uvicorn 监听 127.0.0.1:8787 |
| 前端启动 `npm run dev` | ✅ Vite 监听 localhost:5173 |
| Vite proxy → 后端 API | ✅ `/api/v1/state` 通过 5173 正确转发 |
| Vite proxy → 后端 TTS API | ✅ `/api/v1/tts/status` 正确返回 6 个供应商 |
| WebSocket 实时连接 | ✅ `store.connected = true`，话术自动轮播 |
| 暂停/继续 API | ✅ pause → running=false，resume → running=true |
| 下一句/弹幕 API | ✅ 正常推进话术，弹幕触发 LLM 回复 |
| LLM 弹幕回复（Ollama） | ✅ gemma4:e4b 在线，带 RAG 检索生成回复 |
| 生产构建托管 | ✅ 后端 `http://127.0.0.1:8787/` 返回 Vue 应用 |

### 6.3 页面渲染验证 ✅

| 页面 | 路由 | 验证内容 |
|---|---|---|
| 工作台 | `#/` | 直播间卡片(2张) + 创建流程(3步) + 状态显示"运行中" |
| 直播间详情 | `#/room` | 三栏布局：预览(模型gemma4:e4b) / 脚本+知识库+互动+OBS / 接入状态+设置 |
| 商品知识 | `#/knowledge` | 指标(2商品/20条目/13索引) + 添加表单 + 12行知识表格 |
| 数字人资产 | `#/persona` | 形象预览 + 人设编辑(定位/口吻/字数/规则) + TTS 配置(语速/音量) |
| 全局设置 | `#/settings` | 模型路由表单 + 7个供应商 + 平台设置 + 合规设置 |

### 6.4 已清理项

- ✅ 删除 `src/components/HelloWorld.vue`（Vite 模板）
- ✅ 删除 `src/assets/vite.svg`、`vue.svg`、`hero.png`（模板遗留）

### 6.5 额外发现：Phase 2 TTS 已部分完成

其他人已提前实现了 TTS 服务层（`backend/services/tts.py`），支持 6 种供应商，前端 Persona 页面已集成 TTS 配置 UI。详见代码审查记录。

---

## 七、下一步工作

### 7.1 Phase 2 TTS 收尾

TTS 后端和前端配置已有，但还缺：
1. **试听音频自动播放**：前端拿到 `audio_url` 后需要 `<audio>` 标签播放
2. **TTS 集成进主链路**：话术轮播 `next_line` 和弹幕回复自动走 TTS 生成音频
3. **音频推送到 OBS**：目前只写文件到 `/media/tts/`，没有推送机制

### 7.2 后续阶段

| 阶段 | 内容 | 预计周期 |
|---|---|---|
| Phase 2 | TTS 主链路集成 + 试听闭环 | 1 周（骨架已有） |
| Phase 3 | 数字人渲染接入（HeyGem / DH_live） | 2-3 周 |
| Phase 4 | 弹幕抓取 + 直播闭环 | 1-2 周 |
| Phase 5 | 商业化封装（安装包 + 授权） | 2-3 周 |
| Phase 6 | SaaS 版扩展 | 3-4 周 |

---

## 八、相关文件索引

| 文件/目录 | 说明 |
|---|---|
| `frontend/` | 前端项目根目录 |
| `backend/` | 后端项目根目录（Phase 1 后端已完成） |
| `overlay/` | OBS 浏览器源页面（独立静态文件） |
| `src/aoao_live_console.py` | 原单文件代码（保留参考，不再使用） |
| `configs/` | 配置文件（persona.json, products.yaml 等） |
| `.claude/plans/mellow-drifting-hummingbird.md` | 完整 6 阶段改造方案 |
| `docs/handoff_phase1_frontend.md` | 本文档 |
