<script setup lang="ts">
import { ref } from 'vue'

const password = ref('')
const statusTag = ref<'todo' | 'ok'>('todo')
const statusLabel = ref('待连接')
const log = ref('等待连接 OBS...')
let obsWs: WebSocket | null = null

function appendLog(msg: string) {
  log.value += '\n' + msg
}

function connectObs() {
  if (!password.value) { appendLog('请输入 OBS WebSocket 密码'); return }
  try {
    obsWs = new WebSocket('ws://127.0.0.1:4455')
    obsWs.onopen = () => {
      appendLog('已连接 OBS WebSocket')
      statusTag.value = 'ok'
      statusLabel.value = '已连接'
    }
    obsWs.onclose = () => {
      appendLog('OBS 连接已断开')
      statusTag.value = 'todo'
      statusLabel.value = '待连接'
    }
    obsWs.onerror = () => appendLog('OBS 连接错误')
  } catch (e) {
    appendLog('连接失败: ' + String(e))
  }
}
</script>

<template>
  <section class="bg-paper border border-[#d8e2de] rounded-lg p-4 shadow-[0_8px_24px_rgba(18,31,27,.05)]">
    <div class="flex justify-between items-start gap-3 mb-3.5">
      <div>
        <h2 class="m-0 text-[17px] font-bold">OBS 与开播工具</h2>
        <p class="mt-1.5 text-muted text-sm">连接 OBS 后可自动创建字幕源、刷新 overlay，后续可扩展切场景和录制。</p>
      </div>
      <span
        class="rounded-full px-2 py-1 text-xs font-bold"
        :class="statusTag === 'ok' ? 'bg-green-soft text-green' : 'bg-amber-soft text-amber'"
      >
        {{ statusLabel }}
      </span>
    </div>

    <div class="grid grid-cols-2 gap-2 max-[920px]:grid-cols-1">
      <input
        v-model="password"
        type="password"
        autocomplete="current-password"
        class="px-3 py-3 border border-[#c8d4cf] rounded-md text-sm"
        placeholder="输入 OBS WebSocket 密码"
      />
      <button @click="connectObs" class="px-3.5 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm">连接 OBS</button>
      <button class="px-3.5 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm">创建字幕源</button>
      <button class="px-3.5 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm">刷新字幕源</button>
    </div>

    <div class="mt-3 min-h-[74px] max-h-[120px] overflow-auto bg-[#f7faf8] border border-line rounded-md p-2.5 text-muted text-xs leading-[1.45] whitespace-pre-wrap">
      {{ log }}
    </div>
  </section>
</template>
