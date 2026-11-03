import * as React from 'react'
import { Check, ChevronsUpDown, X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { useT } from '@/lib/i18n'
import { cn } from '@/lib/utils'

export type MultiSelectOption = {
  value: number | string
  label: string
  disabled?: boolean
  depth?: number
}

type MultiSelectProps = {
  options: MultiSelectOption[]
  value: (number | string)[]
  onChange: (value: (number | string)[]) => void
  placeholder?: string
  searchPlaceholder?: string
  emptyText?: string
  maxDisplay?: number
  disabled?: boolean
  className?: string
}

export function MultiSelect({
  options,
  value,
  onChange,
  placeholder,
  searchPlaceholder,
  emptyText,
  maxDisplay = 3,
  disabled = false,
  className,
}: MultiSelectProps) {
  const t = useT()
  const [open, setOpen] = React.useState(false)
  const resolvedPlaceholder = placeholder ?? t('system.common.selectPlaceholder')
  const resolvedSearchPlaceholder = searchPlaceholder ?? t('system.common.searchPlaceholder')
  const resolvedEmptyText = emptyText ?? t('system.common.noMatches')

  const selectedOptions = React.useMemo(() => {
    return options.filter((opt) => value.includes(opt.value))
  }, [options, value])

  const handleSelect = (optValue: number | string) => {
    const newValue = value.includes(optValue) ? value.filter((v) => v !== optValue) : [...value, optValue]
    onChange(newValue)
  }

  const handleRemove = (optValue: number | string, e: React.MouseEvent) => {
    e.stopPropagation()
    onChange(value.filter((v) => v !== optValue))
  }

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation()
    onChange([])
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className={cn('h-auto min-h-9 w-full justify-between font-normal', className)}
        >
          <div className="flex flex-1 flex-wrap gap-1">
            {selectedOptions.length === 0 ? (
              <span className="text-muted-foreground">{resolvedPlaceholder}</span>
            ) : selectedOptions.length <= maxDisplay ? (
              selectedOptions.map((opt) => (
                <Badge key={opt.value} variant="secondary" className="mr-1 mb-1">
                  {opt.label}
                  <button
                    type="button"
                    className="ml-1 rounded-full outline-none ring-offset-background focus:ring-2 focus:ring-ring focus:ring-offset-2"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={(e) => handleRemove(opt.value, e)}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))
            ) : (
              <Badge variant="secondary">{t('system.common.selectedCount').replace('{n}', String(selectedOptions.length))}</Badge>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {selectedOptions.length > 0 ? (
              <button
                type="button"
                className="rounded-full p-0.5 hover:bg-accent"
                onMouseDown={(e) => e.preventDefault()}
                onClick={handleClear}
              >
                <X className="h-4 w-4 text-muted-foreground" />
              </button>
            ) : null}
            <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" />
          </div>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-full min-w-[var(--radix-popover-trigger-width)] p-0" align="start">
        <Command>
          <CommandInput placeholder={resolvedSearchPlaceholder} />
          <CommandList>
            <CommandEmpty>{resolvedEmptyText}</CommandEmpty>
            <CommandGroup>
              {options.map((opt) => (
                <CommandItem
                  key={opt.value}
                  value={String(opt.value)}
                  disabled={opt.disabled}
                  onSelect={() => handleSelect(opt.value)}
                  className={cn(opt.depth && opt.depth > 0 && `pl-${2 + opt.depth * 4}`)}
                  style={opt.depth ? { paddingLeft: `${8 + opt.depth * 16}px` } : undefined}
                >
                  <Check className={cn('mr-2 h-4 w-4', value.includes(opt.value) ? 'opacity-100' : 'opacity-0')} />
                  {opt.depth && opt.depth > 0 ? `${'—'.repeat(opt.depth)} ` : ''}
                  {opt.label}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
