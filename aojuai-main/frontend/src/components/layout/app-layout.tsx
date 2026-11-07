'use client'

import type { ComponentType, ReactNode } from 'react'
import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  Bell,
  BookOpen,
  Copy,
  Cpu,
  ChevronRight,
  CalendarDays,
  Building2,
  Coins,
  Clock,
  Files,
  KeyRound,
  LayoutDashboard,
  Languages,
  LogOut,
  Menu,
  MessageCircle,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  PanelTop,
  Settings,
  Share2,
  Shield,
  Sun,
  Users,
  Workflow,
  ScrollText,
} from 'lucide-react'

import { InboxBell } from '@/components/layout/inbox-bell'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { getDemoModeMessage, isDemoMode } from '@/lib/demo'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { LOCALE_LABELS, SUPPORTED_LOCALES, useLocale, type Locale } from '@/lib/i18n'
import { useSiteBranding } from '@/hooks/useSiteBranding'
import { useTheme } from '@/hooks/useTheme'
import { type MenuRoute, useMenuRoutes } from '@/hooks/useMenuRoutes'
import { useTenant } from '@/hooks/useTenant'

type NavItem = {
  to: string
  label: string
  icon?: ComponentType<{ className?: string }>
}

type NavGroup = {
  id: string
  label: string
  icon?: ComponentType<{ className?: string }>
  pinned?: boolean
  items: NavItem[]
}

const BRAND_LOGO_SRC = '/logo.svg'
const DEFAULT_USER_AVATAR_SRC = '/avatar-ai.svg'

function resolveSessionDisplayName(session: { nickname?: string; username?: string } | null | undefined, fallback: string) {
  return session?.nickname || session?.username || fallback
}

function resolveSessionAvatarSrc(avatar: string | null | undefined) {
  const value = String(avatar || '').trim()
  return value || DEFAULT_USER_AVATAR_SRC
}

function routeTitle(route: MenuRoute) {
  return route.meta?.title || route.name || route.path
}

function isRouteVisible(route: MenuRoute) {
  const meta = route.meta || {}
  if (meta.hidden === true) return false
  if (meta.showLink === false) return false
  return true
}

function iconFromBackendKey(iconKey: string | null | undefined) {
  const map: Record<string, ComponentType<{ className?: string }>> = {
    'ep:alarm-clock': Clock,
    'ep:bell': Bell,
    'ep:calendar': CalendarDays,
    'ep:coin': Coins,
    'ep:collection': BookOpen,
    'ep:cpu': Cpu,
    'ep:files': Files,
    'ep:document': ScrollText,
    'ep:document-copy': Copy,
    'ep:chat-dot-round': MessageCircle,
    'ep:key': KeyRound,
    'ep:menu': PanelTop,
    'ep:office-building': Building2,
    'ep:setting': Settings,
    'ep:share': Share2,
    'ep:user': Users,
    'ep:user-filled': Shield,
    'ep:aim': Workflow,
  }
  if (!iconKey) return PanelTop
  return map[iconKey] ?? PanelTop
}

function collectLeafRoutes(routes: MenuRoute[]): MenuRoute[] {
  const out: MenuRoute[] = []
  for (const r of routes) {
    if (!isRouteVisible(r)) continue
    const children = (r.children || []).filter(isRouteVisible)
    if (children.length > 0) {
      out.push(...collectLeafRoutes(children))
      continue
    }
    out.push(r)
  }
  return out
}

