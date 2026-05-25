<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useLiveStore } from '../stores/liveStore'

const store = useLiveStore()
onMounted(() => store.fetchState())

const form = ref({
  product_id: '',
  kind: 'selling_points',
  title: '',
  safe_level: 'safe',
  text: '',
})

async function addItem() {
  if (!form.value.title.trim() || !form.value.text.trim()) return
  await store.addKnowledge(form.value)
  form.value.title = ''
  form.value.text = ''
}
</script>

<template>
  <header class="px-7 py-5.5 bg-[#f9fbfa] border-b border-line">
    <h1 class="text-[28px] leading-tight m-0">商品知识</h1>
    <div class="mt-2 text-muted text-sm">管理商品资料、知识条目和 RAG 索引。</div>
  </header>

  <div class="px-7 py-4.5 max-[920px]:px-4">
    <!-- Metrics -->
    <div class="grid grid-cols-3 gap-2.5 mb-4 max-w-[480px]">
      <div class="bg-[#f5f8f7] rounded-[7px] p-3">
        <strong class="block text-[22px]">{{ store.state.knowledge?.products ?? 0 }}</strong>
        <span class="text-muted text-xs">商品/场景</span>
      </div>
      <div class="bg-[#f5f8f7] rounded-[7px] p-3">
        <strong class="block text-[22px]">{{ store.state.knowledge?.knowledge_items ?? 0 }}</strong>
        <span class="text-muted text-xs">知识条目</span>
      </div>
      <div class="bg-[#f5f8f7] rounded-[7px] p-3">
        <strong class="block text-[22px]">{{ store.state.knowledge?.embeddings ?? 0 }}</strong>
        <span class="text-muted text-xs">RAG 索引</span>
      </div>
    </div>

    <div class="flex gap-2.5 mb-5">
      <button
        @click="store.rebuildRag()"
        class="px-3.5 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm"
      >
        重建 RAG 语义索引
      </button>
      <span
        class="rounded-full px-2 py-1 text-xs font-bold self-center"
        :class="(store.state.knowledge?.embeddings ?? 0) ? 'bg-green-soft text-green' : 'bg-amber-soft text-amber'"
      >
        {{ (store.state.knowledge?.embeddings ?? 0) ? `${store.state.knowledge.embeddings} 条索引` : '未索引' }}
      </span>
    </div>

    <!-- Add knowledge form -->
    <section class="bg-paper border border-[#d8e2de] rounded-lg p-4 mb-4">
      <h2 class="m-0 text-[17px] font-bold mb-3">添加知识条目</h2>
      <form @submit.prevent="addItem" class="grid grid-cols-2 gap-2 max-[920px]:grid-cols-1">
        <select v-model="form.product_id" class="min-h-[38px] border border-[#c8d4cf] rounded-md px-2.5 bg-white">
          <option value="">选择商品</option>
          <option v-for="p in store.state.products" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <select v-model="form.kind" class="min-h-[38px] border border-[#c8d4cf] rounded-md px-2.5 bg-white">
          <option value="selling_points">卖点</option>
          <option value="safe_claims">安全话术</option>
          <option value="faq">FAQ</option>
          <option value="risky_claims">禁用表达</option>
        </select>
        <input
          v-model="form.title"
          class="px-3 py-3 border border-[#c8d4cf] rounded-md text-sm"
          placeholder="标题，例如：礼盒送礼场景"
        />
        <select v-model="form.safe_level" class="min-h-[38px] border border-[#c8d4cf] rounded-md px-2.5 bg-white">
          <option value="safe">可用于回复</option>
          <option value="risky">仅作风险提示</option>
        </select>
        <textarea
          v-model="form.text"
          class="col-span-2 max-[920px]:col-span-1 min-h-[78px] resize-y p-3 border border-[#c8d4cf] rounded-md font-[inherit]"
          placeholder="输入商品介绍、卖点、FAQ 或禁用表达"
        />
        <button type="submit" class="justify-self-start px-3.5 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm">
          加入知识库
        </button>
      </form>
    </section>

    <!-- Knowledge table -->
    <section class="bg-paper border border-[#d8e2de] rounded-lg p-4">
      <h2 class="m-0 text-[17px] font-bold mb-3">知识条目</h2>
      <table class="w-full border-collapse text-[13px]">
        <thead>
          <tr>
            <th class="border-b border-[#e9eeeb] p-2.5 text-left text-muted text-xs bg-[#f7faf8]">标题</th>
            <th class="border-b border-[#e9eeeb] p-2.5 text-left text-muted text-xs bg-[#f7faf8]">类型</th>
            <th class="border-b border-[#e9eeeb] p-2.5 text-left text-muted text-xs bg-[#f7faf8]">内容</th>
            <th class="border-b border-[#e9eeeb] p-2.5 text-left text-muted text-xs bg-[#f7faf8]">级别</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, i) in store.state.knowledge_items" :key="i">
            <td class="border-b border-[#e9eeeb] p-2.5 text-left align-top">{{ item.title }}</td>
            <td class="border-b border-[#e9eeeb] p-2.5 text-left align-top">{{ item.kind }}</td>
            <td class="border-b border-[#e9eeeb] p-2.5 text-left align-top text-[#3b4b47] leading-[1.45]">{{ item.content }}</td>
            <td class="border-b border-[#e9eeeb] p-2.5 text-left align-top">
              <span
                class="rounded-full px-2 py-1 text-xs font-bold"
                :class="item.safe_level === 'risky' ? 'bg-coral-soft text-coral' : 'bg-green-soft text-green'"
              >
                {{ item.safe_level }}
              </span>
            </td>
          </tr>
          <tr v-if="!store.state.knowledge_items?.length">
            <td colspan="4" class="border-b border-[#e9eeeb] p-2.5 text-muted">暂无知识条目</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>
