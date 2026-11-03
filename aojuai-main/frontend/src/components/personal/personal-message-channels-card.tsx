'use client';
import { translateActive } from '@/lib/i18n/registry'
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { PageHeader } from '@/components/page/page-header';
import { QrCodePreview } from '@/components/share/qr-code-preview';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { ApiError, apiFetch } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { useSiteBranding } from '@/hooks/useSiteBranding';
type MessageChannel = {
    id: number;
    channelType: 'wechat' | 'wecom' | 'feishu' | 'webhook' | string;
    name: string;
    target?: string | null;
    status: 'pending' | 'active' | 'disabled' | string;
    isDefault?: boolean;
    externalUserId?: string | null;
    conversationId?: string | null;
    displayName?: string | null;
    avatar?: string | null;
    messageTypes?: string[];
    boundAt?: string | null;
    lastInboundAt?: string | null;
    lastSentAt?: string | null;
    lastError?: string | null;
    extra?: Record<string, unknown>;
    createdAt?: string | null;
    updatedAt?: string | null;
    secretConfigured?: boolean;
};
type MessageChannelBindResult = {
    channelId: number;
    bindToken: string;
    bindingCode: string;
    qrText: string;
    scode?: string | null;
    qrUrl?: string | null;
    qrImageUrl?: string | null;
    qrPayload?: string | null;
    verificationUriComplete?: string | null;
    expiresAt?: string | null;
    instructions?: string[];
    gatewayReady?: boolean;
    status: string;
    channelType: 'wechat' | 'feishu' | 'wecom';
};
type WecomQrStatus = {
    scode: string;
    status: string;
    connected: boolean;
    botId?: string | null;
    channel?: MessageChannel | null;
    expiresAt?: string | null;
};
type MessageChannelForm = {
    // 放宽成 string：扫码绑定的微信/企微/飞书渠道也要能改默认与订阅类型。
    // 原来锁死成 'webhook'，导致这些渠道只能测试和删除。
    channelType: string;
    name: string;
    target: string;
    secret: string;
    status: 'pending' | 'active' | 'disabled';
    isDefault: boolean;
    messageTypes: string[];
    /** 会话到期前提醒我回一句（只对会话会过期的渠道有意义，如微信）。 */
    renewalReminder: boolean;
    holdUntilActive: boolean;
};
function formatDateTime(value: string | null | undefined): string {
    return value ? new Date(value).toLocaleString() : '-';
}
function defaultMessageChannelForm(): MessageChannelForm {
    return {
        channelType: 'webhook',
        name: 'Webhook Channel',
        target: '',
        secret: '',
        status: 'active',
        renewalReminder: false,
        holdUntilActive: false,
        isDefault: false,
        messageTypes: ['notification'],
    };
}
function messageChannelTypeLabel(type: string): string {
    switch (type) {
        case 'feishu':
            return translateActive("components.personal.personalMessageChannelsCard.copy001");
        case 'wechat':
            return translateActive("components.personal.personalMessageChannelsCard.copy002");
        case 'wecom':
            return translateActive("components.personal.personalMessageChannelsCard.copy003");
        case 'webhook':
            return translateActive("components.personal.personalMessageChannelsCard.copy004");
        default:
            return type || '-';
    }
}
function messageChannelBindStatusLabel(status: string): string {
    switch (status) {
        case 'pending':
            return translateActive("components.personal.personalMessageChannelsCard.copy005");
        case 'active':
            return translateActive("components.personal.personalMessageChannelsCard.copy006");
        case 'disabled':
            return translateActive("components.personal.personalMessageChannelsCard.copy007");
        case 'expired':
            return translateActive("components.personal.personalMessageChannelsCard.copy008");
        default:
            return status || '-';
    }
}
function wecomQrStatusLabel(status: string | null | undefined): string {
    const normalized = String(status || '').trim();
    if (!normalized || normalized === 'pending')
        return translateActive("components.personal.personalMessageChannelsCard.copy009");
    if (normalized === 'scan')
        return translateActive("components.personal.personalMessageChannelsCard.copy010");
    if (normalized === 'success')
        return translateActive("components.personal.personalMessageChannelsCard.copy011");
    if (normalized === 'expired')
        return translateActive("components.personal.personalMessageChannelsCard.copy008");
    return normalized;
}
function messageChannelBindFallbackInstructions(result: MessageChannelBindResult): string[] {
    const provider = result.channelType === 'wechat' ? translateActive("components.personal.personalMessageChannelsCard.copy002") : result.channelType === 'wecom' ? translateActive("components.personal.personalMessageChannelsCard.copy003") : translateActive("components.personal.personalMessageChannelsCard.copy001");
    return [
        translateActive("components.personal.personalMessageChannelsCard.copy012").replace("{0}", String(provider)),
        translateActive("components.personal.personalMessageChannelsCard.copy013"),
        translateActive("components.personal.personalMessageChannelsCard.copy014"),
    ];
}
function resolveMessageChannelQrValue(result: MessageChannelBindResult | null): string {
    if (!result)
        return '';
    return String(result.qrPayload || result.qrUrl || result.verificationUriComplete || '').trim();
}
/** 订阅类型即转发路由：外部中转或定时任务用哪个 messageType 推送，
 *  只有勾了对应类型的渠道才会收到。 */
