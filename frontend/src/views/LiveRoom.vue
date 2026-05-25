<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useLiveStore } from '../stores/liveStore'
import ScriptPanel from '../components/ScriptPanel.vue'
import DanmakuQueue from '../components/DanmakuQueue.vue'
import OBSControl from '../components/OBSControl.vue'

const store = useLiveStore()

onMounted(() => store.fetchState())

const ollama = computed(() => store.state.ollama)
const knowledge = computed(() => store.state.knowledge)
const activeModel = computed(() => {
  const providers = store.providers
  const pid = store.activeProviderId
  return providers[pid]?.model ?? ollama.value?.model ?? ''
})
const ollamaOk = computed(() => ollama.value?.online && ollama.value?.model_found)
const ragCount = computed(() => knowledge.value?.embeddings ?? 0)
</script>

<template>
  <header class="px-7 py-5.5 bg-[#f9fbfa] border-b border-line">
    <h1 class="text-[28px] leading-tight m-0">直播间详情：螯螯测试直播间</h1>
    <div class="mt-2 text-muted text-sm">脚本、互动、OBS 和开播控制。</div>
  </header>

  <div class="grid grid-cols-[320px_minmax(0,1fr)_300px] gap-4 px-7 items-start max-[920px]:grid-cols-1 max-[920px]:px-4">
    <!-- Left rail: preview + assets -->
    <section class="grid gap-3.5">
      <router-link to="/" class="text-muted no-underline text-[13px]">‹ 返回直播间</router-link>

      <div class="bg-white border border-line rounded-lg p-3.5">
        <div class="relative aspect-[9/14] bg-gradient-to-br from-[#06100e] via-[#0b1d19] to-[#07100e] rounded-[7px] overflow-hidden shadow-[inset_0_0_0_1px_rgba(255,255,255,.08)]">
          <div class="absolute top-3 left-3 bg-white/88 text-[#12322f] px-2 py-1.5 rounded-[5px] text-xs font-extrabold">
            AI 主播 / AI 生成
          </div>
          <div class="absolute inset-x-3 bottom-3 bg-white/90 text-[#10201e] p-2.5 rounded-md text-[13px] leading-[1.45] max-h-[120px] overflow-hidden">
            {{ store.state.current_line || '等待话术...' }}
          </div>
        </div>
      </div>

      <div class="bg-[#f7faf8] border border-line rounded-lg p-3">
        <div class="flex justify-between py-1.5 border-b border-[#e7ece9] text-[13px]">
          <span class="text-muted">数字人</span><strong>未选择</strong>
        </div>
        <div class="flex justify-between py-1.5 border-b border-[#e7ece9] text-[13px]">
          <span class="text-muted">声音</span><strong>未选择</strong>
        </div>
        <div class="flex justify-between py-1.5 border-b border-[#e7ece9] text-[13px]">
          <span class="text-muted">模型</span><strong>{{ activeModel || '未配置' }}</strong>
        </div>
        <div class="flex justify-between py-1.5 text-[13px]">
          <span class="text-muted">输出模式</span><strong>OBS 浏览器源</strong>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-2.5">
        <button class="px-3 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm">选择数字人</button>
        <button class="px-3 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm">选择声音</button>
      </div>
    </section>

    <!-- Center: main panels -->
    <section class="grid gap-3.5 min-w-0">
      <ScriptPanel />

      <!-- Knowledge + Guard 2-col -->
      <section class="bg-paper border border-[#d8e2de] rounded-lg p-4 grid grid-cols-2 gap-3.5 max-[920px]:grid-cols-1">
        <div class="border border-[#e8eeee] rounded-lg p-3.5">
          <h2 class="m-0 text-[17px] font-bold">商品知识库</h2>
          <div class="grid grid-cols-3 gap-2.5 my-3">
            <div class="bg-[#f5f8f7] rounded-[7px] p-3">
              <strong class="block text-[22px]">{{ knowledge.products ?? 0 }}</strong>
              <span class="text-muted text-xs">商品/场景</span>
            </div>
            <div class="bg-[#f5f8f7] rounded-[7px] p-3">
              <strong class="block text-[22px]">{{ knowledge.knowledge_items ?? 0 }}</strong>
              <span class="text-muted text-xs">知识条目</span>
            </div>
            <div class="bg-[#f5f8f7] rounded-[7px] p-3">
              <strong class="block text-[22px]">{{ ragCount }}</strong>
              <span class="text-muted text-xs">RAG 索引</span>
            </div>
          </div>
          <button
            @click="store.rebuildRag()"
            class="px-3 py-2 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm"
          >
            重建 RAG 语义索引
          </button>
        </div>

        <div class="border border-[#e8eeee] rounded-lg p-3.5">
          <h2 class="m-0 text-[17px] font-bold">保护配置</h2>
          <div class="flex justify-between gap-3 py-2.5 border-b border-[#edf1ef] text-sm">
            <span>声明 AI 身份</span>
            <span class="rounded-full px-2 py-1 text-xs font-bold bg-green-soft text-green">已启用</span>
          </div>
          <div class="flex justify-between gap-3 py-2.5 border-b border-[#edf1ef] text-sm">
            <span>售后/价格/库存</span>
            <span class="rounded-full px-2 py-1 text-xs font-bold bg-green-soft text-green">真人接管</span>
          </div>
          <div class="flex justify-between gap-3 py-2.5 border-b border-[#edf1ef] text-sm">
            <span>禁忌词输出过滤</span>
            <span class="rounded-full px-2 py-1 text-xs font-bold bg-green-soft text-green">已启用</span>
          </div>
          <div class="flex justify-between gap-3 py-2.5 text-sm">
            <span>隐式元数据标识</span>
            <span class="rounded-full px-2 py-1 text-xs font-bold bg-coral-soft text-coral">待补齐</span>
          </div>
        </div>
      </section>

      <DanmakuQueue />
      <OBSControl />
    </section>

    <!-- Right rail -->
    <aside class="grid gap-3.5">
      <section class="bg-paper border border-[#d8e2de] rounded-lg p-3.5">
        <h2 class="m-0 text-[17px] font-bold mb-2">接入状态</h2>
        <div class="flex justify-between gap-3 py-2.5 border-b border-[#edf1ef] text-sm">
          <span>助理控制台</span>
          <span class="rounded-full px-2 py-1 text-xs font-bold bg-green-soft text-green">已完成</span>
        </div>
        <div class="flex justify-between gap-3 py-2.5 border-b border-[#edf1ef] text-sm">
          <span>OBS 字幕源</span>
          <span class="rounded-full px-2 py-1 text-xs font-bold bg-green-soft text-green">已完成</span>
        </div>
        <div class="flex justify-between gap-3 py-2.5 border-b border-[#edf1ef] text-sm">
          <span>本地 Ollama</span>
          <span
            class="rounded-full px-2 py-1 text-xs font-bold"
            :class="ollamaOk ? 'bg-green-soft text-green' : 'bg-amber-soft text-amber'"
          >
            {{ ollamaOk ? '已连接' : '待检查' }}
          </span>
        </div>
        <div class="flex justify-between gap-3 py-2.5 border-b border-[#edf1ef] text-sm">
          <span>商品知识库</span>
          <span class="rounded-full px-2 py-1 text-xs font-bold bg-green-soft text-green">{{ knowledge.knowledge_items ?? 0 }} 条</span>
        </div>
        <div class="flex justify-between gap-3 py-2.5 border-b border-[#edf1ef] text-sm">
          <span>RAG 语义索引</span>
          <span
            class="rounded-full px-2 py-1 text-xs font-bold"
            :class="ragCount ? 'bg-green-soft text-green' : 'bg-amber-soft text-amber'"
          >
            {{ ragCount ? `${ragCount} 条索引` : '未索引' }}
          </span>
        </div>
        <div class="flex justify-between gap-3 py-2.5 border-b border-[#edf1ef] text-sm">
          <span>数字人形象</span>
          <span class="rounded-full px-2 py-1 text-xs font-bold bg-amber-soft text-amber">待接入</span>
        </div>
        <div class="flex justify-between gap-3 py-2.5 text-sm">
          <span>声音克隆</span>
          <span class="rounded-full px-2 py-1 text-xs font-bold bg-amber-soft text-amber">待接入</span>
        </div>
      </section>

      <section class="bg-paper border border-[#d8e2de] rounded-lg p-3.5">
        <h2 class="m-0 text-[17px] font-bold mb-2">直播设置</h2>
        <label class="block mt-3 mb-1.5 text-muted text-[13px] font-bold">播报频率</label>
        <select class="w-full min-h-[38px] border border-[#c8d4cf] rounded-md px-2.5 bg-white">
          <option>中频率</option><option>低频率</option><option>高频率</option>
        </select>
        <label class="block mt-3 mb-1.5 text-muted text-[13px] font-bold">平台</label>
        <select class="w-full min-h-[38px] border border-[#c8d4cf] rounded-md px-2.5 bg-white">
          <option>抖音</option>
        </select>
        <label class="block mt-3 mb-1.5 text-muted text-[13px] font-bold">直播间地址</label>
        <input class="w-full px-3 py-3 border border-[#c8d4cf] rounded-md text-sm" placeholder="请输入直播间地址" />
      </section>
    </aside>
  </div>
</template>
