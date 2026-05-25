import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../composables/useApi'

export interface LiveState {
  running: boolean
  current_line: string
  index: number
  uptime_seconds: number
  warning: string
  last_danmaku: string
  last_reply_source: string
  ollama: Record<string, any>
  llm_router: Record<string, any>
  knowledge: Record<string, any>
  products: any[]
  knowledge_items: any[]
  interactions: any[]
}

export const useLiveStore = defineStore('live', () => {
  const state = ref<LiveState>({
    running: false,
    current_line: '',
    index: 0,
    uptime_seconds: 0,
    warning: '',
    last_danmaku: '',
    last_reply_source: '',
    ollama: {},
    llm_router: {},
    knowledge: {},
    products: [],
    knowledge_items: [],
    interactions: [],
  })

  const connected = ref(false)
  const lastAudioUrl = ref('')
  const audioPlaying = ref(false)
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let _audioEl: HTMLAudioElement | null = null
  let _audioQueue: string[] = []

  const persona = ref<Record<string, any>>({})
  const ttsStatus = ref<Record<string, any>>({})
  const ttsAutoPlay = ref(true)

  const providers = computed(() => state.value.llm_router?.providers ?? {})
  const activeProviderId = computed(() => state.value.llm_router?.active_provider ?? 'ollama')

  function _initAudioEl() {
    if (_audioEl) return
    _audioEl = new Audio()
    _audioEl.addEventListener('ended', () => {
      audioPlaying.value = false
      _playNext()
    })
    _audioEl.addEventListener('error', () => {
      audioPlaying.value = false
      _playNext()
    })
  }

  function _playNext() {
    if (_audioQueue.length === 0) return
    const url = _audioQueue.shift()!
    _initAudioEl()
    _audioEl!.src = url
    audioPlaying.value = true
    _audioEl!.play().catch(() => {
      audioPlaying.value = false
      _playNext()
    })
  }

  function _enqueueAudio(url: string) {
    if (!ttsAutoPlay.value) return
    lastAudioUrl.value = url
    // If nothing is playing, start immediately; otherwise queue it
    if (!audioPlaying.value) {
      _initAudioEl()
      _audioEl!.src = url
      audioPlaying.value = true
      _audioEl!.play().catch(() => {
        audioPlaying.value = false
        _playNext()
      })
    } else {
      _audioQueue.push(url)
    }
  }

  function clearAudioQueue() {
    _audioQueue = []
    if (_audioEl) {
      _audioEl.pause()
      _audioEl.currentTime = 0
    }
    audioPlaying.value = false
  }

  function connect() {
    if (ws && ws.readyState <= WebSocket.OPEN) return
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(`${proto}://${location.host}/ws`)

    ws.onopen = () => { connected.value = true }

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.event === 'state_update') {
          Object.assign(state.value, msg.data)
        } else if (msg.event === 'danmaku_reply') {
          state.value.last_danmaku = msg.data.question
          state.value.last_reply_source = msg.data.source
          state.value.current_line = msg.data.answer
        } else if (msg.event === 'tts_audio') {
          _enqueueAudio(msg.data.audio_url)
        }
      } catch { /* ignore parse errors */ }
    }

    ws.onclose = () => {
      connected.value = false
      reconnectTimer = setTimeout(connect, 3000)
    }

    ws.onerror = () => ws?.close()
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    ws?.close()
    ws = null
  }

  function send(action: string, payload: Record<string, any> = {}) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action, ...payload }))
    }
  }

  async function fetchState() {
    const data = await api<any>('/api/v1/state')
    Object.assign(state.value, data)
  }

  async function fetchPersona() {
    persona.value = await api<any>('/api/v1/persona')
  }

  async function fetchTtsStatus() {
    ttsStatus.value = await api<any>('/api/v1/tts/status')
  }

  async function nextLine() { send('next_line') }
  async function pause() { send('pause') }
  async function resume() { send('resume') }

  async function sendDanmaku(text: string) {
    send('danmaku', { text })
  }

  async function sendAssistantReply(text: string) {
    send('assistant_reply', { text })
  }

  async function updateLlmProvider(data: Record<string, any>) {
    await api('/api/v1/llm/provider', { method: 'PUT', body: JSON.stringify(data) })
    await fetchState()
  }

  async function updatePersona(data: Record<string, any>) {
    await api('/api/v1/persona', { method: 'PUT', body: JSON.stringify(data) })
    await fetchPersona()
  }

  async function addKnowledge(data: Record<string, any>) {
    await api('/api/v1/knowledge', { method: 'POST', body: JSON.stringify(data) })
    await fetchState()
  }

  async function rebuildRag() {
    await api('/api/v1/knowledge/rag/rebuild', { method: 'POST' })
    await fetchState()
  }

  async function updateTtsConfig(data: Record<string, any>) {
    ttsStatus.value = await api('/api/v1/tts/config', { method: 'PUT', body: JSON.stringify(data) })
  }

  async function synthesizeSpeech(data: Record<string, any>) {
    const result = await api<any>('/api/v1/tts/speak', { method: 'POST', body: JSON.stringify(data) })
    await fetchTtsStatus()
    return result
  }

  async function fetchVoiceSamples() {
    return await api<any>('/api/v1/tts/voice-samples')
  }

  async function uploadVoiceSample(file: File) {
    const form = new FormData()
    form.append('file', file)
    const resp = await fetch('/api/v1/tts/voice-samples/upload', { method: 'POST', body: form })
    return await resp.json()
  }

  async function deleteVoiceSample(filename: string) {
    return await api<any>(`/api/v1/tts/voice-samples/${encodeURIComponent(filename)}`, { method: 'DELETE' })
  }

  return {
    state,
    connected,
    lastAudioUrl,
    audioPlaying,
    ttsAutoPlay,
    clearAudioQueue,
    persona,
    ttsStatus,
    providers,
    activeProviderId,
    connect,
    disconnect,
    fetchState,
    fetchPersona,
    fetchTtsStatus,
    nextLine,
    pause,
    resume,
    sendDanmaku,
    sendAssistantReply,
    updateLlmProvider,
    updatePersona,
    addKnowledge,
    rebuildRag,
    updateTtsConfig,
    synthesizeSpeech,
    fetchVoiceSamples,
    uploadVoiceSample,
    deleteVoiceSample,
  }
})
