<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

const isOnline = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
const apiUnavailable = ref(false)
const updateAvailable = ref(false)
const installPromptAvailable = ref(false)
const iosInstallHint = ref(false)
const bannerTop = ref(140)
let installPromptEvent = null
let registration = null
let hadControllerBeforeRegistration = false

const showBanner = computed(() => !isOnline.value || apiUnavailable.value ||
  updateAvailable.value || installPromptAvailable.value || iosInstallHint.value)

const updateBannerPosition = () => {
  const toolbar = document.querySelector('.app-toolbar')
  bannerTop.value = Math.ceil((toolbar?.getBoundingClientRect().bottom ?? 128) + 8)
}

const onOnline = () => { isOnline.value = true }
const onOffline = () => { isOnline.value = false }
const onApiStatus = event => { apiUnavailable.value = event.detail?.available === false }

const onBeforeInstallPrompt = event => {
  event.preventDefault()
  installPromptEvent = event
  installPromptAvailable.value = true
}
const onAppInstalled = () => { installPromptAvailable.value = false }

const installApp = async () => {
  if (!installPromptEvent) return
  await installPromptEvent.prompt()
  await installPromptEvent.userChoice
  installPromptEvent = null
  installPromptAvailable.value = false
}

const acceptUpdate = () => {
  const waitingWorker = registration?.waiting
  if (!waitingWorker) {
    updateAvailable.value = false
    return
  }
  waitingWorker.postMessage({ type: 'SKIP_WAITING' })
}

const dismissUpdate = () => { updateAvailable.value = false }

const observeRegistration = currentRegistration => {
  registration = currentRegistration
  if (registration.waiting && navigator.serviceWorker.controller) updateAvailable.value = true

  registration.addEventListener('updatefound', () => {
    const installingWorker = registration.installing
    installingWorker?.addEventListener('statechange', () => {
      if (installingWorker.state === 'installed' && navigator.serviceWorker.controller) {
        updateAvailable.value = true
      }
    })
  })
}

const onControllerChange = () => {
  // The user may accept the update from another tab. Reload every tab that was
  // already running under the previous worker so old JS cannot mix with new assets.
  if (hadControllerBeforeRegistration) window.location.reload()
}

onMounted(async () => {
  updateBannerPosition()
  window.addEventListener('resize', updateBannerPosition)
  window.addEventListener('online', onOnline)
  window.addEventListener('offline', onOffline)
  window.addEventListener('smart-tourism:api-status', onApiStatus)
  window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt)
  window.addEventListener('appinstalled', onAppInstalled)

  const standalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true
  iosInstallHint.value = /iPhone|iPad|iPod/i.test(navigator.userAgent) && !standalone

  // Vite dev mode intentionally does not register a worker, keeping HMR and test API calls transparent.
  if (import.meta.env.PROD && window.isSecureContext && 'serviceWorker' in navigator) {
    try {
      hadControllerBeforeRegistration = Boolean(navigator.serviceWorker.controller)
      const workerUrl = new URL(`${import.meta.env.BASE_URL}sw.js`, window.location.href)
      const currentRegistration = await navigator.serviceWorker.register(workerUrl, {
        scope: import.meta.env.BASE_URL,
        updateViaCache: 'none'
      })
      observeRegistration(currentRegistration)
      navigator.serviceWorker.addEventListener('controllerchange', onControllerChange)
    } catch {
      // Installation is optional; the web app remains usable when the browser blocks workers.
    }
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', updateBannerPosition)
  window.removeEventListener('online', onOnline)
  window.removeEventListener('offline', onOffline)
  window.removeEventListener('smart-tourism:api-status', onApiStatus)
  window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt)
  window.removeEventListener('appinstalled', onAppInstalled)
  navigator.serviceWorker?.removeEventListener('controllerchange', onControllerChange)
})
</script>

<template>
  <section v-if="showBanner" class="pwa-status-stack" :style="{ top: `${bannerTop}px` }" aria-label="应用状态" aria-live="polite">
    <p v-if="!isOnline" class="pwa-status-message is-offline" role="status">
      网络已断开。应用外壳可用；POI、路线和 AI 行程需要联网。
    </p>
    <p v-else-if="apiUnavailable" class="pwa-status-message is-api-unavailable" role="status">
      后端 API 暂不可达，数据和业务操作无法刷新；恢复后请重试刚才的操作。
    </p>
    <div v-if="updateAvailable" class="pwa-status-message is-update" role="status">
      <span>发现新版本，可立即更新或稍后使用。</span>
      <button type="button" @click="acceptUpdate">立即更新</button>
      <button type="button" class="pwa-secondary-action" @click="dismissUpdate">稍后</button>
    </div>
    <div v-if="installPromptAvailable" class="pwa-status-message is-install" role="status">
      <span>可将智慧文旅添加到主屏幕并以独立窗口启动。</span>
      <button type="button" @click="installApp">安装应用</button>
    </div>
    <p v-if="iosInstallHint" class="pwa-status-message is-install" role="status">
      可在 Safari 的分享菜单中选择“添加到主屏幕”。
    </p>
  </section>
</template>

<style scoped>
.pwa-status-stack {
  position: fixed;
  z-index: 70;
  left: 50%;
  display: grid;
  gap: 7px;
  width: min(560px, calc(100vw - 24px));
  transform: translateX(-50%);
  pointer-events: none;
}
.pwa-status-message {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 10px;
  margin: 0;
  padding: 10px 12px;
  border: 1px solid #c8d8eb;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 4px 18px rgb(16 35 62 / 18%);
  color: #263b56;
  font: 14px/1.45 system-ui, 'Segoe UI', 'Microsoft YaHei', sans-serif;
  pointer-events: auto;
}
/* Status-only messages contain no controls and must not cover map/workspace actions. */
.pwa-status-message.is-offline,
.pwa-status-message.is-api-unavailable {
  pointer-events: none;
}
.is-offline { border-color: #e6b566; background: #fff8e9; }
.is-api-unavailable { border-color: #e5aaa5; background: #fff3f2; }
.is-update { border-color: #8bb2ed; background: #eff6ff; }
.pwa-status-message button {
  min-width: 44px;
  min-height: 44px;
  padding: 8px 12px;
  border: 0;
  border-radius: 9px;
  background: #215fc5;
  color: #fff;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}
.pwa-status-message .pwa-secondary-action { background: #e9eff7; color: #263b56; }
.pwa-status-message button:focus-visible { outline: 3px solid #174f9f; outline-offset: 2px; }
@media (max-width: 600px) {
  .pwa-status-stack { width: calc(100vw - 20px); }
  .pwa-status-message { font-size: 14px; }
}
</style>
