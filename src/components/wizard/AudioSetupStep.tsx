import { useEffect, useState, useRef } from 'react'
import { Button } from '../ui/button'
import { Label } from '../ui/label'
import { Select } from '../ui/select'
import { useBackend } from '../../hooks/useBackend'
import type { WizardData } from './SetupWizard'

interface AudioSetupStepProps {
  data: WizardData
  onUpdate: (updates: Partial<WizardData>) => void
  onNext: () => void
  onBack: () => void
}

interface AudioDevice {
  id: number
  name: string
  is_default?: boolean
  is_active?: boolean
  channels?: number
  sample_rate?: number
}

export function AudioSetupStep({ data, onUpdate, onNext, onBack }: AudioSetupStepProps) {
  const { sendMessage, lastMessage, testMicrophone, stopTestMicrophone, audioLevel, connected } = useBackend()
  const [inputDevices, setInputDevices] = useState<AudioDevice[]>([])
  const [outputDevices, setOutputDevices] = useState<AudioDevice[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [testingMic, setTestingMic] = useState(false)
  const [testingSpeaker, setTestingSpeaker] = useState(false)
  const audioContextRef = useRef<AudioContext | null>(null)

  useEffect(() => {
    // Request audio devices when connected (with small delay to ensure stable connection)
    if (connected) {
      const timer = setTimeout(() => {
        sendMessage({ type: 'get_audio_devices', payload: {} })
      }, 500)

      // Set up polling to detect new devices (every 3 seconds)
      const pollInterval = setInterval(() => {
        sendMessage({ type: 'get_audio_devices', payload: {} })
      }, 3000)

      return () => {
        clearTimeout(timer)
        clearInterval(pollInterval)
      }
    }
  }, [sendMessage, connected])

  useEffect(() => {
    if (lastMessage?.type === 'audio_devices') {
      const { inputs, outputs } = lastMessage.payload as { inputs: AudioDevice[], outputs: AudioDevice[] }
      setInputDevices(inputs || [])
      setOutputDevices(outputs || [])
      setIsLoading(false)

      // Set defaults if not already set
      if (!data.inputDevice) {
        const defaultInput = inputs?.find((d: AudioDevice) => d.is_default)
        if (defaultInput) {
          onUpdate({ inputDevice: String(defaultInput.id), inputDeviceName: defaultInput.name })
        }
      } else {
        // Update name for already-selected device (in case devices just loaded)
        const selected = inputs?.find((d: AudioDevice) => String(d.id) === data.inputDevice)
        if (selected && !data.inputDeviceName) {
          onUpdate({ inputDeviceName: selected.name })
        }
      }
      if (!data.outputDevice) {
        const defaultOutput = outputs?.find((d: AudioDevice) => d.is_default)
        if (defaultOutput) {
          onUpdate({ outputDevice: String(defaultOutput.id), outputDeviceName: defaultOutput.name })
        }
      } else {
        const selected = outputs?.find((d: AudioDevice) => String(d.id) === data.outputDevice)
        if (selected && !data.outputDeviceName) {
          onUpdate({ outputDeviceName: selected.name })
        }
      }
    }
  }, [lastMessage, data.inputDevice, data.outputDevice, onUpdate])

  const handleTestMic = () => {
    if (testingMic) {
      stopTestMicrophone()
      setTestingMic(false)
    } else {
      // Pass the selected device ID if available
      const deviceId = data.inputDevice ? parseInt(data.inputDevice, 10) : undefined
      testMicrophone(deviceId)
      setTestingMic(true)
    }
  }

  const handleTestSpeaker = async () => {
    if (testingSpeaker) return

    setTestingSpeaker(true)
    try {
      // Create audio context if needed
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext()
      }
      const ctx = audioContextRef.current

      // Create a simple beep sound
      const oscillator = ctx.createOscillator()
      const gainNode = ctx.createGain()

      oscillator.connect(gainNode)
      gainNode.connect(ctx.destination)

      oscillator.frequency.value = 440 // A4 note
      oscillator.type = 'sine'

      gainNode.gain.setValueAtTime(0.3, ctx.currentTime)
      gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5)

      oscillator.start(ctx.currentTime)
      oscillator.stop(ctx.currentTime + 0.5)

      // Wait for sound to finish
      await new Promise(resolve => setTimeout(resolve, 600))
    } catch (error) {
      console.error('Error testing speaker:', error)
    } finally {
      setTestingSpeaker(false)
    }
  }

  // Group devices by active/inactive status
  const createDeviceGroups = (devices: AudioDevice[]) => {
    const activeDevices = devices.filter(d => d.is_active !== false)
    const inactiveDevices = devices.filter(d => d.is_active === false)

    const groups = []

    if (activeDevices.length > 0) {
      groups.push({
        label: 'Available Devices',
        options: activeDevices.map((device) => ({
          value: String(device.id),
          label: `${device.name}${device.is_default ? ' (Default)' : ''}`,
        }))
      })
    }

    if (inactiveDevices.length > 0) {
      groups.push({
        label: 'Unavailable Devices',
        options: inactiveDevices.map((device) => ({
          value: String(device.id),
          label: device.name,
          disabled: true,
        }))
      })
    }

    return groups
  }

  const inputGroups = createDeviceGroups(inputDevices)
  const outputGroups = createDeviceGroups(outputDevices)

  // Flat options for backwards compatibility
  const inputOptions = [
    { value: '', label: 'System Default' },
    ...inputDevices.map((device) => ({
      value: String(device.id),
      label: `${device.name}${device.is_default ? ' (Default)' : ''}`,
    })),
  ]

  const outputOptions = [
    { value: '', label: 'System Default' },
    ...outputDevices.map((device) => ({
      value: String(device.id),
      label: `${device.name}${device.is_default ? ' (Default)' : ''}`,
    })),
  ]

  return (
    <div className="space-y-6 max-w-lg mx-auto">
      <div className="text-center">
        <h2 className="text-2xl font-bold">Audio Setup</h2>
        <p className="text-muted-foreground mt-2">
          Configure your microphone and speakers
        </p>
      </div>

      {isLoading ? (
        <div className="text-center py-8">
          <p className="text-muted-foreground">Loading audio devices...</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Input Device */}
          <div className="space-y-2">
            <Label htmlFor="input-device">Microphone</Label>
            <Select
              value={data.inputDevice || ''}
              onValueChange={(value) => {
                const device = inputDevices.find(d => String(d.id) === value)
                onUpdate({ inputDevice: value, inputDeviceName: device?.name || null })
              }}
              options={inputOptions}
              groups={inputGroups.length > 0 ? inputGroups : undefined}
              placeholder="Select microphone"
            />

            {/* Mic test */}
            <div className="space-y-2 mt-2">
              <div className="flex items-center gap-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleTestMic}
                  className={testingMic ? 'bg-red-500/20 border-red-500' : ''}
                >
                  {testingMic ? 'Stop Test' : 'Test Microphone'}
                </Button>
                {testingMic && (
                  <span className="text-xs text-muted-foreground">
                    Speak into your microphone...
                  </span>
                )}
              </div>
              {/* Always show mic level bar when testing */}
              {testingMic && (
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground w-12">Level:</span>
                    <div className="flex-1 h-3 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all duration-75 ${
                          audioLevel > 0.7 ? 'bg-red-500' : audioLevel > 0.3 ? 'bg-green-500' : 'bg-blue-500'
                        }`}
                        style={{ width: `${Math.max(audioLevel * 100, 2)}%` }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground w-10 text-right">
                      {Math.round(audioLevel * 100)}%
                    </span>
                  </div>
                  {audioLevel > 0.1 && (
                    <p className="text-xs text-green-500">Microphone is working!</p>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Output Device */}
          <div className="space-y-2">
            <Label htmlFor="output-device">Speakers/Headphones</Label>
            <Select
              value={data.outputDevice || ''}
              onValueChange={(value) => {
                const device = outputDevices.find(d => String(d.id) === value)
                onUpdate({ outputDevice: value, outputDeviceName: device?.name || null })
              }}
              options={outputOptions}
              groups={outputGroups.length > 0 ? outputGroups : undefined}
              placeholder="Select output device"
            />

            {/* Speaker test */}
            <div className="flex items-center gap-4 mt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleTestSpeaker}
                disabled={testingSpeaker}
                className={testingSpeaker ? 'bg-blue-500/20 border-blue-500' : ''}
              >
                {testingSpeaker ? 'Playing...' : 'Test Speaker'}
              </Button>
              <span className="text-xs text-muted-foreground">
                {testingSpeaker ? 'You should hear a beep' : 'Click to play a test tone'}
              </span>
            </div>
          </div>

          <div className="bg-muted/50 p-4 rounded-lg text-sm">
            <p className="font-medium mb-2">Tips:</p>
            <ul className="space-y-1 text-muted-foreground">
              <li>- Use a headset to prevent echo</li>
              <li>- Make sure your microphone is not muted</li>
              <li>- Test your mic to verify it&apos;s working</li>
            </ul>
          </div>
        </div>
      )}

      <div className="flex justify-between pt-4">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onNext}>
          Next
        </Button>
      </div>
    </div>
  )
}
