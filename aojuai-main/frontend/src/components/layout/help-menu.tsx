'use client'

import Link from 'next/link'
import { useState } from 'react'
import { BookOpen, HelpCircle, LifeBuoy, RotateCcw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { RpDialog } from '@/components/realphotos/rp-table'

/** 2026-11-18 UX-P2-6：顶栏帮助入口，与右下角 AI 助手并存。 */
export function HelpMenu() {
  const [faqOpen, setFaqOpen] = useState(false)

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="帮助" title="帮助">
            <HelpCircle className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-44">
          <DropdownMenuItem asChild>
            <a href="/realphotos/workspace?guide=1">
              <BookOpen className="mr-2 h-4 w-4" />
              快速上手
            </a>
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setFaqOpen(true)}>
            <HelpCircle className="mr-2 h-4 w-4" />
            常见问题
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href="/support">
              <LifeBuoy className="mr-2 h-4 w-4" />
              联系客服
            </Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <a href="/realphotos/workspace?guide=1">
              <RotateCcw className="mr-2 h-4 w-4" />
              重看新手引导
            </a>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {faqOpen ? (
        <RpDialog title="帮助 · 常见问题" label="帮助与常见问题" onClose={() => setFaqOpen(false)}>
          <div className="space-y-3">
            <section>
              <h3 className="font-medium">三步完成第一张原图</h3>
              <ol className="mt-1 list-inside list-decimal space-y-1 text-xs text-muted-foreground">
                <li>在「图片资源」上传或 URL 导入图片。</li>
                <li>在「批量原图」选择设备预设，确认张数与预计扣分。</li>
                <li>提交后在「任务详情」查看检测报告与下载结果。</li>
              </ol>
            </section>
            <section>
              <h3 className="font-medium">为什么积分被冻结 / 扣减？</h3>
              <p className="mt-1 text-xs text-muted-foreground">
                处理任务提交时按 10 积分/张冻结；检测通过并交付后从冻结里扣减，未通过或失败按规则释放。
                「积分与充值」页可查看冻结变动、变动后余额与关联任务。
              </p>
            </section>
            <section>
              <h3 className="font-medium">检测未通过怎么办？</h3>
              <p className="mt-1 text-xs text-muted-foreground">
                在任务详情勾选任务后点「重新处理」，或按检测报告的建议调整预设参数后重新提交。
                图片被锁定时，可在「图片资源」对锁定图片提交申诉。
              </p>
            </section>
            <section>
              <h3 className="font-medium">下载与保留期</h3>
              <p className="mt-1 text-xs text-muted-foreground">
                结果经资源网关下载，不生成 ZIP；消息保留 30 天，结果文件请在保留期内保存。
              </p>
            </section>
            <div className="flex flex-wrap gap-2 border-t pt-3">
              <Link className="rp-btn rp-btn-primary rp-btn-sm" href="/realphotos/batch">
                去批量原图
              </Link>
              <Link className="rp-btn rp-btn-sm" href="/realphotos/messages">
                打开消息中心
              </Link>
              <Link className="rp-btn rp-btn-sm" href="/support">
                联系客服
              </Link>
            </div>
          </div>
        </RpDialog>
      ) : null}
    </>
  )
}
