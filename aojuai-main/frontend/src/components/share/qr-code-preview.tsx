'use client';
import { translateActive } from '@/lib/i18n/registry'
import { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import { cn } from '@/lib/utils';
type QrCodePreviewProps = {
    value: string;
    size?: number;
    className?: string;
};
export function QrCodePreview({ value, size = 224, className }: QrCodePreviewProps) {
    const [src, setSrc] = useState('');
    const normalizedValue = String(value || '').trim();
    useEffect(() => {
        let active = true;
        if (!normalizedValue)
            return () => {
                active = false;
            };
        void QRCode.toDataURL(normalizedValue, {
            width: size,
            margin: 1,
            errorCorrectionLevel: 'M',
            color: {
                dark: '#111827',
                light: '#ffffffff',
            },
        })
            .then((dataUrl) => {
            if (active)
                setSrc(dataUrl);
        })
            .catch(() => {
            if (active)
                setSrc('');
        });
        return () => {
            active = false;
        };
    }, [normalizedValue, size]);
    return (<div className={cn('flex items-center justify-center overflow-hidden rounded-2xl border bg-white p-3 shadow-sm', className)}>
      {normalizedValue && src ? (<img src={src} alt={translateActive("components.share.qrCodePreview.copy001")} width={size} height={size} className="h-auto max-w-full"/>) : (<div className="flex h-full min-h-[180px] w-full items-center justify-center text-sm text-muted-foreground">{translateActive("components.share.qrCodePreview.copy002")}</div>)}
    </div>);
}
