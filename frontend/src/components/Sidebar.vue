<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
const navItems = [
  { to: '/', icon: '▣', label: '工作台' },
  { to: '/room', icon: '▤', label: '直播间详情' },
  { to: '/persona', icon: '◉', label: '数字人资产' },
  { to: '/knowledge', icon: '▥', label: '商品知识' },
  { to: '/settings', icon: '◇', label: '全局设置' },
]
</script>

<template>
  <aside class="bg-sidebar text-[#e7f0ed] px-3.5 py-4.5 flex flex-col gap-6">
    <div class="flex gap-3 items-center p-1.5">
      <div class="w-[46px] h-[46px] grid place-items-center rounded-lg bg-green text-white font-extrabold text-[22px]">
        螯
      </div>
      <div>
        <strong class="block text-[15px]">螯螯直播</strong>
        <span class="block mt-0.5 text-sidebar-muted text-xs">AI 数字人中控</span>
      </div>
    </div>

    <nav class="grid gap-1.5">
      <router-link
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="flex items-center gap-2.5 min-h-[42px] px-3 text-sidebar-text no-underline rounded-md font-bold text-sm
               hover:bg-sidebar-hover hover:text-white"
        :class="{ 'bg-sidebar-hover text-white!': route.path === item.to }"
      >
        <span class="w-[18px] text-center">{{ item.icon }}</span>
        {{ item.label }}
      </router-link>
    </nav>

    <div class="mt-auto p-3 rounded-lg bg-sidebar-foot text-sidebar-muted text-xs">
      <div>当前版本</div>
      <strong class="block text-white mt-1">Phase 1 Frontend</strong>
    </div>
  </aside>
</template>
