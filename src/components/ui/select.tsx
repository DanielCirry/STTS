import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

interface SelectOptionGroup {
  label: string
  options: SelectOption[]
}

interface SelectProps {
  value: string
  onValueChange: (value: string) => void
  options: SelectOption[]
  groups?: SelectOptionGroup[]
  placeholder?: string
  disabled?: boolean
  className?: string
}

export function Select({
  value,
  onValueChange,
  options,
  groups,
  placeholder = 'Select...',
  disabled,
  className,
}: SelectProps) {
  const allOptions = groups
    ? groups.flatMap(g => g.options)
    : options
  const selectedOption = allOptions.find((opt) => opt.value === value)

  return (
    <div className={cn('relative', className)}>
      <select
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        disabled={disabled}
        className={cn(
          'flex h-9 w-full appearance-none items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm ring-offset-background',
          'placeholder:text-muted-foreground',
          'focus:outline-none focus:ring-1 focus:ring-ring',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'pr-8',
          '[&>option]:bg-background [&>option]:text-foreground',
          '[&>optgroup]:bg-background [&>optgroup]:text-foreground [&>optgroup]:font-semibold'
        )}
      >
        {placeholder && !selectedOption && (
          <option value="" disabled className="bg-background text-muted-foreground">
            {placeholder}
          </option>
        )}
        {groups ? (
          // Render grouped options
          groups.map((group) => (
            group.options.length > 0 && (
              <optgroup key={group.label} label={group.label} className="bg-background">
                {group.options.map((option) => (
                  <option
                    key={option.value}
                    value={option.value}
                    disabled={option.disabled}
                    className="bg-background text-foreground"
                  >
                    {option.label}
                  </option>
                ))}
              </optgroup>
            )
          ))
        ) : (
          // Render flat options
          options.map((option) => (
            <option
              key={option.value}
              value={option.value}
              disabled={option.disabled}
              className="bg-background text-foreground"
            >
              {option.label}
            </option>
          ))
        )}
      </select>
      <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 opacity-50 pointer-events-none" />
    </div>
  )
}
