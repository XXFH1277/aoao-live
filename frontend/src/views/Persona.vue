<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useLiveStore } from '../stores/liveStore'

const store = useLiveStore()

const form = ref({
  positioning: '',
  tone: '',
  max_chars: 90,
  max_sentences: 3,
  rules: '',
})

const ttsForm = ref({
  provider_id: 'windows_sapi',
  base_url: '',
  model: '',
  voice: '',
  api_key: '',
  extra_json: '',
  rate: 0,
  volume: 100,
  test_text: '大家好，我是 AI 数字人主播螯螯，本直播间有真人助理实时监管。',
})

const ttsBusy = ref(false)
const ttsError = ref('')
const ttsResult = ref<Record<string, any> | null>(null)
const ttsProviders = computed(() => store.ttsStatus?.providers ?? {})
const ttsProviderEntries = computed(() => Object.entries(ttsProviders.value))
const activeTtsProvider = computed(() => (ttsProviders.value ?? {})[ttsForm.value.provider_id] ?? {})
const isGptSovits = computed(() => (activeTtsProvider.value as any).type === 'gpt_sovits_api')

// Voice samples
const voiceSamples = ref<any[]>([])
const uploadBusy = ref(false)
const uploadError = ref('')
const isRecording = ref(false)
let mediaRecorder: MediaRecorder | null = null
let recordedChunks: Blob[] = []

// Active tab for voice section
const voiceTab = ref<'provider' | 'training'>('training')

onMounted(async () => {
  await Promise.all([store.fetchPersona(), store.fetchTtsStatus(), loadVoiceSamples()])
  const p = store.persona
  form.value.positioning = p.positioning ?? ''
  form.value.tone = p.voice_style?.tone ?? ''
  form.value.max_chars = p.reply_style?.max_chars ?? 90
  form.value.max_sentences = p.reply_style?.max_sentences ?? 3
  form.value.rules = (p.reply_style?.rules ?? []).join('\n')
  const t = store.ttsStatus
  ttsForm.value.provider_id = t.active_provider ?? 'windows_sapi'
  ttsForm.value.rate = t.rate ?? 0
  ttsForm.value.volume = t.volume ?? 100
  syncTtsProviderFields()
})

async function savePersona() {
  await store.updatePersona(form.value)
}

async function saveTtsConfig() {
  await store.updateTtsConfig(ttsForm.value)
}

function syncTtsProviderFields() {
  const provider = ttsProviders.value[ttsForm.value.provider_id] ?? {}
  ttsForm.value.base_url = provider.base_url ?? ''
  ttsForm.value.model = provider.model ?? ''
  ttsForm.value.voice = provider.voice ?? ''
  ttsForm.value.extra_json = JSON.stringify(provider.extra ?? {}, null, 2)
  ttsForm.value.api_key = ''
}

async function testTts() {
  ttsBusy.value = true
  ttsError.value = ''
  ttsResult.value = null
  try {
    await saveTtsConfig()
    const result = await store.synthesizeSpeech({
      text: ttsForm.value.test_text,
      provider: ttsForm.value.provider_id,
      voice: ttsForm.value.voice,
      rate: ttsForm.value.rate,
      volume: ttsForm.value.volume,
    })
    if (!result.ok) {
      ttsError.value = result.hint || result.error || 'TTS 生成失败'
      return
    }
    ttsResult.value = result
  } catch (error) {
    ttsError.value = error instanceof Error ? error.message : String(error)
  } finally {
    ttsBusy.value = false
  }
}

async function loadVoiceSamples() {
  try {
    const data = await store.fetchVoiceSamples()
    voiceSamples.value = data.samples ?? []
  } catch { /* ignore */ }
}

async function handleFileUpload(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  uploadBusy.value = true
  uploadError.value = ''
  try {
    const result = await store.uploadVoiceSample(file)
    if (!result.ok) {
      uploadError.value = result.error || '上传失败'
    } else {
      await loadVoiceSamples()
    }
  } catch (e) {
    uploadError.value = e instanceof Error ? e.message : String(e)
  } finally {
    uploadBusy.value = false
    target.value = ''
  }
}

async function deleteSample(filename: string) {
  await store.deleteVoiceSample(filename)
  await loadVoiceSamples()
}

