import { useState } from 'react'
import { WelcomeStep } from './WelcomeStep'
import { AudioSetupStep } from './AudioSetupStep'
import { ModelDownloadStep } from './ModelDownloadStep'
import { IntegrationSetupStep } from './IntegrationSetupStep'
import { CompletionStep } from './CompletionStep'

export interface WizardData {
  inputDevice: string | null
  outputDevice: string | null
  inputDeviceName: string | null
  outputDeviceName: string | null
  sttModel: string
  translationEnabled: boolean
  translationModel: string | null
  ttsEngine: string
  vrchatEnabled: boolean
  vrOverlayEnabled: boolean
}

const STEPS = [
  { id: 'welcome', title: 'Welcome' },
  { id: 'audio', title: 'Audio Setup' },
  { id: 'models', title: 'Models' },
  { id: 'integrations', title: 'Integrations' },
  { id: 'complete', title: 'Complete' },
]

interface SetupWizardProps {
  onComplete: (data: WizardData) => void
  onSkip?: () => void
}

export function SetupWizard({ onComplete, onSkip }: SetupWizardProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [data, setData] = useState<WizardData>({
    inputDevice: null,
    outputDevice: null,
    inputDeviceName: null,
    outputDeviceName: null,
    sttModel: 'tiny',
    translationEnabled: false,
    translationModel: null,
    ttsEngine: 'edge',
    vrchatEnabled: true,
    vrOverlayEnabled: false,
  })

  const updateData = (updates: Partial<WizardData>) => {
    setData(prev => ({ ...prev, ...updates }))
  }

  const nextStep = () => {
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(prev => prev + 1)
    }
  }

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1)
    }
  }

  const handleComplete = () => {
    onComplete(data)
  }

  const renderStep = () => {
    switch (STEPS[currentStep].id) {
      case 'welcome':
        return <WelcomeStep onNext={nextStep} onSkip={onSkip} />
      case 'audio':
        return (
          <AudioSetupStep
            data={data}
            onUpdate={updateData}
            onNext={nextStep}
            onBack={prevStep}
          />
        )
      case 'models':
        return (
          <ModelDownloadStep
            data={data}
            onUpdate={updateData}
            onNext={nextStep}
            onBack={prevStep}
          />
        )
      case 'integrations':
        return (
          <IntegrationSetupStep
            data={data}
            onUpdate={updateData}
            onNext={nextStep}
            onBack={prevStep}
          />
        )
      case 'complete':
        return (
          <CompletionStep
            data={data}
            onComplete={handleComplete}
            onBack={prevStep}
          />
        )
      default:
        return null
    }
  }

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Progress bar */}
      <div className="p-4 border-b">
        <div className="flex items-center justify-between mb-2">
          {STEPS.map((step, index) => (
            <div key={step.id} className="flex items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                  index < currentStep
                    ? 'bg-primary text-primary-foreground'
                    : index === currentStep
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                {index < currentStep ? '✓' : index + 1}
              </div>
              {index < STEPS.length - 1 && (
                <div
                  className={`w-16 h-1 mx-2 ${
                    index < currentStep ? 'bg-primary' : 'bg-muted'
                  }`}
                />
              )}
            </div>
          ))}
        </div>
        <div className="flex justify-between text-xs text-muted-foreground">
          {STEPS.map(step => (
            <span key={step.id} className="w-20 text-center">
              {step.title}
            </span>
          ))}
        </div>
      </div>

      {/* Step content */}
      <div className="flex-1 overflow-auto p-6">
        {renderStep()}
      </div>
    </div>
  )
}
