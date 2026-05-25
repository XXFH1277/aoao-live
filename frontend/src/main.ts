import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

import Dashboard from './views/Dashboard.vue'
import LiveRoom from './views/LiveRoom.vue'
import Knowledge from './views/Knowledge.vue'
import Persona from './views/Persona.vue'
import Settings from './views/Settings.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard },
    { path: '/room', name: 'liveroom', component: LiveRoom },
    { path: '/knowledge', name: 'knowledge', component: Knowledge },
    { path: '/persona', name: 'persona', component: Persona },
    { path: '/settings', name: 'settings', component: Settings },
  ],
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
