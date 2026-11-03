'use client'

import { useMemo, type ReactNode } from 'react'
import { usePathname } from 'next/navigation'
import { PackageX } from 'lucide-react'

import { Card, CardContent } from '@/components/ui/card'
import { useTenant } from '@/hooks/useTenant'
import { resolveRouteBlock } from '@/lib/feature-switches'
import { useT } from '@/lib/i18n'

/**
 * 模块路由守卫：未安装 / 未启用的模块，直接敲 URL 也进不去。
 *
 * 为什么需要它：菜单会按开关过滤，但 Next 的 App Router 把 `(app)` 下所有页面
 * 都编译进产物，用户手敲 `/cms/pages` 照样能渲染出页面壳——接口全 404，
 * 界面就是一堆报错。守卫把这条路堵上，与后端"未装即 404"保持一致。
 *
 * **它不是安全边界**，只是 UX：真正的门禁在后端（未装的模块连路由都不挂载）。
 * 所以这里刻意 fail-open——目录还没加载完、或目录接口失败回落到构建期 fallback 时，
 * 一律放行，宁可多渲染一次也不要闪一下"不可用"。
 */
export function ModuleRouteGuard({ children }: { children: ReactNode }) {
  const t = useT()
  const pathname = usePathname()
  const { featureCatalog, featureSwitches, featureSwitchesLoading } = useTenant()

  const blocked = useMemo(() => {
    // 开关还没到位就别下结论，否则首屏会闪一下"未启用"。
    if (featureSwitchesLoading || !featureSwitches) return null
    return resolveRouteBlock(pathname || '/', featureCatalog, featureSwitches)
  }, [pathname, featureCatalog, featureSwitches, featureSwitchesLoading])

  if (!blocked) return <>{children}</>

  return (
    <Card className="mx-auto mt-16 max-w-md">
      <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
        <PackageX className="h-8 w-8 text-muted-foreground" />
        <p className="text-base font-medium">
          {blocked.reason === 'uninstalled'
            ? t('system.moduleGuard.uninstalledTitle')
            : t('system.moduleGuard.disabledTitle')}
        </p>
        <p className="text-sm text-muted-foreground">
          {(blocked.reason === 'uninstalled'
            ? t('system.moduleGuard.uninstalledHint')
            : t('system.moduleGuard.disabledHint')
          ).replace('{code}', blocked.code)}
        </p>
      </CardContent>
    </Card>
  )
}
