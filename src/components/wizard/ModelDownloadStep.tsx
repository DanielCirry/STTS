import { useState } from 'react'
import { Button } from '../ui/button'
import { Label } from '../ui/label'
import { Switch } from '../ui/switch'
import { Select } from '../ui/select'
import type { WizardData } from './SetupWizard'

interface ModelDownloadStepProps {
  data: WizardData
  onUpdate: (updates: Partial<WizardData>) => void
  onNext: () => void
  onBack: () => void
}

const STT_MODELS = [
  { id: 'tiny', name: 'Tiny (~75MB)', description: 'Fastest, lower accuracy', recommended: false },
  { id: 'base', name: 'Base (~145MB)', description: 'Fast, good accuracy', recommended: true },
  { id: 'small', name: 'Small (~500MB)', description: 'Balanced speed/accuracy', recommended: false },
  { id: 'medium', name: 'Medium (~1.5GB)', description: 'High accuracy, slower', recommended: false },
  { id: 'large-v3', name: 'Large V3 (~3GB)', description: 'Best accuracy, slowest', recommended: false },
]

const TTS_ENGINES = [
  { id: 'edge', name: 'Edge TTS (Online)', description: 'Microsoft neural voices, requires internet', recommended: true },
  { id: 'piper', name: 'Piper (Offline)', description: 'Local neural voices, no internet needed', recommended: false },
  { id: 'sapi', name: 'Windows SAPI', description: 'Built-in Windows voices', recommended: false },
]

export function ModelDownloadStep({ data, onUpdate, onNext, onBack }: ModelDownloadStepProps) {
  const [downloading, setDownloading] = useState(false)

  const handleDownloadModels = async () => {
    setDownloading(true)
    // In a real implementation, this would trigger model downloads
    // For now, we just simulate a delay
    await new Promise(resolve => setTimeout(resolve, 1000))
    setDownloading(false)
    onNext()
  }

  const sttOptions = STT_MODELS.map((model) => ({
    value: model.id,
    label: `${model.name}${model.recommended ? ' (Recommended)' : ''}`,
  }))

  const ttsOptions = TTS_ENGINES.map((engine) => ({
    value: engine.id,
    label: `${engine.name}${engine.recommended ? ' (Recommended)' : ''}`,
  }))

  return (
    <div className="space-y-6 max-w-lg mx-auto">
      <div className="text-center">
        <h2 className="text-2xl font-bold">Model Setup</h2>
        <p className="text-muted-foreground mt-2">
          Choose which AI models to use
        </p>
      </div>

      <div className="space-y-6">
        {/* STT Model Selection */}
        <div className="space-y-2">
          <Label>Speech Recognition Model</Label>
          <Select
            value={data.sttModel}
            onValueChange={(value) => onUpdate({ sttModel: value })}
            options={sttOptions}
            placeholder="Select model"
          />
          <p className="text-xs text-muted-foreground">
            {STT_MODELS.find(m => m.id === data.sttModel)?.description}
          </p>
        </div>

        {/* Translation */}
        <div className="space-y-4 p-4 border rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <Label>Translation</Label>
              <p className="text-xs text-muted-foreground">
                Translate speech to another language
              </p>
            </div>
            <Switch
              checked={data.translationEnabled}
              onCheckedChange={(checked) => onUpdate({
                translationEnabled: checked,
                translationModel: checked ? 'nllb-200-distilled-600M' : null
              })}
            />
          </div>

          {data.translationEnabled && (
            <div className="pt-2 border-t">
              <p className="text-sm text-muted-foreground">
                NLLB translation model (~1.2GB) will be downloaded.
                Supports 200+ languages including English, Japanese, Korean, Chinese, and more.
              </p>
            </div>
          )}
        </div>

        {/* TTS Engine Selection */}
        <div className="space-y-2">
          <Label>Text-to-Speech Engine</Label>
          <Select
            value={data.ttsEngine}
            onValueChange={(value) => onUpdate({ ttsEngine: value })}
            options={ttsOptions}
            placeholder="Select TTS engine"
          />
          <p className="text-xs text-muted-foreground">
            {TTS_ENGINES.find(e => e.id === data.ttsEngine)?.description}
          </p>
        </div>

        {/* Download info */}
        <div className="bg-muted/50 p-4 rounded-lg text-sm">
          <p className="font-medium mb-2">Download Summary:</p>
          <ul className="space-y-1 text-muted-foreground">
            <li>- STT Model: {STT_MODELS.find(m => m.id === data.sttModel)?.name}</li>
            {data.translationEnabled && (
              <li>- Translation Model: NLLB-200 (~1.2GB)</li>
            )}
            {data.ttsEngine === 'piper' && (
              <li>- Piper TTS: Voice models will be downloaded separately</li>
            )}
          </ul>
          <p className="mt-2 text-xs">
            Models will be downloaded on first use.
          </p>
        </div>
      </div>

      <div className="flex justify-between pt-4">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button onClick={handleDownloadModels} disabled={downloading}>
          {downloading ? 'Preparing...' : 'Next'}
        </Button>
      </div>
    </div>
  )
}
