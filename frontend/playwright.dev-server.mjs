import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'

export default async function startPlaywrightDevServer() {
  const server = await createServer({
    configFile: fileURLToPath(new URL('./vite.config.js', import.meta.url)),
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true
    }
  })

  await server.listen()
  return async () => {
    await server.close()
  }
}
