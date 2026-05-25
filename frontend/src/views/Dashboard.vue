<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useLiveStore } from '../stores/liveStore'

const store = useLiveStore()
const router = useRouter()

onMounted(() => store.fetchState())
</script>

<template>
  <header class="px-7 py-5.5 bg-[#f9fbfa] border-b border-line flex justify-between items-center gap-4 flex-wrap">
    <div>
      <h1 class="text-[28px] leading-tight m-0">我的直播间</h1>
      <div class="mt-2 text-muted text-sm">有人值守的 AI 主播工作台：商品知识、脚本、互动、合规和 OBS 统一管理。</div>
    </div>
    <div class="flex gap-2.5 items-center flex-wrap">
      <span
        class="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-full font-bold text-[13px]"
        :class="store.state.running ? 'bg-green-soft text-green' : 'bg-coral-soft text-coral'"
      >
        <span class="w-2 h-2 rounded-full bg-current" />
        {{ store.state.running ? '运行中' : '已暂停' }}
      </span>
      <button
        @click="store.resume()"
        class="px-3.5 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm"
      >
        开始值守
      </button>
    </div>
  </header>

  <section class="grid grid-cols-[repeat(2,minmax(220px,280px))] gap-4 p-4.5 px-7 max-[920px]:grid-cols-1 max-[920px]:px-4">
    <article
      class="bg-white border border-line rounded-lg overflow-hidden shadow-[0_8px_22px_rgba(29,44,39,.06)] cursor-pointer border-[#a9d2f7]"
      @click="router.push('/room')"
    >
      <div class="h-[150px] grid place-items-center bg-[#f1f5f9] text-[#708090] text-2xl font-extrabold">AI</div>
      <div class="p-3.5 grid gap-1 text-center">
        <strong>螯螯测试直播间</strong>
        <span class="text-muted text-xs">抖音 · 数字人直播间</span>
        <div class="text-muted text-xs">ID: AOAO-0001</div>
      </div>
    </article>

    <article class="bg-white border border-line rounded-lg overflow-hidden shadow-[0_8px_22px_rgba(29,44,39,.06)] cursor-pointer">
      <div class="h-[150px] grid place-items-center bg-[#f1f5f9] text-[#9aa7b2] text-[32px] font-extrabold">+</div>
      <div class="p-3.5 grid gap-1 text-center">
        <strong>新建直播间</strong>
        <span class="text-muted text-xs">复制当前配置快速起号</span>
        <div class="text-muted text-xs">待创建</div>
      </div>
    </article>
  </section>

  <section class="px-7 py-4.5 border-t border-[#dfe8e4] max-[920px]:px-4">
    <div class="flex justify-between items-start gap-4 mb-3.5">
      <div>
        <h2 class="m-0 text-[22px]">创建直播间</h2>
        <p class="mt-1.5 text-muted">按流程配置：直播类型、商品、数字人、直播参数。</p>
      </div>
      <button class="px-3.5 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm">
        新建直播间
      </button>
    </div>

    <div class="grid grid-cols-3 gap-3.5 max-[920px]:grid-cols-1">
      <div class="bg-white border border-[#d8e2de] rounded-lg p-4 min-h-[170px]">
        <h3 class="m-0 mb-2.5 text-base">1. 选择直播类型</h3>
        <div class="grid gap-2">
          <div class="border border-[#dce6e2] rounded-[7px] p-2.5 bg-[#fbfcfb]">
            <strong class="block">数字人带货</strong>
            <span class="block mt-0.5 text-muted text-xs">商品讲解、弹幕问答、真人助理监管</span>
          </div>
          <div class="border border-[#dce6e2] rounded-[7px] p-2.5 bg-[#fbfcfb]">
            <strong class="block">文旅咨询</strong>
            <span class="block mt-0.5 text-muted text-xs">路线、房态、交通信息，敏感信息人工确认</span>
          </div>
          <div class="border border-[#dce6e2] rounded-[7px] p-2.5 bg-[#fbfcfb]">
            <strong class="block">试播 Demo</strong>
            <span class="block mt-0.5 text-muted text-xs">只用于本机测试和 OBS 合成</span>
          </div>
        </div>
      </div>

      <div class="bg-white border border-[#d8e2de] rounded-lg p-4 min-h-[170px]">
        <h3 class="m-0 mb-2.5 text-base">2. 选择商品/知识库</h3>
        <div class="grid gap-2">
          <div class="border border-[#dce6e2] rounded-[7px] p-2.5 bg-[#fbfcfb]">
            <strong class="block">舟山海鲜礼盒 Demo</strong>
            <span class="block mt-0.5 text-muted text-xs">家庭聚餐、节日送礼、本地特产</span>
          </div>
          <div class="border border-[#dce6e2] rounded-[7px] p-2.5 bg-[#fbfcfb]">
            <strong class="block">舟山文旅线路 Demo</strong>
            <span class="block mt-0.5 text-muted text-xs">普陀山、朱家尖、东极岛</span>
          </div>
        </div>
      </div>

      <div class="bg-white border border-[#d8e2de] rounded-lg p-4 min-h-[170px]">
        <h3 class="m-0 mb-2.5 text-base">3. 选择数字人和声音</h3>
        <div class="grid gap-2">
          <div class="border border-[#dce6e2] rounded-[7px] p-2.5 bg-[#fbfcfb]">
            <strong class="block">螯螯</strong>
            <span class="block mt-0.5 text-muted text-xs">形象待接入，当前使用 OBS 字幕源占位</span>
          </div>
          <div class="border border-[#dce6e2] rounded-[7px] p-2.5 bg-[#fbfcfb]">
            <strong class="block">声音克隆</strong>
            <span class="block mt-0.5 text-muted text-xs">待接 GPT-SoVITS / CosyVoice</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
