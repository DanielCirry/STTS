import { Button } from '../ui/button'
import type { WizardData } from './SetupWizard'

interface CompletionStepProps {
  data: WizardData
  onComplete: () => void
  onBack: () => void
}

export function CompletionStep({ data, onComplete, onBack }: CompletionStepProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <div className="max-w-md space-y-6">
        <div className="text-5xl">🎉</div>

        <h2 className="text-2xl font-bold">Setup Complete!</h2>
        <p className="text-muted-foreground">
          STTS is ready to use. Here&apos;s a summary of your configuration:
        </p>

        <div className="text-left bg-muted/50 p-4 rounded-lg space-y-3">
          <div>
            <p className="text-xs text-muted-foreground uppercase">Audio</p>
            <p className="text-sm">
              Input: {data.inputDeviceName || 'Default'}
            </p>
            <p className="text-sm">
              Output: {data.outputDeviceName || 'Default'}
            </p>
          </div>

          <div>
            <p className="text-xs text-muted-foreground uppercase">Speech Recognition</p>
            <p className="text-sm">Model: {data.sttModel}</p>
          </div>

          <div>
            <p className="text-xs text-muted-foreground uppercase">Translation</p>
            <p className="text-sm">
              {data.translationEnabled ? 'Enabled (NLLB-200)' : 'Disabled'}
            </p>
          </div>

          <div>
            <p className="text-xs text-muted-foreground uppercase">Text-to-Speech</p>
            <p className="text-sm">
              Engine: {data.ttsEngine === 'edge' ? 'Edge TTS' : data.ttsEngine === 'piper' ? 'Piper' : 'Windows SAPI'}
            </p>
          </div>

          <div>
            <p className="text-xs text-muted-foreground uppercase">Integrations</p>
            <p className="text-sm">
              VRChat: {data.vrchatEnabled ? 'Enabled' : 'Disabled'}
            </p>
            <p className="text-sm">
              VR Overlay: {data.vrOverlayEnabled ? 'Enabled' : 'Disabled'}
            </p>
          </div>
        </div>

        <div className="bg-primary/10 border border-primary/30 p-4 rounded-lg text-sm text-left">
          <p className="font-medium mb-1">Next step: Install Features</p>
          <p className="text-muted-foreground">
            Some features (Speech-to-Text, Translation, etc.) require additional downloads.
            You&apos;ll be taken to the Install Features page to set them up.
          </p>
        </div>

        <div className="space-y-2 text-sm text-muted-foreground">
          <p>
            You can adjust all settings later in the Settings tab.
          </p>
        </div>

        <div className="flex gap-4 justify-center pt-4">
          <Button variant="outline" onClick={onBack}>
            Back
          </Button>
          <Button onClick={onComplete}>
            Continue to Install Features
          </Button>
        </div>
      </div>
    </div>
  )
}
