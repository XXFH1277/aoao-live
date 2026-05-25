<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useLiveStore } from '../stores/liveStore'

const store = useLiveStore()

onMounted(() => store.fetchState())

const form = ref({
  provider_id: '',
  model: '',
  base_url: '',
  api_key: '',
})

const providers = computed(() => store.providers)
const activeId = computed(() => store.activeProviderId)
const activeProvider = computed(() => providers.value[activeId.value] ?? {})

const providerEntries = computed(() => Object.entries(providers.value))

function syncFields() {
  const p = providers.value[form.value.provider_id] ?? {}
  form.value.model = (p as any).model ?? ''
  form.value.base_url = (p as any).base_url ?? ''
  form.value.api_key = ''
}

onMounted(() => {
  form.value.provider_id = activeId.value
  syncFields()
})

async function saveProvider() {
  await store.updateLlmProvider(form.value)
}

const apiKeyStatus = computed(() => {
  const p = activeProvider.value as any
  if (!p.api_key_required) return { label: '本地模型无需密钥', ok: true }
  return p.api_key_saved
    ? { label: '密钥已保存', ok: true }
    : { label: '等待填写密钥', ok: false }
})

const providerTypeLabel = computed(() => {
  const p = activeProvider.value as any
  return p.type === 'ollama' ? '本地 Ollama' : 'OpenAI 兼容接口'
})
</script>

