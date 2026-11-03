'use client'

import { Render } from '@measured/puck'
import type { Data } from '@measured/puck'

import { puckConfig } from '@/components/cms/puck-config'

/** Renders a Puck document with the shared CMS component config. */
export function CmsPageRender({ data }: { data: Data }) {
  if (!data || !Array.isArray((data as { content?: unknown }).content)) {
    return null
  }
  return <Render config={puckConfig} data={data} />
}

export default CmsPageRender