const MESSAGE_TYPE_OPTIONS = [
    { value: 'notification', labelKey: 'components.personal.personalMessageChannelsCard.typeNotification' },
    { value: 'relay', labelKey: 'components.personal.personalMessageChannelsCard.typeRelay' },
    { value: 'harness', labelKey: 'components.personal.personalMessageChannelsCard.typeHarness' },
];

/** 会话会过期、因此需要"到期提醒"的渠道类型。与后端
 *  `channel_renewal.SESSION_EXPIRING_CHANNEL_TYPES` 对应。 */
const SESSION_EXPIRING_TYPES = ['wechat'];

function buildMessageChannelPayload(form: MessageChannelForm) {
    return {
        channelType: form.channelType,
        name: form.name.trim(),
        target: form.target.trim() || null,
        secret: form.secret.trim() || null,
        status: form.status,
        isDefault: form.isDefault,
        messageTypes: form.messageTypes,
        // **只传这个布尔，不传 extra。**
        //
        // 之前是"把已有 extra 一起带上"，但页面里的 extra 来自缓存、可能已经过时：
        // 打开页面后发生一次入站，再保存开关，就会把新的 context token 一起回滚。
        // 后端收到这个字段后走 JSONB 局部合并，只动这一个键。（codex 复核发现）
        ...(SESSION_EXPIRING_TYPES.includes(form.channelType)
            ? { renewalReminder: form.renewalReminder, holdUntilActive: form.holdUntilActive }
            : {}),
    };
}
function mapChannelToForm(channel: MessageChannel): MessageChannelForm {
    return {
        channelType: channel.channelType || 'webhook',
        name: channel.name || '',
        target: channel.target || '',
        secret: '',
        // **保留 pending。** 原来把非 disabled 一律映射成 active：
        // 用户在扫码绑定途中点"编辑→保存"，pending 渠道会被激活，
        // 而入站绑定只认 pending，重新扫码又会因"已有 active 渠道"被拒——
        // 绑定流程就此卡死。（codex 复核发现）
        status: channel.status === 'disabled' ? 'disabled' : (channel.status === 'pending' ? 'pending' : 'active'),
        isDefault: Boolean(channel.isDefault),
        messageTypes: channel.messageTypes || ['notification'],
        renewalReminder: Boolean((channel.extra as Record<string, unknown> | undefined)?.renewalReminderEnabled),
        holdUntilActive: Boolean((channel.extra as Record<string, unknown> | undefined)?.holdUntilActiveEnabled),
    };
}
export function PersonalMessageChannelsCard() {
    const { session } = useAuth();
    const branding = useSiteBranding();
    const [messageChannels, setMessageChannels] = useState<MessageChannel[]>([]);
    const [messageChannelsLoading, setMessageChannelsLoading] = useState(false);
    const [messageChannelSaving, setMessageChannelSaving] = useState(false);
    const [messageChannelBinding, setMessageChannelBinding] = useState(false);
    const [wecomQrPolling, setWecomQrPolling] = useState(false);
    const [wecomQrStatus, setWecomQrStatus] = useState<WecomQrStatus | null>(null);
    const [messageChannelBindResult, setMessageChannelBindResult] = useState<MessageChannelBindResult | null>(null);
    const [testingMessageChannelId, setTestingMessageChannelId] = useState<number | null>(null);
    const [editingMessageChannelId, setEditingMessageChannelId] = useState<number | null>(null);
    const [messageChannelForm, setMessageChannelForm] = useState<MessageChannelForm>(() => defaultMessageChannelForm());
    const bindQrValue = resolveMessageChannelQrValue(messageChannelBindResult);
    useEffect(() => {
        if (!session)
            return;
        void loadMessageChannels();
    }, [session]);
    useEffect(() => {
        if (!session || !messageChannelBindResult || messageChannelBindResult.status !== 'pending')
            return;
        const channelId = messageChannelBindResult.channelId;
        const expiresAtMs = messageChannelBindResult.expiresAt ? new Date(messageChannelBindResult.expiresAt).getTime() : 0;
        let stopped = false;
        let notified = false;
        const pollBindStatus = async () => {
            if (stopped)
                return;
            if (expiresAtMs && Number.isFinite(expiresAtMs) && Date.now() > expiresAtMs) {
                setMessageChannelBindResult((prev) => prev && prev.channelId === channelId && prev.status === 'pending' ? { ...prev, status: 'expired' } : prev);
                await loadMessageChannels({ silent: true });
                return;
            }
            const channels = await loadMessageChannels({ silent: true });
            if (stopped || !channels)
                return;
            const channel = channels.find((item) => item.id === channelId);
            if (!channel) {
                setMessageChannelBindResult((prev) => prev && prev.channelId === channelId ? { ...prev, status: 'expired' } : prev);
                return;
            }
            const qrExtra = channel.extra?.qr && typeof channel.extra.qr === 'object' ? (channel.extra.qr as Record<string, unknown>) : {};
            const gatewayReady = typeof qrExtra.gatewayReady === 'boolean' ? qrExtra.gatewayReady : undefined;
            const nextExpiresAt = typeof channel.extra?.expiresAt === 'string'
                ? channel.extra.expiresAt
                : typeof qrExtra.expiresAt === 'string'
                    ? qrExtra.expiresAt
                    : undefined;
            setMessageChannelBindResult((prev) => {
                if (!prev || prev.channelId !== channelId)
                    return prev;
                return {
                    ...prev,
                    status: channel.status || prev.status,
                    gatewayReady: Boolean(prev.gatewayReady || gatewayReady),
                    expiresAt: nextExpiresAt || prev.expiresAt,
                };
            });
            if (channel.status === 'active' && !notified) {
                notified = true;
                toast.success(translateActive("components.personal.personalMessageChannelsCard.copy015").replace("{0}", String(messageChannelTypeLabel(channel.channelType))));
                setMessageChannelBindResult(null);
            }
            else if (channel.status === 'disabled' && !notified) {
                notified = true;
                toast.error(channel.lastError || translateActive("components.personal.personalMessageChannelsCard.copy016"));
            }
        };
        void pollBindStatus();
        const timer = window.setInterval(() => {
            void pollBindStatus();
        }, 3000);
        return () => {
            stopped = true;
            window.clearInterval(timer);
        };
    }, [session, messageChannelBindResult?.channelId, messageChannelBindResult?.status, messageChannelBindResult?.expiresAt]);
    useEffect(() => {
        if (!session || !messageChannelBindResult || messageChannelBindResult.channelType !== 'wecom')
            return;
        const activeScode = String(messageChannelBindResult.scode || '').trim();
        if (!activeScode || messageChannelBindResult.status !== 'pending')
            return;
        let stopped = false;
        const poll = async () => {
            if (stopped)
                return;
            await pollWecomQrStatus(activeScode, { silent: true });
        };
        void poll();
        const timer = window.setInterval(() => {
            void poll();
        }, 3000);
        return () => {
            stopped = true;
            window.clearInterval(timer);
        };
    }, [session, messageChannelBindResult?.channelType, messageChannelBindResult?.scode, messageChannelBindResult?.status]);
    async function loadMessageChannels(options?: {
        silent?: boolean;
    }): Promise<MessageChannel[] | null> {
        if (!session)
            return null;
        if (!options?.silent)
            setMessageChannelsLoading(true);
        try {
            const channels = await apiFetch<MessageChannel[]>('/api/v1/message-channels', { session });
            const nextChannels = channels || [];
            setMessageChannels(nextChannels);
            return nextChannels;
        }
        catch (err) {
            if (!options?.silent)
                toast.error(err instanceof ApiError ? err.message : translateActive("components.personal.personalMessageChannelsCard.copy017"));
            return null;
        }
        finally {
            if (!options?.silent)
                setMessageChannelsLoading(false);
        }
    }
    async function saveMessageChannel() {
        if (!session)
            return;
        if (!messageChannelForm.name.trim()) {
            toast.error(translateActive("components.personal.personalMessageChannelsCard.copy018"));
            return;
        }
        // 后端是 `message_types or channel.message_types`：全空会被静默保留旧值，
        // 于是界面显示"一个都没勾"、实际仍在收消息。前端直接拦住。
        if (!messageChannelForm.messageTypes.length) {
            toast.error(translateActive("components.personal.personalMessageChannelsCard.messageTypesRequired"));
            return;
        }
        if (messageChannelForm.channelType === 'webhook' && !messageChannelForm.target.trim()) {
            toast.error(translateActive("components.personal.personalMessageChannelsCard.copy019"));
            return;
        }
        setMessageChannelSaving(true);
        const id = toast.loading(editingMessageChannelId ? translateActive("components.personal.personalMessageChannelsCard.copy020") : translateActive("components.personal.personalMessageChannelsCard.copy021"));
        try {
            const payload = buildMessageChannelPayload(messageChannelForm);
            await apiFetch<MessageChannel>(editingMessageChannelId ? `/api/v1/message-channels/${editingMessageChannelId}` : '/api/v1/message-channels/manual', {
                method: editingMessageChannelId ? 'PUT' : 'POST',
                session,
                body: JSON.stringify(payload),
            });
            setEditingMessageChannelId(null);
            setMessageChannelForm(defaultMessageChannelForm());
            await loadMessageChannels();
            toast.success(translateActive("components.personal.personalMessageChannelsCard.copy022"), { id });
        }
        catch (err) {
            toast.error(err instanceof ApiError ? err.message : translateActive("components.personal.personalMessageChannelsCard.copy023"), { id });
        }
        finally {
            setMessageChannelSaving(false);
        }
    }
    async function startWecomMessageChannelBind() {
        if (!session)
            return;
        setMessageChannelBinding(true);
        setWecomQrStatus(null);
        const id = toast.loading(translateActive("components.personal.personalMessageChannelsCard.copy024"));
        try {
            const res = await apiFetch<Omit<MessageChannelBindResult, 'channelType'>>('/api/v1/message-channels/wecom/qrcode/start', {
                method: 'POST',
                session,
            });
            setMessageChannelBindResult({ ...res, channelType: 'wecom' });
            if (res.scode) {
                setWecomQrStatus({ scode: res.scode, status: 'pending', connected: false, channel: null });
            }
            await loadMessageChannels();
            toast.success(translateActive("components.personal.personalMessageChannelsCard.copy025"), { id });
        }
        catch (err) {
            toast.error(err instanceof ApiError ? err.message : translateActive("components.personal.personalMessageChannelsCard.copy026"), { id });
        }
        finally {
            setMessageChannelBinding(false);
        }
    }
    async function pollWecomQrStatus(scode: string, options?: {
        silent?: boolean;
    }) {
        if (!session)
            return null;
        if (!options?.silent)
            setWecomQrPolling(true);
        try {
            const res = await apiFetch<WecomQrStatus>(`/api/v1/message-channels/wecom/qrcode/status?scode=${encodeURIComponent(scode)}`, { session });
            setWecomQrStatus(res);
            setMessageChannelBindResult((prev) => {
                if (!prev || prev.channelType !== 'wecom' || prev.scode !== scode)
                    return prev;
                const channelExpiresAt = typeof res.channel?.extra?.expiresAt === 'string' ? res.channel.extra.expiresAt : undefined;
                return {
                    ...prev,
                    gatewayReady: Boolean(prev.gatewayReady || res.connected),
                    status: res.channel?.status || prev.status,
                    expiresAt: res.expiresAt || channelExpiresAt || prev.expiresAt,
                };
            });
            if (res.connected) {
                await loadMessageChannels({ silent: true });
            }
            return res;
        }
        catch (err) {
            if (!options?.silent) {
                toast.error(err instanceof ApiError ? err.message : translateActive("components.personal.personalMessageChannelsCard.copy027"));
            }
            return null;
        }
        finally {
            if (!options?.silent)
                setWecomQrPolling(false);
        }
    }
    async function startMessageChannelBind(channelType: 'wechat' | 'feishu' | 'wecom') {
        if (!session)
            return;
        if (channelType === 'wecom') {
            await startWecomMessageChannelBind();
            return;
        }
        setMessageChannelBinding(true);
        setWecomQrStatus(null);
        const id = toast.loading(translateActive("components.personal.personalMessageChannelsCard.copy028"));
        try {
            const res = await apiFetch<Omit<MessageChannelBindResult, 'channelType'>>('/api/v1/message-channels/bind/start', {
                method: 'POST',
                session,
                body: JSON.stringify({
                    channelType,
                    name: channelType === 'wechat' ? translateActive("components.personal.personalMessageChannelsCard.copy029") : translateActive("components.personal.personalMessageChannelsCard.copy030"),
                    messageTypes: ['notification'],
                }),
            });
            setMessageChannelBindResult({ ...res, channelType });
            await loadMessageChannels();
            toast.success(translateActive("components.personal.personalMessageChannelsCard.copy031"), { id });
        }
        catch (err) {
            toast.error(err instanceof ApiError ? err.message : translateActive("components.personal.personalMessageChannelsCard.copy032"), { id });
        }
        finally {
            setMessageChannelBinding(false);
        }
    }
    async function testMessageChannel(channel: MessageChannel) {
        if (!session)
            return;
        setTestingMessageChannelId(channel.id);
        const id = toast.loading(translateActive("components.personal.personalMessageChannelsCard.copy033"));
        try {
            await apiFetch(`/api/v1/message-channels/${channel.id}/test`, {
                method: 'POST',
                session,
                body: JSON.stringify({
                    title: translateActive("components.personal.personalMessageChannelsCard.copy034").replace("{0}", String(branding.title)),
                    content: translateActive("components.personal.personalMessageChannelsCard.copy035").replace("{0}", String(channel.name)),
                }),
            });
            await loadMessageChannels();
            toast.success(translateActive("components.personal.personalMessageChannelsCard.copy036"), { id });
        }
        catch (err) {
            await loadMessageChannels();
            toast.error(err instanceof ApiError ? err.message : translateActive("components.personal.personalMessageChannelsCard.copy037"), { id });
        }
        finally {
            setTestingMessageChannelId(null);
        }
    }
    async function deleteMessageChannel(channel: MessageChannel) {
        if (!session)
            return;
        const ok = window.confirm(translateActive("components.personal.personalMessageChannelsCard.copy038").replace("{0}", String(channel.name)));
        if (!ok)
            return;
        const id = toast.loading(translateActive("components.personal.personalMessageChannelsCard.copy039"));
        try {
            await apiFetch(`/api/v1/message-channels/${channel.id}`, { method: 'DELETE', session });
            if (editingMessageChannelId === channel.id) {
                setEditingMessageChannelId(null);
                setMessageChannelForm(defaultMessageChannelForm());
            }
            await loadMessageChannels();
            toast.success(translateActive("components.personal.personalMessageChannelsCard.copy040"), { id });
        }
        catch (err) {
            toast.error(err instanceof ApiError ? err.message : translateActive("components.personal.personalMessageChannelsCard.copy041"), { id });
        }
    }
    if (!session)
        return null;
    return (<div className="grid gap-4">
      <Card>
        <CardHeader>
          <PageHeader title={translateActive("components.personal.personalMessageChannelsCard.copy042")} description={translateActive("components.personal.personalMessageChannelsCard.copy043")}/>
        </CardHeader>
        <CardContent className="grid gap-3 lg:grid-cols-3">
          <div className="flex h-full flex-col rounded-xl border p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-medium">{translateActive("components.personal.personalMessageChannelsCard.copy029")}</div>
                <div className="mt-1 text-xs text-muted-foreground">{translateActive("components.personal.personalMessageChannelsCard.copy044")}</div>
              </div>
              <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">{translateActive("components.personal.personalMessageChannelsCard.copy045")}</span>
            </div>
            <Button type="button" variant="outline" className="mt-4 w-full self-start sm:mt-auto sm:w-auto" disabled={messageChannelBinding} onClick={() => {
            void startMessageChannelBind('wechat');
        }}>{translateActive("components.personal.personalMessageChannelsCard.copy046")}</Button>
          </div>

          <div className="flex h-full flex-col rounded-xl border p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-medium">{translateActive("components.personal.personalMessageChannelsCard.copy047")}</div>
                <div className="mt-1 text-xs text-muted-foreground">{translateActive("components.personal.personalMessageChannelsCard.copy048")}</div>
              </div>
              <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">{translateActive("components.personal.personalMessageChannelsCard.copy045")}</span>
            </div>
            <Button type="button" variant="outline" className="mt-4 w-full self-start sm:mt-auto sm:w-auto" disabled={messageChannelBinding} onClick={() => {
            void startWecomMessageChannelBind();
        }}>{translateActive("components.personal.personalMessageChannelsCard.copy049")}</Button>
          </div>

          <div className="flex h-full flex-col rounded-xl border p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-medium">{translateActive("components.personal.personalMessageChannelsCard.copy030")}</div>
                <div className="mt-1 text-xs text-muted-foreground">{translateActive("components.personal.personalMessageChannelsCard.copy050")}</div>
              </div>
              <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">{translateActive("components.personal.personalMessageChannelsCard.copy045")}</span>
            </div>
            <Button type="button" variant="outline" className="mt-4 w-full self-start sm:mt-auto sm:w-auto" disabled={messageChannelBinding} onClick={() => {
            void startMessageChannelBind('feishu');
        }}>{translateActive("components.personal.personalMessageChannelsCard.copy051")}</Button>
          </div>

          {messageChannelBindResult ? (<div className="grid gap-4 rounded-xl border bg-muted/30 p-4 md:grid-cols-[240px_minmax(0,1fr)] lg:col-span-3">
              <div className="grid gap-2">
                <div className="text-sm font-medium">{messageChannelTypeLabel(messageChannelBindResult.channelType)}{translateActive("components.personal.personalMessageChannelsCard.copy052")}</div>
                <div className="flex min-h-[236px] items-center justify-center rounded-xl border bg-background p-3">
                  {messageChannelBindResult.qrImageUrl ? (<img src={messageChannelBindResult.qrImageUrl} alt={translateActive("components.personal.personalMessageChannelsCard.copy053").replace("{0}", String(messageChannelTypeLabel(messageChannelBindResult.channelType)))} className="h-[220px] w-[220px] rounded-md object-contain"/>) : bindQrValue ? (<QrCodePreview value={bindQrValue} size={220} className="rounded-md border-0 p-0 shadow-none"/>) : (<div className="text-center text-xs text-muted-foreground">{translateActive("components.personal.personalMessageChannelsCard.copy054")}</div>)}
                </div>
                {bindQrValue ? (<a href={bindQrValue} target="_blank" rel="noreferrer" className="break-all text-xs text-primary underline-offset-4 hover:underline">{translateActive("components.personal.personalMessageChannelsCard.copy055")}</a>) : null}
              </div>
              <div className="grid content-start gap-3">
                <div>
                  <div className="text-sm font-medium">{translateActive("components.personal.personalMessageChannelsCard.copy056")}</div>
                  <div className="mt-2 inline-flex rounded-xl border bg-background px-5 py-3 font-mono text-3xl font-semibold tracking-[0.35em]">
                    {messageChannelBindResult.bindingCode || messageChannelBindResult.qrText || messageChannelBindResult.bindToken}
                  </div>
                </div>
                <div className="rounded-xl border bg-background p-3 text-xs text-muted-foreground">
                  {(messageChannelBindResult.instructions?.length
                ? messageChannelBindResult.instructions
                : messageChannelBindFallbackInstructions(messageChannelBindResult)).map((item, index) => (<div key={`${index}-${item}`} className="flex gap-2 py-1">
                      <span className="font-mono text-xs">{index + 1}.</span>
                      <span>{item}</span>
                    </div>))}
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  <span className="rounded-full border bg-background px-2 py-0.5">{translateActive("components.personal.personalMessageChannelsCard.copy057")}{messageChannelBindStatusLabel(messageChannelBindResult.status)}
                  </span>
                  <span className="rounded-full border bg-background px-2 py-0.5">
                    {messageChannelBindResult.channelType === 'wecom'
                ? translateActive("components.personal.personalMessageChannelsCard.copy058").replace("{0}", String(wecomQrStatus ? wecomQrStatusLabel(wecomQrStatus.status) : translateActive("components.personal.personalMessageChannelsCard.copy009"))) : translateActive("components.personal.personalMessageChannelsCard.copy059").replace("{0}", String(messageChannelBindResult.gatewayReady ? translateActive("components.common.ready") : translateActive("components.personal.personalMessageChannelsCard.waitingScanOrAuthorize")))}
                  </span>
                  {messageChannelBindResult.expiresAt ? (<span className="rounded-full border bg-background px-2 py-0.5">{translateActive("components.personal.personalMessageChannelsCard.copy060")}{formatDateTime(messageChannelBindResult.expiresAt)}
                    </span>) : null}
                </div>
                <div className="text-xs text-muted-foreground">{translateActive("components.personal.personalMessageChannelsCard.copy061")}</div>
                {messageChannelBindResult.channelType === 'wecom' && messageChannelBindResult.scode ? (<div className="flex flex-wrap gap-2">
                    <Button type="button" variant="outline" size="sm" disabled={wecomQrPolling} onClick={() => {
                    void pollWecomQrStatus(String(messageChannelBindResult.scode || ''));
                }}>
                      {wecomQrPolling ? translateActive("components.personal.personalMessageChannelsCard.copy062") : translateActive("components.personal.personalMessageChannelsCard.copy063")}
                    </Button>
                  </div>) : null}
              </div>
            </div>) : null}
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <Card>
          <CardHeader>
            <PageHeader title={translateActive("components.personal.personalMessageChannelsCard.copy064")} description={translateActive("components.personal.personalMessageChannelsCard.copy065")}/>
          </CardHeader>
          <CardContent className="grid gap-3">
            {messageChannelsLoading ? <div className="text-xs text-muted-foreground">{translateActive("components.personal.personalMessageChannelsCard.copy066")}</div> : null}
            {(messageChannels || []).map((channel) => (<div key={channel.id} className="rounded-xl border p-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="grid min-w-0 gap-1 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{channel.name}</span>
                      <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                        {messageChannelTypeLabel(channel.channelType)}
                      </span>
                      {channel.isDefault ? <span className="rounded-full border px-2 py-0.5 text-xs">{translateActive("components.personal.personalMessageChannelsCard.copy067")}</span> : null}
                      <span className="rounded-full border px-2 py-0.5 text-xs">
                        {channel.status === 'pending' ? translateActive("components.personal.personalMessageChannelsCard.copy005") : channel.status === 'active' ? translateActive("components.personal.personalMessageChannelsCard.copy068") : translateActive("components.personal.personalMessageChannelsCard.copy007")}
                      </span>
                    </div>
                    <div className="break-all text-xs text-muted-foreground">{translateActive("components.personal.personalMessageChannelsCard.copy069")}{channel.displayName || channel.externalUserId || channel.target || '-'}
                    </div>
                    <div className="text-xs text-muted-foreground">{translateActive("components.personal.personalMessageChannelsCard.copy070")}{formatDateTime(channel.boundAt)}{translateActive("components.personal.personalMessageChannelsCard.copy071")}{formatDateTime(channel.lastInboundAt)}{translateActive("components.personal.personalMessageChannelsCard.copy072")}{formatDateTime(channel.lastSentAt)}
                      {channel.secretConfigured ? translateActive("components.personal.personalMessageChannelsCard.copy073") : ''}
                    </div>
                    {channel.lastError ? <div className="break-all text-xs text-destructive">{translateActive("components.personal.personalMessageChannelsCard.copy074")}{channel.lastError}</div> : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" disabled={testingMessageChannelId === channel.id || channel.status !== 'active'} onClick={() => {
                void testMessageChannel(channel);
            }}>
                      {testingMessageChannelId === channel.id ? translateActive("components.personal.personalMessageChannelsCard.copy075") : translateActive("components.personal.personalMessageChannelsCard.copy076")}
                    </Button>
                    {/* 编辑对所有**已绑定**的渠道类型开放：扫码绑定的微信/企微/飞书
                        也要能设默认、改订阅类型。原来只对 webhook 出现。
                        pending（还在扫码中）不给编辑：那时改什么都没意义，
                        误存还会把它推成 active 卡死绑定流程。 */}
                    {channel.status !== 'pending' ? (<Button size="sm" variant="outline" onClick={() => {
                    setEditingMessageChannelId(channel.id);
                    setMessageChannelForm(mapChannelToForm(channel));
                }}>{translateActive("components.personal.personalMessageChannelsCard.copy077")}</Button>) : null}
                    <Button size="sm" variant="outline" onClick={() => {
                void deleteMessageChannel(channel);
            }}>{translateActive("components.personal.personalMessageChannelsCard.copy078")}</Button>
                  </div>
                </div>
              </div>))}
            {!messageChannelsLoading && messageChannels.length === 0 ? (<div className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">{translateActive("components.personal.personalMessageChannelsCard.copy079")}</div>) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <PageHeader title={editingMessageChannelId ? translateActive("components.personal.personalMessageChannelsCard.copy080") : translateActive("components.personal.personalMessageChannelsCard.copy081")} description={translateActive("components.personal.personalMessageChannelsCard.copy082")}/>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">{translateActive("components.personal.personalMessageChannelsCard.copy083")}</div>

            <div className="grid gap-2">
              <Label>{translateActive("components.personal.personalMessageChannelsCard.copy084")}</Label>
              <Select value={messageChannelForm.channelType} disabled>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="webhook">{translateActive("components.personal.personalMessageChannelsCard.copy004")}</SelectItem>
                  <SelectItem value="wechat">{translateActive("components.personal.personalMessageChannelsCard.copy002")}</SelectItem>
                  <SelectItem value="wecom">{translateActive("components.personal.personalMessageChannelsCard.copy003")}</SelectItem>
                  <SelectItem value="feishu">{translateActive("components.personal.personalMessageChannelsCard.copy001")}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label>{translateActive("components.personal.personalMessageChannelsCard.copy085")}</Label>
              <Input value={messageChannelForm.name} disabled={messageChannelSaving} onChange={(event) => setMessageChannelForm((prev) => ({ ...prev, name: event.target.value }))} placeholder={translateActive("components.personal.personalMessageChannelsCard.copy086")}/>
            </div>

            {/* 地址与密钥只对 Webhook 有意义：扫码绑定的渠道由网关寻址，
                把这两个框摆出来只会让人以为该填。 */}
            {messageChannelForm.channelType === 'webhook' ? (<>
            <div className="grid gap-2">
              <Label>{translateActive("components.personal.personalMessageChannelsCard.copy087")}</Label>
              <Textarea value={messageChannelForm.target} disabled={messageChannelSaving} onChange={(event) => setMessageChannelForm((prev) => ({ ...prev, target: event.target.value }))} placeholder="https://example.com/webhook"/>
            </div>

            <div className="grid gap-2">
              <Label>{translateActive("components.personal.personalMessageChannelsCard.copy088")}</Label>
              <Input type="password" value={messageChannelForm.secret} disabled={messageChannelSaving} onChange={(event) => setMessageChannelForm((prev) => ({ ...prev, secret: event.target.value }))} placeholder={editingMessageChannelId ? translateActive("components.personal.personalMessageChannelsCard.copy089") : translateActive("components.personal.personalMessageChannelsCard.copy090")}/>
            </div>
            </>) : null}

            {/* 订阅类型 = 转发路由。中转/定时任务发什么类型，这里勾了才收得到。 */}
            <div className="grid gap-2">
              <Label>{translateActive("components.personal.personalMessageChannelsCard.messageTypesLabel")}</Label>
              <div className="flex flex-wrap gap-3 rounded-xl border p-3 text-sm">
                {MESSAGE_TYPE_OPTIONS.map((option) => (
                  <label key={option.value} className="flex items-center gap-2">
                    <Switch
                      checked={messageChannelForm.messageTypes.includes(option.value)}
                      onCheckedChange={(checked) => setMessageChannelForm((prev) => ({
                        ...prev,
                        messageTypes: checked
                          ? Array.from(new Set([...prev.messageTypes, option.value]))
                          : prev.messageTypes.filter((item) => item !== option.value),
                      }))}
                    />
                    {translateActive(option.labelKey)}
                  </label>
                ))}
              </div>
              <p className="text-muted-foreground text-xs">{translateActive("components.personal.personalMessageChannelsCard.messageTypesHint")}</p>
            </div>

            <div className="flex flex-wrap items-center gap-4 rounded-xl border p-3 text-sm">
              <label className="flex items-center gap-2">
                <Switch checked={messageChannelForm.status === 'active'} onCheckedChange={(checked) => setMessageChannelForm((prev) => ({ ...prev, status: checked ? 'active' : 'disabled' }))}/>{translateActive("components.personal.personalMessageChannelsCard.copy091")}</label>
              <label className="flex items-center gap-2">
                <Switch checked={messageChannelForm.isDefault} onCheckedChange={(checked) => setMessageChannelForm((prev) => ({ ...prev, isDefault: Boolean(checked) }))}/>{translateActive("components.personal.personalMessageChannelsCard.copy092")}</label>
              {/* 只对会话会过期的渠道显示。默认关闭：往用户微信推一条未经请求的
                  消息、还占用他自己的会话窗口，得他点头才做。 */}
              {SESSION_EXPIRING_TYPES.includes(messageChannelForm.channelType) ? (
              <label className="flex items-center gap-2">
                <Switch checked={messageChannelForm.renewalReminder} onCheckedChange={(checked) => setMessageChannelForm((prev) => ({ ...prev, renewalReminder: Boolean(checked) }))}/>{translateActive("components.personal.personalMessageChannelsCard.renewalReminder")}</label>) : null}
            </div>
            {SESSION_EXPIRING_TYPES.includes(messageChannelForm.channelType) ? (
              <p className="text-muted-foreground text-xs">{translateActive("components.personal.personalMessageChannelsCard.renewalReminderHint")}</p>) : null}
            {SESSION_EXPIRING_TYPES.includes(messageChannelForm.channelType) ? (
              <div className="grid gap-1">
                <label className="flex items-center gap-2">
                  <Switch checked={messageChannelForm.holdUntilActive} onCheckedChange={(checked) => setMessageChannelForm((prev) => ({ ...prev, holdUntilActive: Boolean(checked) }))}/>{translateActive("components.personal.personalMessageChannelsCard.holdUntilActive")}
                </label>
                <p className="text-muted-foreground text-xs">{translateActive("components.personal.personalMessageChannelsCard.holdUntilActiveHint")}</p>
              </div>) : null}

            <div className="flex flex-col gap-2 sm:flex-row">
              <Button className="w-full sm:w-auto" disabled={messageChannelSaving} onClick={() => {
            void saveMessageChannel();
        }}>
                {messageChannelSaving ? translateActive("components.personal.personalMessageChannelsCard.copy093") : editingMessageChannelId ? translateActive("components.personal.personalMessageChannelsCard.copy094") : translateActive("components.personal.personalMessageChannelsCard.copy095")}
              </Button>
              {editingMessageChannelId ? (<Button type="button" variant="outline" className="w-full sm:w-auto" disabled={messageChannelSaving} onClick={() => {
                setEditingMessageChannelId(null);
                setMessageChannelForm(defaultMessageChannelForm());
            }}>{translateActive("components.personal.personalMessageChannelsCard.copy096")}</Button>) : null}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>);
}
