import { preview } from 'vite'
import { fileURLToPath } from 'node:url'

export default async function startPwaPreview() {
  const port = Number(process.env.PLAYWRIGHT_PWA_PORT || 4173)
  const server = await preview({
    configFile: fileURLToPath(new URL('./vite.config.js', import.meta.url)),
    preview: {
      host: '127.0.0.1',
      port,
      strictPort: true
    }
  })

  return async () => {
    await server.close()
  }
}
