import { Command } from '@tauri-apps/plugin-shell'

let backendProcess: Awaited<ReturnType<typeof Command.prototype.spawn>> | null = null

export async function startBackend(): Promise<boolean> {
  if (backendProcess) {
    return true
  }

  try {
    // In development, run python directly
    // In production, this would be a bundled executable
    const command = Command.create('python', ['python/main.py', '9876'])

    command.on('close', () => {
      backendProcess = null
    })

    command.on('error', (error) => {
      console.error('Backend process error:', error)
    })

    command.stdout.on('data', () => {
      // Backend stdout captured but not logged
    })

    command.stderr.on('data', (line) => {
      console.error('[Backend Error]', line)
    })

    backendProcess = await command.spawn()

    // Wait a bit for the server to start
    await new Promise((resolve) => setTimeout(resolve, 1000))

    return true
  } catch (error) {
    console.error('Failed to start backend:', error)
    return false
  }
}

export async function stopBackend(): Promise<void> {
  if (backendProcess) {
    await backendProcess.kill()
    backendProcess = null
  }
}

export function isBackendRunning(): boolean {
  return backendProcess !== null
}
