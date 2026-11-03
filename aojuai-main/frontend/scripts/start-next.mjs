import net from 'node:net'
import { spawn } from 'node:child_process'
import path from 'node:path'

const DEFAULT_HOST = '0.0.0.0'
const RANDOM_PORT_HOST = '127.0.0.1'

function parsePort(value) {
  const raw = String(value || '').trim()
  if (!raw) return null
  const port = Number.parseInt(raw, 10)
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`Invalid PORT: ${raw}`)
  }
  return port
}

function reserveRandomPort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()

    server.on('error', reject)
    server.listen(0, RANDOM_PORT_HOST, () => {
      const address = server.address()
      if (!address || typeof address === 'string') {
        server.close(() => reject(new Error('Failed to resolve random port')))
        return
      }

      const { port } = address
      server.close((closeError) => {
        if (closeError) {
          reject(closeError)
          return
        }
        resolve(port)
      })
    })
  })
}

async function main() {
  const host = String(process.env.NEXT_HOST || DEFAULT_HOST).trim() || DEFAULT_HOST
  const explicitPort = parsePort(process.env.PORT)
  const port = explicitPort ?? (await reserveRandomPort())
  const nextBin = path.resolve(process.cwd(), 'node_modules', '.bin', 'next')

  if (!explicitPort) {
    console.error(`[aoju-next] PORT not provided, using random free port: ${port}`)
  }

  const child = spawn(nextBin, ['start', '-H', host, '-p', String(port)], {
    stdio: 'inherit',
    env: {
      ...process.env,
      PORT: String(port),
      NEXT_HOST: host,
    },
  })

  child.on('exit', (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal)
      return
    }
    process.exit(code ?? 0)
  })

  child.on('error', (error) => {
    console.error('[aoju-next] Failed to launch next start:', error)
    process.exit(1)
  })
}

main().catch((error) => {
  console.error('[aoju-next] Failed to resolve start parameters:', error)
  process.exit(1)
})