function useSampleAsRef(sample: any) {
  // Set this sample as GPT-SoVITS reference audio
  ttsForm.value.provider_id = 'gpt_sovits'
  syncTtsProviderFields()
  try {
    const extra = JSON.parse(ttsForm.value.extra_json || '{}')
    extra.ref_audio_path = sample.path
    ttsForm.value.extra_json = JSON.stringify(extra, null, 2)
  } catch {
    ttsForm.value.extra_json = JSON.stringify({ ref_audio_path: sample.path, text_lang: 'zh', prompt_lang: 'zh' }, null, 2)
  }
  voiceTab.value = 'provider'
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    recordedChunks = []
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) recordedChunks.push(e.data)
    }
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop())
      const blob = new Blob(recordedChunks, { type: 'audio/webm' })
      const file = new File([blob], `recording_${Date.now()}.webm`, { type: 'audio/webm' })
      uploadBusy.value = true
      try {
        // Convert to WAV via backend would be better, but for now upload as-is
        // GPT-SoVITS supports webm/wav/mp3
        const result = await store.uploadVoiceSample(file)
        if (result.ok) {
          await loadVoiceSamples()
        } else {
          uploadError.value = result.error || '保存录音失败'
        }
      } finally {
        uploadBusy.value = false
      }
    }
    mediaRecorder.start()
    isRecording.value = true
  } catch (e) {
    uploadError.value = '无法访问麦克风，请检查浏览器权限'
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
  }
  isRecording.value = false
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

const providerQuality: Record<string, { stars: number; desc: string }> = {
  windows_sapi: { stars: 1, desc: '机械播报，仅用于开发测试' },
  gpt_sovits: { stars: 5, desc: '声音克隆，最接近真人，需要本地 GPU' },
  minimax: { stars: 4, desc: '云端高品质，按量计费' },
  mimo: { stars: 4, desc: '云端高品质，按量计费' },
  custom_openai: { stars: 3, desc: '取决于具体服务商' },
  custom_http: { stars: 3, desc: '取决于具体服务商' },
}
</script>

