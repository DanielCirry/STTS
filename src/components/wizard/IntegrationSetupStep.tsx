import { useEffect, useState } from 'react'
import { Button } from '../ui/button'
import { Label } from '../ui/label'
import { Switch } from '../ui/switch'
import { useBackend } from '../../hooks/useBackend'
import type { WizardData } from './SetupWizard'

interface IntegrationSetupStepProps {
  data: WizardData
  onUpdate: (updates: Partial<WizardData>) => void
  onNext: () => void
  onBack: () => void
}

interface OverlayStatus {
  available: boolean
}

export function IntegrationSetupStep({ data, onUpdate, onNext, onBack }: IntegrationSetupStepProps) {
  const { lastMessage } = useBackend()
  const [vrOverlayAvailable, setVrOverlayAvailable] = useState(false)

  useEffect(() => {
    if (lastMessage?.type === 'status') {
      const overlayStatus = lastMessage.payload?.vrOverlay as OverlayStatus | undefined
      if (overlayStatus) {
        setVrOverlayAvailable(overlayStatus.available)
      }
    }
  }, [lastMessage])

  return (
    <div className="space-y-6 max-w-lg mx-auto">
      <div className="text-center">
        <h2 className="text-2xl font-bold">Integrations</h2>
        <p className="text-muted-foreground mt-2">
          Configure VRChat and VR settings
        </p>
      </div>

      <div className="space-y-6">
        {/* VRChat Integration */}
        <div className="space-y-4 p-4 border rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <Label>VRChat Integration</Label>
              <p className="text-xs text-muted-foreground">
                Send text to VRChat chatbox via OSC
              </p>
            </div>
            <Switch
              checked={data.vrchatEnabled}
              onCheckedChange={(checked) => onUpdate({ vrchatEnabled: checked })}
            />
          </div>

          {data.vrchatEnabled && (
            <div className="pt-2 border-t text-sm text-muted-foreground space-y-2">
              <p>Make sure OSC is enabled in VRChat:</p>
              <ol className="list-decimal list-inside space-y-1 ml-2">
                <li>Open VRChat Action Menu</li>
                <li>Go to Options &gt; OSC</li>
                <li>Enable OSC</li>
              </ol>
            </div>
          )}
        </div>

        {/* VR Overlay */}
        <div className="space-y-4 p-4 border rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <Label>VR Overlay</Label>
              <p className="text-xs text-muted-foreground">
                Show text overlay in SteamVR
              </p>
            </div>
            <Switch
              checked={data.vrOverlayEnabled}
              onCheckedChange={(checked) => onUpdate({ vrOverlayEnabled: checked })}
              disabled={!vrOverlayAvailable}
            />
          </div>

          {!vrOverlayAvailable && (
            <p className="text-xs text-amber-500">
              VR overlay requires SteamVR to be installed and a VR headset connected.
            </p>
          )}

          {vrOverlayAvailable && data.vrOverlayEnabled && (
            <div className="pt-2 border-t text-sm text-muted-foreground">
              <p>The overlay will appear in front of you in VR, showing:</p>
              <ul className="list-disc list-inside mt-2 ml-2">
                <li>Your transcribed speech</li>
                <li>Translations</li>
                <li>AI assistant responses</li>
              </ul>
            </div>
          )}
        </div>

        {/* Info box */}
        <div className="bg-muted/50 p-4 rounded-lg text-sm">
          <p className="font-medium mb-2">Additional Features:</p>
          <ul className="space-y-1 text-muted-foreground">
            <li>- AI assistant with keyword activation (default: &quot;jarvis&quot;)</li>
            <li>- Speaker capture for transcribing game audio</li>
          </ul>
        </div>
      </div>

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
