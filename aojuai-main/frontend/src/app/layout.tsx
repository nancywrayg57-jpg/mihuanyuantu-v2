import type { ReactNode } from 'react'
import type { Metadata } from 'next'

import '@fontsource-variable/plus-jakarta-sans'
import '@fontsource-variable/sora'
import './globals.css'
import { Providers } from './providers'
import { PUBLIC_SITE_ENABLED } from '@/lib/public-site'
import { buildSiteMetadata, fetchSitePublicConfig, getRequestSiteMetadataContext } from '@/lib/server/site-metadata'

// 部署后旧 chunk 404 的自愈（回流自 nextjs-plugins）：加载 /_next/static 脚本失败时
// 带时间窗防抖强制刷新到最新构建，避免用户停留在残缺页面。
const CHUNK_RECOVERY_SCRIPT = `
(() => {
  const RETRY_KEY = '__aoju_chunk_reload_at__';
  const RETRY_WINDOW_MS = 30000;

  function shouldReload() {
    try {
      const now = Date.now();
      const last = Number.parseInt(sessionStorage.getItem(RETRY_KEY) || '', 10);
      if (Number.isFinite(last) && now - last < RETRY_WINDOW_MS) {
        return false;
      }
      sessionStorage.setItem(RETRY_KEY, String(now));
      return true;
    } catch (_error) {
      return true;
    }
  }

  function reloadToLatest() {
    if (!shouldReload()) {
      return;
    }
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('_chunk_refresh', String(Date.now()));
      window.location.replace(url.toString());
      return;
    } catch (_error) {}
    window.location.reload();
  }

  window.addEventListener('error', (event) => {
    const target = event.target;
    if (
      target instanceof HTMLScriptElement &&
      typeof target.src === 'string' &&
      target.src.includes('/_next/static/')
    ) {
      reloadToLatest();
    }
  }, true);

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason;
    const message =
      typeof reason === 'string'
        ? reason
        : (reason && typeof reason.message === 'string' ? reason.message : '');
    if (/ChunkLoadError|Loading chunk .* failed|Failed to fetch dynamically imported module/i.test(message)) {
      reloadToLatest();
    }
  });
})();
`;

export async function generateMetadata(): Promise<Metadata> {
  const context = PUBLIC_SITE_ENABLED ? await getRequestSiteMetadataContext() : null
  const site = context ? await fetchSitePublicConfig({ host: context.host }) : null

  return {
    ...buildSiteMetadata({
      site,
      origin: site?.canonicalOrigin,
      fallbackTitle: 'AOJUAI',
      fallbackDescription: 'AOJUAI enterprise intelligence workspace',
    }),
    icons: {
      icon: '/favicon.ico',
      shortcut: '/favicon.ico',
      apple: '/favicon.ico',
    },
  }
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  const { headers } = await import('next/headers')
  const lang = (await headers()).get('x-cms-locale') || 'zh'
  return (
    <html lang={lang} suppressHydrationWarning>
      <head>
        <script id="aoju-chunk-recovery" dangerouslySetInnerHTML={{ __html: CHUNK_RECOVERY_SCRIPT }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
