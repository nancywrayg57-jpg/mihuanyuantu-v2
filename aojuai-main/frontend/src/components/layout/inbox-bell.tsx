'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { Bell } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { apiFetch } from '@/lib/api'

export function InboxBell() {
  const [unread, setUnread] = useState(0)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const data = await apiFetch<{ unreadCount?: number }>('/api/v1/realphotos/inbox')
        if (active) setUnread(Number(data.unreadCount || 0))
      } catch {
        if (active) setUnread(0)
      }
    }
    void load()
    const timer = window.setInterval(() => void load(), 60000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  return (
    <Button variant="outline" size="icon" className="relative shrink-0" asChild>
      <Link href="/realphotos/messages" aria-label={`消息中心，未读 ${unread}`}>
        <Bell className="h-4 w-4" />
        {unread > 0 ? (
          <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-destructive px-1 text-center text-[10px] leading-4 text-destructive-foreground">
            {unread > 99 ? '99+' : unread}
          </span>
        ) : null}
      </Link>
    </Button>
  )
}