<template>
  <header class="px-7 py-5.5 bg-[#f9fbfa] border-b border-line">
    <div class="flex justify-between items-start gap-4">
      <div>
        <h1 class="text-[28px] leading-tight m-0">数字人资产</h1>
        <div class="mt-2 text-muted text-sm">数字人是独立资产：形象、人设、声音、输出方式，多个直播间可以复用。</div>
      </div>
      <button class="px-3.5 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm">创建数字人</button>
    </div>
  </header>

  <div class="px-7 py-4.5 max-[920px]:px-4">
    <div class="grid grid-cols-[300px_minmax(0,1fr)] gap-3.5 max-[920px]:grid-cols-1">
      <!-- Avatar preview -->
      <div class="bg-white border border-[#d8e2de] rounded-lg p-3.5">
        <div class="aspect-square rounded-lg bg-gradient-to-br from-[#07110f] to-[#14362f] grid place-items-center text-white/60 font-extrabold">
          螯螯形象待接入
        </div>
        <div class="bg-[#f7faf8] border border-line rounded-lg p-3 mt-3">
          <div class="flex justify-between py-1.5 border-b border-[#e7ece9] text-[13px]">
            <span class="text-muted">形象状态</span><strong>待接入</strong>
          </div>
          <div class="flex justify-between py-1.5 border-b border-[#e7ece9] text-[13px]">
            <span class="text-muted">声音引擎</span>
            <strong :class="ttsForm.provider_id === 'gpt_sovits' ? 'text-green' : ttsForm.provider_id === 'windows_sapi' ? 'text-coral' : 'text-teal'">
              {{ (activeTtsProvider as any).label || '未配置' }}
            </strong>
          </div>
          <div class="flex justify-between py-1.5 border-b border-[#e7ece9] text-[13px]">
            <span class="text-muted">参考音频</span>
            <strong>{{ voiceSamples.length }} 个</strong>
          </div>
          <div class="flex justify-between py-1.5 text-[13px]">
            <span class="text-muted">人设状态</span><strong>已配置</strong>
          </div>
        </div>
      </div>

      <!-- Right panel -->
      <div class="flex flex-col gap-3.5">
        <!-- Voice Training Section -->
        <div class="bg-white border border-[#d8e2de] rounded-lg p-4">
          <div class="flex items-center gap-3 mb-3">
            <h3 class="m-0 text-lg font-bold">声音配置</h3>
            <div class="flex rounded-md overflow-hidden border border-line">
              <button
                @click="voiceTab = 'training'"
                class="px-3 py-1.5 text-[13px] font-bold border-0 cursor-pointer transition-colors"
                :class="voiceTab === 'training' ? 'bg-teal text-white' : 'bg-white text-muted hover:bg-wash'"
              >
                声音训练
              </button>
              <button
                @click="voiceTab = 'provider'"
                class="px-3 py-1.5 text-[13px] font-bold border-0 cursor-pointer transition-colors"
                :class="voiceTab === 'provider' ? 'bg-teal text-white' : 'bg-white text-muted hover:bg-wash'"
              >
                供应商配置
              </button>
            </div>
          </div>

          <!-- Voice Training Tab -->
          <div v-if="voiceTab === 'training'">
            <!-- Quality explanation -->
            <div class="bg-amber-soft border border-[#e8c06f] rounded-lg p-3 mb-3">
              <div class="font-bold text-amber text-sm mb-1">为什么听起来像机器人？</div>
              <div class="text-[13px] text-[#7a5a00] leading-relaxed">
                当前使用的是 <strong>Windows 系统语音（SAPI）</strong>，这是上一代语音合成技术。
                要达到接近真人的效果，需要切换到 <strong>GPT-SoVITS 声音克隆</strong> 或 <strong>云端 TTS</strong>。
                下面上传一段你的声音样本（5-30秒），即可用 GPT-SoVITS 克隆出专属声音。
              </div>
            </div>

            <!-- Upload & Record -->
            <div class="grid grid-cols-2 gap-3 mb-3 max-[720px]:grid-cols-1">
              <div class="border border-dashed border-[#a8bab4] rounded-lg p-4 text-center hover:border-teal transition-colors">
                <div class="text-3xl mb-2">📁</div>
                <div class="font-bold text-sm mb-1">上传参考音频</div>
                <div class="text-muted text-xs mb-2">WAV / MP3 / OGG / FLAC，建议 5~30 秒</div>
                <label class="inline-block px-3 py-2 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm hover:opacity-90">
                  {{ uploadBusy ? '上传中...' : '选择文件' }}
                  <input type="file" accept=".wav,.mp3,.ogg,.flac,.m4a,.webm" class="hidden" @change="handleFileUpload" :disabled="uploadBusy" />
                </label>
              </div>
              <div class="border border-dashed border-[#a8bab4] rounded-lg p-4 text-center hover:border-coral transition-colors">
                <div class="text-3xl mb-2">🎙</div>
                <div class="font-bold text-sm mb-1">浏览器录音</div>
                <div class="text-muted text-xs mb-2">点击开始录制，再点停止保存</div>
                <button
                  v-if="!isRecording"
                  @click="startRecording"
                  class="px-3 py-2 rounded-md font-bold text-white bg-coral border-0 cursor-pointer text-sm hover:opacity-90"
                >
                  开始录音
                </button>
                <button
                  v-else
                  @click="stopRecording"
                  class="px-3 py-2 rounded-md font-bold text-white bg-ink border-0 cursor-pointer text-sm animate-pulse"
                >
                  ⏹ 停止录音
                </button>
              </div>
            </div>

            <div v-if="uploadError" class="text-coral text-[13px] mb-2">{{ uploadError }}</div>

            <!-- Voice samples list -->
            <div v-if="voiceSamples.length > 0" class="border border-line rounded-lg overflow-hidden">
              <div class="bg-wash px-3 py-2 font-bold text-sm text-muted border-b border-line">
                已上传的声音样本（{{ voiceSamples.length }}）
              </div>
              <div
                v-for="sample in voiceSamples"
                :key="sample.filename"
                class="flex items-center gap-2 px-3 py-2.5 border-b border-line last:border-b-0 hover:bg-wash/50"
              >
                <audio :src="sample.url" controls class="h-8 flex-1 min-w-0" />
                <span class="text-xs text-muted shrink-0">{{ formatSize(sample.size) }}</span>
                <button
                  @click="useSampleAsRef(sample)"
                  class="shrink-0 px-2 py-1 rounded text-xs font-bold text-white bg-green border-0 cursor-pointer hover:opacity-90"
                  title="设为 GPT-SoVITS 参考音频"
                >
                  用作参考
                </button>
                <button
                  @click="deleteSample(sample.filename)"
                  class="shrink-0 px-2 py-1 rounded text-xs font-bold text-coral bg-coral-soft border border-coral/30 cursor-pointer hover:opacity-90"
                >
                  删除
                </button>
              </div>
            </div>

            <div v-else class="text-center text-muted text-sm py-6">
              还没有声音样本，上传或录制一段你的声音开始训练
            </div>

            <!-- Provider quality comparison -->
            <div class="mt-4">
              <div class="font-bold text-sm mb-2">声音引擎对比</div>
              <div class="grid gap-1.5">
                <div
                  v-for="[id, provider] in ttsProviderEntries"
                  :key="id"
                  class="flex items-center gap-2.5 px-3 py-2 rounded-md border cursor-pointer transition-colors"
                  :class="ttsForm.provider_id === id ? 'border-teal bg-teal-soft' : 'border-line hover:bg-wash'"
                  @click="ttsForm.provider_id = id as string; syncTtsProviderFields(); voiceTab = 'provider'"
                >
                  <span class="text-sm">{{ '⭐'.repeat(providerQuality[id as string]?.stars ?? 3) }}</span>
                  <span class="font-bold text-sm">{{ (provider as any).label }}</span>
                  <span class="text-muted text-xs">{{ providerQuality[id as string]?.desc ?? '' }}</span>
                  <span
                    v-if="(provider as any).ready"
                    class="ml-auto shrink-0 text-xs font-bold text-green bg-green-soft rounded-full px-2 py-0.5"
                  >
                    可用
                  </span>
                  <span
                    v-else
                    class="ml-auto shrink-0 text-xs font-bold text-muted bg-wash rounded-full px-2 py-0.5"
                  >
                    需配置
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Provider Config Tab -->
          <div v-if="voiceTab === 'provider'" class="grid gap-2.5">
            <select
              v-model="ttsForm.provider_id"
              @change="syncTtsProviderFields"
              class="min-h-[38px] border border-[#c8d4cf] rounded-md px-2.5 bg-white"
            >
              <option v-for="[id, provider] in ttsProviderEntries" :key="id" :value="id">
                {{ (provider as any).label ?? id }}
              </option>
            </select>

            <!-- GPT-SoVITS specific guidance -->
            <div v-if="isGptSovits" class="bg-green-soft border border-green/30 rounded-md p-3 text-[13px] leading-relaxed">
              <strong class="text-green">GPT-SoVITS 声音克隆说明：</strong>
              <ol class="m-0 mt-1 pl-4">
                <li>先启动 GPT-SoVITS 的 <code>api_v2.py</code>（默认监听 127.0.0.1:9880）</li>
                <li>在上方"声音训练"标签页上传 5-30 秒参考音频</li>
                <li>点击"用作参考"按钮，会自动填入下方高级参数</li>
                <li>在 <code>prompt_text</code> 填入参考音频里说的那句话</li>
                <li>点"生成试听"验证效果</li>
              </ol>
            </div>

            <input
              v-model="ttsForm.base_url"
              class="px-3 py-2.5 border border-[#c8d4cf] rounded-md text-sm"
              placeholder="Base URL，本地系统语音可留空"
            />
            <div class="grid grid-cols-2 gap-2">
              <input
                v-model="ttsForm.model"
                class="px-3 py-2.5 border border-[#c8d4cf] rounded-md text-sm"
                placeholder="模型，例如 speech-2.8-hd"
              />
              <input
                v-model="ttsForm.voice"
                class="px-3 py-2.5 border border-[#c8d4cf] rounded-md text-sm"
                placeholder="音色 / voice_id"
              />
            </div>
            <textarea
              v-if="isGptSovits"
              v-model="ttsForm.extra_json"
              class="min-h-[132px] border border-[#c8d4cf] rounded-md p-2.5 font-mono text-xs leading-relaxed"
              placeholder='{"ref_audio_path":"E:/voice/aoao.wav","prompt_text":"参考音频里说的话","text_lang":"zh","prompt_lang":"zh"}'
            />
            <input
              v-if="(activeTtsProvider as any).api_key_required"
              v-model="ttsForm.api_key"
              type="password"
              autocomplete="off"
              class="px-3 py-2.5 border border-[#c8d4cf] rounded-md text-sm"
              :placeholder="(activeTtsProvider as any).api_key_saved ? '密钥已保存，留空不改' : '粘贴语音 API Key'"
            />
            <div class="grid grid-cols-2 gap-2">
              <label class="grid gap-1 text-xs text-muted font-bold">
                语速 ({{ ttsForm.rate }})
                <input v-model.number="ttsForm.rate" type="range" min="-10" max="10" />
              </label>
              <label class="grid gap-1 text-xs text-muted font-bold">
                音量 ({{ ttsForm.volume }}%)
                <input v-model.number="ttsForm.volume" type="range" min="0" max="100" />
              </label>
            </div>

            <!-- Test area -->
            <div class="border-t border-line pt-3 mt-1">
              <div class="font-bold text-sm mb-2">试听测试</div>
              <textarea
                v-model="ttsForm.test_text"
                class="w-full min-h-[78px] border border-[#c8d4cf] rounded-md p-2.5 font-[inherit]"
                placeholder="输入一句话测试声音"
              />
              <div class="flex items-center gap-2 flex-wrap mt-2">
                <button
                  type="button"
                  @click="saveTtsConfig"
                  class="px-3 py-2 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm"
                >
                  保存配置
                </button>
                <button
                  type="button"
                  @click="testTts"
                  :disabled="ttsBusy"
                  class="px-3 py-2 rounded-md font-bold text-white bg-[#42a63f] border-0 cursor-pointer text-sm disabled:opacity-60"
                >
                  {{ ttsBusy ? '生成中...' : '生成试听' }}
                </button>
              </div>
              <div v-if="ttsError" class="text-coral text-[13px] leading-normal mt-2">{{ ttsError }}</div>
              <audio v-if="ttsResult?.audio_url" :src="ttsResult.audio_url" controls autoplay class="w-full mt-2" />
              <div class="text-muted text-xs mt-1">
                当前：{{ (activeTtsProvider as any).type || 'windows_sapi' }} · 已生成 {{ store.ttsStatus?.generated_count ?? 0 }} 条
              </div>
            </div>
          </div>
        </div>

        <!-- Persona editor -->
        <div class="bg-white border border-[#d8e2de] rounded-lg p-4">
          <h3 class="m-0 mb-3 text-lg font-bold">螯螯人设</h3>
          <form @submit.prevent="savePersona" class="grid grid-cols-2 gap-3 max-[920px]:grid-cols-1">
            <div class="col-span-2 max-[920px]:col-span-1">
              <label class="block mb-1.5 text-muted text-[13px] font-bold">定位</label>
              <textarea
                v-model="form.positioning"
                class="w-full min-h-[90px] border border-[#c8d4cf] rounded-md p-2.5 font-[inherit]"
              />
            </div>
            <div class="col-span-2 max-[920px]:col-span-1">
              <label class="block mb-1.5 text-muted text-[13px] font-bold">说话口吻</label>
              <textarea
                v-model="form.tone"
                class="w-full min-h-[90px] border border-[#c8d4cf] rounded-md p-2.5 font-[inherit]"
              />
            </div>
            <div>
              <label class="block mb-1.5 text-muted text-[13px] font-bold">单次回复字数上限</label>
              <input v-model.number="form.max_chars" type="number" min="40" max="180" class="w-full px-3 py-3 border border-[#c8d4cf] rounded-md text-sm" />
            </div>
            <div>
              <label class="block mb-1.5 text-muted text-[13px] font-bold">句数上限</label>
              <input v-model.number="form.max_sentences" type="number" min="1" max="5" class="w-full px-3 py-3 border border-[#c8d4cf] rounded-md text-sm" />
            </div>
            <div class="col-span-2 max-[920px]:col-span-1">
              <label class="block mb-1.5 text-muted text-[13px] font-bold">回复规则（一行一条）</label>
              <textarea
                v-model="form.rules"
                class="w-full min-h-[150px] border border-[#c8d4cf] rounded-md p-2.5 font-[inherit]"
              />
            </div>
            <div class="col-span-2 max-[920px]:col-span-1 flex items-center gap-2.5 flex-wrap">
              <button type="submit" class="px-3.5 py-2.5 rounded-md font-bold text-white bg-teal border-0 cursor-pointer text-sm">保存人设</button>
              <span class="rounded-full px-2 py-1 text-xs font-bold bg-green-soft text-green">会进入模型系统提示词</span>
            </div>
          </form>

          <div class="mt-4 border border-[#e8eeee] rounded-lg p-3.5">
            <h2 class="m-0 text-[17px] font-bold">形象</h2>
            <p class="text-muted text-[13px] leading-normal mt-1.5">后续接入 HeyGem / DH_live，本区负责上传素材、训练/克隆、预览。</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
