import { redirect } from 'next/navigation'

/**
 * `/realphotos` 是菜单目录节点。S0 仅后端地基；本页满足 GOV-06/GOV-20。
 */
export default function RealphotosIndexPage(): never {
  redirect('/realphotos/workspace')
}
