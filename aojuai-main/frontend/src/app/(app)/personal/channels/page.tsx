'use client';
import { translateActive } from '@/lib/i18n/registry'
import { PersonalMessageChannelsCard } from '@/components/personal/personal-message-channels-card';
export default function PersonalChannelsPage() {
    return (<div className="grid gap-5">
      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="max-w-3xl">
          <div className="text-2xl font-semibold tracking-tight text-foreground">{translateActive("app.personal.channels.page.copy001")}</div>
          <div className="mt-2 text-sm leading-6 text-muted-foreground">{translateActive("app.personal.channels.page.copy002")}</div>
        </div>
      </section>

      <PersonalMessageChannelsCard />
    </div>);
}