<template>
  <header class="px-7 py-5.5 bg-[#f9fbfa] border-b border-line">
    <h1 class="text-[28px] leading-tight m-0">全局设置</h1>
    <div class="mt-2 text-muted text-sm">跨直播间复用的配置：模型、OBS、平台、合规和日志。</div>
  </header>

  <div class="px-7 py-4.5 max-[920px]:px-4">
    <div class="grid grid-cols-[minmax(360px,1.45fr)_minmax(260px,.85fr)] gap-3.5 items-start max-[920px]:grid-cols-1">
      <!-- Model routing -->
      <div class="bg-white border border-[#d8e2de] rounded-lg p-4">
        <h3 class="m-0 mb-2.5 text-base font-bold">模型路由</h3>

        <div class="flex items-center justify-between gap-3 p-3 border border-[#dce6e2] rounded-lg bg-[#f7faf8] my-2.5">
          <div>
            <strong class="block text-[15px]">{{ (activeProvider as any).label ?? activeId }}</strong>
            <span class="block mt-0.5 text-muted text-xs">{{ providerTypeLabel }} · {{ (activeProvider as any).model || '未配置模型' }}</span>
          </div>
          <span
            class="rounded-full px-2 py-1 text-xs font-bold"
            :class="apiKeyStatus.ok ? 'bg-green-soft text-green' : 'bg-amber-soft text-amber'"
          >
            {{ apiKeyStatus.label }}
          </span>
        </div>

        <form @submit.prevent="saveProvider" class="grid grid-cols-2 gap-3 max-[920px]:grid-cols-1">
          <div class="grid gap-1.5">
            <label class="text-muted text-xs font-extrabold">供应商</label>
            <select
              v-model="form.provider_id"
              @change="syncFields"
              class="w-full min-h-[38px] border border-[#c8d4cf] rounded-md px-2.5 bg-white"
            >
              <option v-for="[id, p] in providerEntries" :key="id" :value="id">
                {{ (p as any).label ?? id }}
              </option>
            </select>
          </div>
          <div class="grid gap-1.5">
            <label class="text-muted text-xs font-extrabold">模型名</label>
            <input v-model="form.model" class="w-full px-3 py-3 border border-[#c8d4cf] rounded-md text-sm" placeholder="deepseek-chat / qwen-plus / gemma4:e4b" />
          </div>
          <div class="col-span-2 max-[920px]:col-span-1 grid gap-1.5">
            <label class="text-muted text-xs font-extrabold">Base URL</label>
            <input v-model="form.base_url" class="w-full px-3 py-3 border border-[#c8d4cf] rounded-md text-sm" placeholder="https://api.example.com/v1" />
          </div>
          <div class="col-span-2 max-[920px]:col-span-1 grid gap-1.5">
            <label class="text-muted text-xs font-extrabold">API Key</label>
            <input v-model="form.api_key" type="password" autocomplete="off" class="w-full px-3 py-3 border border-[#c8d4cf] rounded-md text-sm" placeholder="已保存则留空；本地 Ollama 不需要" />
          </div>
          <div class="col-span-2 max-[920px]:col-span-1 flex items-center gap-2.5 flex-wrap">
            <button type="submit" class="px-3.5 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm">保存并切换</button>
            <span
              class="rounded-full px-2 py-1 text-xs font-bold"
              :class="(store.state.knowledge?.embeddings ?? 0) ? 'bg-green-soft text-green' : 'bg-amber-soft text-amber'"
            >
              RAG：{{ (store.state.knowledge?.embeddings ?? 0) ? `${store.state.knowledge.embeddings} 条索引` : '未索引' }}
            </span>
          </div>
        </form>

        <div class="mt-3 p-2.5 rounded-lg bg-[#f1f6f3] text-[#4d5e58] text-[13px] leading-[1.55]">
          后续接 DeepSeek、Kimi、Qwen、MiMo 或中转站，只要它是 OpenAI 兼容的 <code class="bg-[#edf2ef] px-1.5 py-0.5 rounded text-sm">/chat/completions</code> 接口，就能走这里。
        </div>
      </div>

      <!-- Right column -->
      <div class="grid gap-3.5">
        <div class="bg-white border border-[#d8e2de] rounded-lg p-4">
          <h3 class="m-0 mb-2.5 text-base font-bold">可用供应商</h3>
          <div class="grid gap-2 mt-2.5">
            <div
              v-for="[id, p] in providerEntries"
              :key="id"
              class="flex justify-between gap-2.5 items-center p-2.5 rounded-lg border border-[#e1e9e5] bg-[#fbfcfb] text-[13px]"
            >
              <div>
                <strong class="block">{{ (p as any).label ?? id }}</strong>
                <span class="text-muted text-xs">{{ (p as any).model || '未配置' }}</span>
              </div>
              <span
                class="rounded-full px-2 py-1 text-xs font-bold"
                :class="id === activeId ? 'bg-green-soft text-green' : 'bg-amber-soft text-amber'"
              >
                {{ id === activeId ? '当前' : '可选' }}
              </span>
            </div>
          </div>
        </div>

        <div class="bg-white border border-[#d8e2de] rounded-lg p-4">
          <h3 class="m-0 mb-2.5 text-base font-bold">平台设置</h3>
          <div class="flex justify-between py-1.5 border-b border-[#e7ece9] text-[13px]">
            <span class="text-muted">平台</span><strong>抖音</strong>
          </div>
          <div class="flex justify-between py-1.5 border-b border-[#e7ece9] text-[13px]">
            <span class="text-muted">弹幕捕获</span><strong>待接入</strong>
          </div>
          <div class="flex justify-between py-1.5 text-[13px]">
            <span class="text-muted">推流方式</span><strong>OBS</strong>
          </div>
        </div>

        <div class="bg-white border border-[#d8e2de] rounded-lg p-4">
          <h3 class="m-0 mb-2.5 text-base font-bold">合规设置</h3>
          <div class="flex justify-between py-1.5 border-b border-[#e7ece9] text-[13px]">
            <span class="text-muted">显式标识</span><strong>已启用</strong>
          </div>
          <div class="flex justify-between py-1.5 border-b border-[#e7ece9] text-[13px]">
            <span class="text-muted">真人监管</span><strong>已启用</strong>
          </div>
          <div class="flex justify-between py-1.5 text-[13px]">
            <span class="text-muted">隐式标识</span><strong>待补齐</strong>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
