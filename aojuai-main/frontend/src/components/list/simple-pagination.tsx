import { useT } from '@/lib/i18n'
import { Button } from '@/components/ui/button'

export function SimplePagination({
  total,
  currentPage,
  pageSize,
  onChange,
  disabled,
}: {
  total: number
  currentPage: number
  pageSize: number
  onChange: (nextPage: number) => void
  disabled?: boolean
}) {
  const t = useT()
  const hasPrev = currentPage > 1
  const hasNext = currentPage * pageSize < total

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div className="text-sm text-muted-foreground">{t('common.totalItems').replace('{n}', String(total))}</div>
      <div className="flex w-full gap-2 sm:w-auto sm:items-center">
        <Button
          variant="outline"
          className="flex-1 sm:flex-none"
          disabled={disabled || !hasPrev}
          onClick={() => onChange(Math.max(1, currentPage - 1))}
        >
          {t('common.prevPage')}
        </Button>
        <Button
          variant="outline"
          className="flex-1 sm:flex-none"
          disabled={disabled || !hasNext}
          onClick={() => onChange(currentPage + 1)}
        >
          {t('common.nextPage')}
        </Button>
      </div>
    </div>
  )
}
