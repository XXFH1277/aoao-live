<script setup lang="ts">
import { ref } from 'vue'
import { useLiveStore } from '../stores/liveStore'

const store = useLiveStore()
const danmakuText = ref('')
const assistantText = ref('')

async function submitDanmaku() {
  if (!danmakuText.value.trim()) return
  await store.sendDanmaku(danmakuText.value.trim())
  danmakuText.value = ''
}

async function submitAssistant() {
  if (!assistantText.value.trim()) return
  await store.sendAssistantReply(assistantText.value.trim())
  assistantText.value = ''
}

function tagClass(status: string) {
  if (status === 'answered') return 'bg-green-soft text-green'
  if (status === 'new') return 'bg-amber-soft text-amber'
  if (status === 'handoff') return 'bg-coral-soft text-coral'
  return 'bg-green-soft text-green'
}
</script>

<template>
  <section class="bg-paper border border-[#d8e2de] rounded-lg p-4 shadow-[0_8px_24px_rgba(18,31,27,.05)]">
    <div class="flex justify-between items-start gap-3 mb-3.5">
      <div>
        <h2 class="m-0 text-[17px] font-bold">主动互动控制</h2>
        <p class="mt-1.5 text-muted text-sm">模拟弹幕、真人接管、话术切换都会同步到 OBS 字幕源。</p>
      </div>
      <div class="flex gap-2">
        <button @click="store.resume()" class="px-3 py-2 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm">继续</button>
        <button @click="store.pause()" class="px-3 py-2 rounded-md font-bold text-white bg-coral border-0 cursor-pointer text-sm">暂停</button>
        <button @click="store.nextLine()" class="px-3 py-2 rounded-md font-bold text-white bg-[#53645f] border-0 cursor-pointer text-sm">下一句</button>
      </div>
    </div>

    <form @submit.prevent="submitDanmaku" class="grid grid-cols-[minmax(0,1fr)_auto] gap-2 mt-2.5">
      <input
        v-model="danmakuText"
        class="px-3 py-3 border border-[#c8d4cf] rounded-md text-sm"
        placeholder="模拟弹幕：这个海鲜礼盒适合送人吗 / 主播是真人吗 / 发货要多久"
      />
      <button type="submit" class="px-3.5 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm">模拟提问</button>
    </form>

    <form @submit.prevent="submitAssistant" class="grid grid-cols-[minmax(0,1fr)_auto] gap-2 mt-2">
      <input
        v-model="assistantText"
        class="px-3 py-3 border border-[#c8d4cf] rounded-md text-sm"
        placeholder="真人助理确认后的回复"
      />
      <button type="submit" class="px-3.5 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm">主动控制回复</button>
    </form>

    <p class="text-muted text-[13px] leading-normal mt-2">
      上一条弹幕：{{ store.state.last_danmaku || '暂无' }}
    </p>

    <div class="grid gap-2.5 mt-3">
      <div
        v-for="(item, i) in store.state.interactions"
        :key="i"
        class="border border-[#e6ece9] rounded-lg p-3 bg-[#fbfcfb]"
      >
        <div class="flex justify-between gap-2.5 items-center">
          <strong>{{ item.message }}</strong>
          <span class="rounded-full px-2 py-1 text-xs font-bold" :class="tagClass(item.status)">
            {{ item.status }}
          </span>
        </div>
        <p class="my-2 leading-normal text-[#364642]">{{ item.reply || '等待处理' }}</p>
        <div class="text-muted text-xs">{{ item.created_at }} · {{ item.source || item.kind }}</div>
      </div>
      <div v-if="!store.state.interactions?.length" class="text-muted text-xs">暂无互动记录</div>
    </div>
  </section>
</template>
