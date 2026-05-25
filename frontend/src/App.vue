<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useLiveStore } from './stores/liveStore'
import Sidebar from './components/Sidebar.vue'
import StatusBar from './components/StatusBar.vue'

const store = useLiveStore()

onMounted(() => store.connect())
onUnmounted(() => store.disconnect())
</script>

<template>
  <div class="min-h-screen grid grid-cols-[212px_minmax(0,1fr)]
              max-[920px]:grid-cols-1">
    <Sidebar class="max-[920px]:hidden" />
    <main class="pb-18 min-w-0">
      <router-view />
    </main>
  </div>
  <StatusBar />
</template>
