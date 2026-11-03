import { redirect } from 'next/navigation'

/**
 * `/support` 是菜单目录节点的路径，本身没有内容。
 *
 * 但它必须存在一个页面：GOV-06 要求每条菜单 path 都解析到 `(app)` 下的真实页面，
 * GOV-20 则要求每个页面都被某个模块的 route_prefix 覆盖——两条一起成立，
 * 才能保证"模块没装时手敲 URL 进不来"。
 */
export default function SupportIndexPage(): never {
  redirect('/support/tickets')
}
