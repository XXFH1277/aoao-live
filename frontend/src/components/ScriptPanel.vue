<script setup lang="ts">
import { useLiveStore } from '../stores/liveStore'

const store = useLiveStore()
</script>

<template>
  <section class="bg-paper border border-[#d8e2de] rounded-lg p-4 shadow-[0_8px_24px_rgba(18,31,27,.05)]">
    <div class="flex justify-between items-start gap-3 mb-3.5">
      <div>
        <h2 class="m-0 text-[17px] font-bold">智能脚本</h2>
        <p class="mt-1.5 text-muted text-sm">把商品知识、人设和合规边界喂给本地模型，生成可控回复。</p>
      </div>
      <span class="bg-[#e6f6e9] text-[#278044] rounded-md px-3.5 py-2 font-bold text-[13px] shrink-0">
        AI 知识库已加载
      </span>
    </div>

    <div class="flex gap-2.5 flex-wrap mb-3.5">
      <span class="px-3 py-2 rounded-md bg-[#e7f2ff] text-[#1d74bd] text-[13px] font-extrabold">1. 添加商品</span>
      <span class="px-3 py-2 rounded-md bg-[#e7f2ff] text-[#1d74bd] text-[13px] font-extrabold">2. 生成话术</span>
      <span class="px-3 py-2 rounded-md bg-[#e7f2ff] text-[#1d74bd] text-[13px] font-extrabold">3. 人设约束</span>
      <span class="px-3 py-2 rounded-md bg-[#e9f7e7] text-[#2e8b44] text-[13px] font-extrabold">4. AI 回复</span>
      <span class="px-3 py-2 rounded-md bg-[#eef2f6] text-[#66727d] text-[13px] font-extrabold">5. 去敏感词</span>
    </div>

    <div class="border border-[#e6ece9] rounded-lg p-4 bg-[#fbfcfb]">
      <div class="font-extrabold mb-2.5">当前口播 / OBS 字幕</div>
      <div class="border border-[#cbdceb] bg-white rounded-md p-3.5 min-h-[150px] max-h-[260px] overflow-auto leading-[1.7] text-[#394843]">
        {{ store.state.current_line || '等待话术...' }}
      </div>

      <div
        v-if="store.state.warning"
        class="mt-3 p-3 bg-amber-soft border border-[#e8c06f] rounded-md text-amber font-bold"
      >
        {{ store.state.warning }}
      </div>

      <div class="flex gap-2.5 flex-wrap mt-3 text-muted text-[13px]">
        <span class="inline-flex items-center border border-line rounded-full px-2 py-1.5 bg-[#fbfcfb]">
          运行 {{ store.state.uptime_seconds }} 秒
        </span>
        <span class="inline-flex items-center border border-line rounded-full px-2 py-1.5 bg-[#fbfcfb]">
          话术位置 #{{ store.state.index }}
        </span>
        <span class="inline-flex items-center border border-line rounded-full px-2 py-1.5 bg-[#fbfcfb]">
          回复来源：{{ store.state.last_reply_source || '无' }}
        </span>
        <span class="inline-flex items-center border border-line rounded-full px-2 py-1.5 bg-[#fbfcfb]">
          AI 标识已显示
        </span>
        <label
          class="inline-flex items-center gap-1.5 border rounded-full px-2 py-1.5 cursor-pointer select-none"
          :class="store.ttsAutoPlay ? 'border-green bg-green-soft text-green' : 'border-line bg-[#fbfcfb] text-muted'"
        >
          <input type="checkbox" v-model="store.ttsAutoPlay" class="sr-only" />
          🔊 TTS {{ store.ttsAutoPlay ? '已开启' : '已关闭' }}
        </label>
        <span v-if="store.audioPlaying" class="inline-flex items-center border border-teal bg-teal-soft text-teal rounded-full px-2 py-1.5 text-[13px]">
          🎵 播放中
        </span>
        <button
          v-if="store.audioPlaying"
          @click="store.clearAudioQueue()"
          class="inline-flex items-center border border-coral bg-coral-soft text-coral rounded-full px-2 py-1.5 text-[13px] cursor-pointer hover:opacity-80"
        >
          ⏹ 停止播放
        </button>
      </div>

      <audio v-if="store.lastAudioUrl" :src="store.lastAudioUrl" controls class="w-full mt-2 h-8" />
    </div>
  </section>
</template>