export function AppLayout({ children }: { children: ReactNode }) {
  const { session, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const { tenants, targetTenant, targetTenantId, setTargetTenantId, loading: tenantLoading } = useTenant()
  const branding = useSiteBranding(targetTenant?.name || undefined)
  const { routes: menuRoutes, loading: menuRoutesLoading, error: menuRoutesError } = useMenuRoutes()
  const router = useRouter()
  const pathname = usePathname()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  // 手风琴互斥：undefined = 跟随当前路由所在分组，null = 全部收起
  const [expandedGroupId, setExpandedGroupId] = useState<string | null | undefined>(undefined)
  const { locale, setLocale, t, tMenu } = useLocale()
  const sessionDisplayName = resolveSessionDisplayName(session, t('system.layout.accountFallback'))
  const sessionAvatarSrc = resolveSessionAvatarSrc(session?.avatar)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const saved = window.localStorage.getItem('aoju.sidebar.collapsed')
    if (saved === '1') setSidebarCollapsed(true)
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem('aoju.sidebar.collapsed', sidebarCollapsed ? '1' : '0')
  }, [sidebarCollapsed])

  const isNavItemActive = (to: string) => (
    to === '/' ? pathname === '/' : pathname === to || pathname.startsWith(`${to}/`)
  )

  const visibleGroups = useMemo<NavGroup[]>(() => {
    const groups: NavGroup[] = [
      {
        id: 'overview',
        label: t('system.layout.overview'),
        icon: LayoutDashboard,
        pinned: true,
        items: [{ to: '/welcome', label: t('system.layout.home'), icon: LayoutDashboard }],
      },
    ]

    for (const root of (menuRoutes || []).filter(isRouteVisible)) {
      const children = root.children || []
      const visibleChildren = children.filter(isRouteVisible)
      const leafRoutes = collectLeafRoutes(visibleChildren)
      const sources = leafRoutes.length ? leafRoutes : children.length ? [] : [root]
      const items = sources.map((r) => ({
        to: r.path,
        label: routeTitle(r),
        icon: iconFromBackendKey(r.meta?.icon ?? null),
      }))
      if (items.length > 0) {
        groups.push({
          id: `menu:${root.path || routeTitle(root)}`,
          label: routeTitle(root),
          icon: iconFromBackendKey(root.meta?.icon ?? visibleChildren[0]?.meta?.icon ?? null),
          items,
        })
      }
    }

    const usedPaths = new Set(groups.flatMap((g) => g.items.map((i) => i.to)))
    const demoItems: NavItem[] = [
      { to: '/schedule', label: t('system.layout.schedule'), icon: CalendarDays },
      { to: '/permission/page', label: t('system.layout.pagePermission'), icon: Shield },
      { to: '/permission/button', label: t('system.layout.buttonPermission'), icon: KeyRound },
      { to: '/system/dict', label: t('system.layout.dict'), icon: BookOpen },
      { to: '/tenant/package/index', label: t('system.layout.tenantPackage'), icon: Building2 },
    ]
    const missingDemoItems = demoItems.filter((i) => !usedPaths.has(i.to))
    if (missingDemoItems.length) {
      groups.push({
        id: 'demo',
        label: t('system.layout.demo'),
        icon: Shield,
        items: missingDemoItems,
      })
    }

    return groups
  }, [menuRoutes, t])

  const renderNav = (options: { compact: boolean; allowCollapseToggle: boolean }) => {
    const { compact, allowCollapseToggle } = options
    return (
      <div className="flex h-full flex-col">
        <div
          className={cn(
            'flex h-14 items-center border-b',
            compact ? 'justify-center px-2' : 'justify-between px-3',
          )}
        >
          <Link
            href="/welcome"
            className={cn(
              'flex min-w-0 items-center gap-2',
              compact ? 'justify-center' : 'flex-1',
            )}
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-lg border bg-background/80">
              <img src={BRAND_LOGO_SRC} alt={branding.title} className="h-7 w-7" />
            </span>
            {!compact ? <span className="truncate font-semibold tracking-tight">{branding.title}</span> : null}
          </Link>
          {allowCollapseToggle ? (
            <Button
              variant="ghost"
              size="icon"
              className={cn('hidden h-8 w-8 md:inline-flex', compact && 'ml-0')}
              onClick={() => setSidebarCollapsed((prev) => !prev)}
              title={compact ? t('nav.expandSidebar') : t('nav.collapseSidebar')}
            >
              {compact ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            </Button>
          ) : null}
        </div>
        <ScrollArea className="flex-1">
          <nav className={cn('space-y-2 p-2', compact && 'space-y-1 p-1.5')}>
            {menuRoutesError ? (
              <div className="px-3 py-2 text-xs text-destructive">{t('nav.menuLoadFailed')}{menuRoutesError}</div>
            ) : null}
            {menuRoutesLoading ? (
              <div className="px-3 py-2 text-xs text-muted-foreground">{t('nav.loadingMenus')}</div>
            ) : null}
            {visibleGroups.map((group) => {
              const groupId = group.id
              const GroupIcon = group.icon || PanelTop
              const pinned = Boolean(group.pinned)
              const active = group.items.some((item) => isNavItemActive(item.to))
              // 手风琴互斥：未做选择时跟随当前路由所在分组；pinned 分组常开
              const expanded = pinned ? true : expandedGroupId === undefined ? active : expandedGroupId === groupId
              const collapsed = !expanded
              const canToggle = !pinned

              if (compact) {
                // 收起态：分组变为飞出菜单，二级直接可达
                const singleItem = group.items.length === 1 ? group.items[0] : null
                if (singleItem) {
                  return (
                    <Link
                      key={groupId}
                      href={singleItem.to}
                      onClick={() => setMobileNavOpen(false)}
                      title={tMenu(group.label)}
                      className={cn(
                        'flex h-8 w-full items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground',
                        active && 'bg-primary/10 text-primary',
                      )}
                    >
                      <GroupIcon className="h-4 w-4 shrink-0" />
                    </Link>
                  )
                }
                return (
                  <DropdownMenu key={groupId}>
                    <DropdownMenuTrigger asChild>
                      <button
                        type="button"
                        title={tMenu(group.label)}
                        className={cn(
                          'flex h-8 w-full items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground',
                          active && 'bg-primary/10 text-primary',
                        )}
                      >
                        <GroupIcon className="h-4 w-4 shrink-0" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent side="right" align="start" sideOffset={6} className="min-w-44">
                      <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">{tMenu(group.label)}</div>
                      {group.items.map((item) => (
                        <DropdownMenuItem key={item.to} asChild>
                          <Link
                            href={item.to}
                            className={cn(isNavItemActive(item.to) && 'bg-primary/10 text-primary')}
                          >
                            {item.icon ? <item.icon className="mr-2 h-4 w-4" /> : null}
                            {tMenu(item.label)}
                          </Link>
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                )
              }

              return (
                <div key={groupId} className="border-b border-border/40 pb-1.5 last:border-0 last:pb-0">
                  <button
                    type="button"
                    disabled={!canToggle}
                    onClick={() => setExpandedGroupId(expanded ? null : groupId)}
                    className={cn(
                      'flex h-8 w-full items-center gap-2 rounded-md px-2 text-sm font-semibold text-foreground/85 transition-colors',
                      active && 'text-foreground',
                      canToggle ? 'hover:bg-muted/60' : 'cursor-default',
                    )}
                  >
                    <GroupIcon className={cn('h-4 w-4 shrink-0 text-muted-foreground', active && 'text-primary')} />
                    <span className="truncate">{tMenu(group.label)}</span>
                    {canToggle ? (
                      <ChevronRight
                        className={cn(
                          'ml-auto h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform',
                          collapsed ? 'rotate-0' : 'rotate-90',
                        )}
                      />
                    ) : null}
                  </button>
                  {!collapsed ? (
                    <div className="mt-0.5 space-y-0.5">
                      {group.items.map((item) => {
                        const itemActive = isNavItemActive(item.to)
                        return (
                          <Link
                            key={item.to}
                            href={item.to}
                            onClick={() => setMobileNavOpen(false)}
                            className={cn(
                              'relative flex h-8 items-center gap-2 rounded-md pl-4 pr-2 text-sm font-medium transition-colors',
                              itemActive
                                ? 'bg-primary/10 text-primary'
                                : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
                            )}
                          >
                            {itemActive ? (
                              <span className="absolute left-1 top-1/2 h-3.5 w-0.5 -translate-y-1/2 rounded-full bg-primary" />
                            ) : null}
                            {item.icon ? (
                              <item.icon className={cn('h-4 w-4 shrink-0', !itemActive && 'text-muted-foreground/80')} />
                            ) : null}
                            <span className="truncate">{tMenu(item.label)}</span>
                          </Link>
                        )
                      })}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </nav>
        </ScrollArea>
      </div>
    )
  }

  const nav = renderNav({
    compact: sidebarCollapsed,
    allowCollapseToggle: true,
  })

  return (
    <div className="min-h-screen overflow-x-hidden bg-background text-foreground">
      <div className="flex min-h-screen max-w-full overflow-x-hidden">
        <aside
          className={cn(
            'hidden border-r bg-muted/30 transition-[width] duration-200 lg:block',
            sidebarCollapsed ? 'w-16' : 'w-60',
          )}
        >
          {nav}
        </aside>

        <main className="flex min-w-0 flex-1 flex-col overflow-x-hidden">
          <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b bg-background/80 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/70">
            <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
              <SheetTrigger asChild>
                <Button variant="outline" size="icon" className="lg:hidden">
                  <Menu className="h-4 w-4" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-80 p-0">
                <SheetHeader className="px-4 py-4">
                  <SheetTitle>{t('nav.title')}</SheetTitle>
                </SheetHeader>
                {renderNav({ compact: false, allowCollapseToggle: false })}
              </SheetContent>
            </Sheet>

            <div className="min-w-0 flex-1 overflow-hidden">
              <div className="flex items-center gap-2 text-sm">
                <div className="truncate font-medium">{sessionDisplayName}</div>
                <div className="text-muted-foreground">{session?.isSuperuser ? t('role.superuser') : t('role.user')}</div>
                {session?.isSuperuser ? (
                  <div className="ml-2 hidden items-center gap-2 text-muted-foreground sm:flex">
                    <span>{t('topbar.targetTenant')}</span>
                    <div className="w-56">
                      <Select
                        value={targetTenantId ? String(targetTenantId) : ''}
                        onValueChange={(v) => setTargetTenantId(Number(v))}
                        disabled={tenantLoading || tenants.length === 0}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder={tenantLoading ? t('common.loading') : t('topbar.selectTenant')} />
                        </SelectTrigger>
                        <SelectContent>
                          {tenants.map((t) => (
                            <SelectItem key={t.id} value={String(t.id)}>
                              {t.name} ({t.code})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    {targetTenant ? (
                      <span className="hidden truncate text-xs md:inline">
                        #{targetTenant.id}
                      </span>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>

            {isDemoMode() ? (
              <Badge
                variant="outline"
                className="shrink-0"
                title={getDemoModeMessage()}
              >
                {t('system.layout.demoMode')}
              </Badge>
            ) : null}

            <InboxBell />

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="secondary" className="gap-2 pl-2 pr-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full border bg-muted">
                    <img src={sessionAvatarSrc} alt={sessionDisplayName} className="h-full w-full object-cover" />
                  </span>
                  <span className="hidden max-w-40 truncate sm:inline">{sessionDisplayName}</span>
                  <span className="sm:hidden">{t('topbar.menu')}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {session?.isSuperuser && targetTenant ? (
                  <>
                    <div className="px-2 py-1.5 text-xs text-muted-foreground">
                      {t('system.layout.targetTenant')
                        .replace('{name}', targetTenant.name)
                        .replace('{code}', targetTenant.code)}
                    </div>
                    <DropdownMenuSeparator />
                  </>
                ) : null}
                {session?.isSuperuser && tenants.length > 0 ? (
                  <>
                    <DropdownMenuSub>
                      <DropdownMenuSubTrigger>{t('system.layout.switchTenant')}</DropdownMenuSubTrigger>
                      <DropdownMenuPortal>
                        <DropdownMenuSubContent className="max-h-80 overflow-auto">
                          <DropdownMenuRadioGroup
                            value={targetTenantId ? String(targetTenantId) : ''}
                            onValueChange={(v) => setTargetTenantId(Number(v))}
                          >
                            {tenants.map((t) => (
                              <DropdownMenuRadioItem key={t.id} value={String(t.id)}>
                                {t.name} ({t.code})
                              </DropdownMenuRadioItem>
                            ))}
                          </DropdownMenuRadioGroup>
                        </DropdownMenuSubContent>
                      </DropdownMenuPortal>
                    </DropdownMenuSub>
                    <DropdownMenuSeparator />
                  </>
                ) : null}
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>
                    {theme === 'dark' ? <Moon className="mr-2 h-4 w-4" /> : <Sun className="mr-2 h-4 w-4" />}
                    {t('topbar.theme')}
                  </DropdownMenuSubTrigger>
                  <DropdownMenuPortal>
                    <DropdownMenuSubContent>
                      <DropdownMenuRadioGroup value={theme} onValueChange={(v) => setTheme(v as 'light' | 'dark')}>
                        <DropdownMenuRadioItem value="light">
                          <Sun className="mr-2 h-4 w-4" />
                          {t('topbar.themeLight')}
                        </DropdownMenuRadioItem>
                        <DropdownMenuRadioItem value="dark">
                          <Moon className="mr-2 h-4 w-4" />
                          {t('topbar.themeDark')}
                        </DropdownMenuRadioItem>
                      </DropdownMenuRadioGroup>
                    </DropdownMenuSubContent>
                  </DropdownMenuPortal>
                </DropdownMenuSub>
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>
                    <Languages className="mr-2 h-4 w-4" />
                    {t('topbar.language')}
                  </DropdownMenuSubTrigger>
                  <DropdownMenuPortal>
                    <DropdownMenuSubContent>
                      <DropdownMenuRadioGroup value={locale} onValueChange={(v) => setLocale(v as Locale)}>
                        {SUPPORTED_LOCALES.map((item) => (
                          <DropdownMenuRadioItem key={item} value={item}>
                            {t(LOCALE_LABELS[item])}
                          </DropdownMenuRadioItem>
                        ))}
                      </DropdownMenuRadioGroup>
                    </DropdownMenuSubContent>
                  </DropdownMenuPortal>
                </DropdownMenuSub>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => {
                    logout()
                    router.replace('/login')
                  }}
                >
                  <LogOut className="mr-2 h-4 w-4" />
                  {t('auth.logout')}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </header>
          <div className="min-w-0 flex-1 p-3 md:p-4">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
