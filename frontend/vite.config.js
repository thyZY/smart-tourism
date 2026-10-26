import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'

function pwaWorkerPlugin() {
  return {
    name: 'smart-tourism-pwa-worker',
    apply: 'build',
    generateBundle(_options, bundle) {
      const staticBundleFiles = Object.keys(bundle).filter(fileName =>
        fileName === 'index.html' ||
        /^assets\/.*\.(?:css|js|png|svg|webp|woff2?)$/i.test(fileName)
      )
      const precacheUrls = [
        '/',
        '/index.html',
        ...staticBundleFiles.map(fileName => `/${fileName}`),
        '/manifest.webmanifest',
        '/favicon.svg',
        '/icons/app-icon.svg',
        '/icons/app-icon-192.png',
        '/icons/app-icon-512.png'
      ]
      const uniquePrecacheUrls = [...new Set(precacheUrls)]
      const publicFiles = [
        'manifest.webmanifest',
        'favicon.svg',
        'icons/app-icon.svg',
        'icons/app-icon-192.png',
        'icons/app-icon-512.png'
      ]
      const contentFingerprints = [
        ...staticBundleFiles.map(fileName => {
          const output = bundle[fileName]
          const source = output.type === 'asset' ? output.source : output.code
          const bytes = Buffer.isBuffer(source) ? source : Buffer.from(source)
          return `${fileName}:${createHash('sha256').update(bytes).digest('hex')}`
        }),
        ...publicFiles.map(fileName => {
          const source = readFileSync(new URL(`./public/${fileName}`, import.meta.url))
          return `${fileName}:${createHash('sha256').update(source).digest('hex')}`
        })
      ]
      const cacheVersion = createHash('sha256')
        .update(`${uniquePrecacheUrls.join('\n')}\n${contentFingerprints.join('\n')}`)
        .digest('hex')
        .slice(0, 12)
      const workerTemplate = readFileSync(new URL('./src/pwa/sw.js', import.meta.url), 'utf8')
      const workerSource = workerTemplate
        .replace('__PRECACHE_URLS__', JSON.stringify(uniquePrecacheUrls))
        .replace('__CACHE_NAME__', JSON.stringify(`smart-tourism-shell-${cacheVersion}`))

      this.emitFile({ type: 'asset', fileName: 'sw.js', source: workerSource })
    }
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), pwaWorkerPlugin()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true
      }
    }
  }
})
