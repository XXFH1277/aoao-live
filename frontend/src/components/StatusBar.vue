<script setup lang="ts">
import { ref } from 'vue'

const roomUrl = ref('')
</script>

<template>
  <footer class="fixed left-[180px] right-0 bottom-0 h-[58px] flex items-center gap-2.5
                  px-7 bg-white/96 border-t border-line shadow-[0_-5px_18px_rgba(18,30,26,.06)]
                  max-[920px]:left-0 max-[920px]:h-auto max-[920px]:flex-wrap">
    <span class="bg-wash border border-line rounded-md px-3.5 py-2.5 font-bold">平台：抖音</span>
    <input
      v-model="roomUrl"
      class="max-w-[280px] px-3 py-2.5 border border-[#c8d4cf] rounded-md text-sm"
      placeholder="请输入直播间地址"
    />
    <button class="px-3.5 py-2.5 rounded-md font-bold text-white bg-[#f2bd74] border-0 cursor-pointer text-sm">
      开始弹幕捕获
    </button>
    <button class="px-3.5 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm">
      保存
    </button>
    <button class="px-3.5 py-2.5 rounded-md font-bold text-white bg-[#42a63f] border-0 cursor-pointer text-sm">
      开始直播
    </button>
  </footer>
</template>
