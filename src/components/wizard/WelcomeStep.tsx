import { Button } from '../ui/button'

interface WelcomeStepProps {
  onNext: () => void
  onSkip?: () => void
}

export function WelcomeStep({ onNext, onSkip }: WelcomeStepProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <div className="max-w-md space-y-6">
        <h1 className="text-3xl font-bold">Welcome to STTS</h1>
        <p className="text-muted-foreground">
          Speech-to-Text-to-Speech for VRChat
        </p>

        <div className="space-y-4 text-left bg-muted/50 p-4 rounded-lg">
          <h2 className="font-semibold">Features:</h2>
          <ul className="space-y-2 text-sm">
            <li className="flex items-center gap-2">
              <span className="text-primary">●</span>
              <span>Real-time speech recognition</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-primary">●</span>
              <span>Translation between 200+ languages</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-primary">●</span>
              <span>Text-to-speech with multiple voices</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-primary">●</span>
              <span>AI assistant with keyword activation</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-primary">●</span>
              <span>VRChat chatbox integration</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-primary">●</span>
              <span>VR overlay for SteamVR</span>
            </li>
          </ul>
        </div>

        <p className="text-sm text-muted-foreground">
          This wizard will help you set up STTS for the first time.
          It will configure your audio devices, download required models,
          and set up integrations.
        </p>

        <div className="flex gap-4 justify-center pt-4">
          {onSkip && (
            <Button variant="outline" onClick={onSkip}>
              Skip Setup
            </Button>
          )}
          <Button onClick={onNext}>
            Get Started
          </Button>
        </div>
      </div>
    </div>
  )
}
