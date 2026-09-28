import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';

import { api } from '../lib/api';
import { useI18n } from '../lib/i18n';
import {
  currentPushSubscription,
  pushSupport,
  subscribeToPush,
  subscriptionPayload,
  unsubscribeFromPush,
} from '../lib/pwa';
import type { PushSupport } from '../lib/pwa';
import { useToast } from '../lib/toast';
import type { NotificationChannelResult, NotificationSettings } from '../lib/types';

type DeviceState = 'loading' | 'on' | 'off' | 'blocked' | Exclude<PushSupport, 'ok'>;

export default function Notifications() {
  const { t } = useI18n();
  const toast = useToast();
  const [settings, setSettings] = useState<NotificationSettings | null>(null);
  const [device, setDevice] = useState<DeviceState>('loading');
  const [busy, setBusy] = useState(false);
  const [ntfyUrl, setNtfyUrl] = useState('');
  const [ntfyToken, setNtfyToken] = useState('');
  const [webhookUrl, setWebhookUrl] = useState('');
  const [webhookSecret, setWebhookSecret] = useState('');
  const [results, setResults] = useState<NotificationChannelResult[] | null>(null);

  const apply = useCallback((data: NotificationSettings) => {
    setSettings(data);
    setNtfyUrl(data.ntfy_url);
    setWebhookUrl(data.webhook_url);
    setNtfyToken('');
    setWebhookSecret('');
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await api.getNotificationSettings();
        if (cancelled) return;
        apply(data);
        const support = pushSupport();
        if (support !== 'ok') {
          setDevice(support);
          return;
        }
        if (Notification.permission === 'denied') {
          setDevice('blocked');
          return;
        }
        const subscription = await currentPushSubscription();
        if (subscription) {
          // Re-register quietly so the server knows this device belongs to
          // whoever is signed in now, even if it forgot an old subscription.
          await api.addPushSubscription(subscriptionPayload(subscription));
          if (!cancelled) apply(await api.getNotificationSettings());
        }
        if (!cancelled) setDevice(subscription ? 'on' : 'off');
      } catch {
        if (!cancelled) toast.error(t('common.loadError'));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apply, t, toast]);

  const run = async (work: () => Promise<void>) => {
    setBusy(true);
    try {
      await work();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('settings.saveFailed'));
    } finally {
      setBusy(false);
    }
  };

  const enableDevice = () =>
    run(async () => {
      const subscription = await subscribeToPush(await api.getWebPushKey());
      if (!subscription) {
        setDevice(Notification.permission === 'denied' ? 'blocked' : 'off');
        toast.error(t('notifications.permissionDenied'));
        return;
      }
      await api.addPushSubscription(subscriptionPayload(subscription));
      apply(await api.getNotificationSettings());
      setDevice('on');
      toast.success(t('notifications.deviceEnabled'));
    });

  const disableDevice = () =>
    run(async () => {
      const endpoint = await unsubscribeFromPush();
      if (endpoint) await api.removePushSubscription(endpoint);
      apply(await api.getNotificationSettings());
      setDevice('off');
    });

  const toggle = (key: 'notify_on_ready' | 'notify_on_error', value: boolean) =>
    run(async () => apply(await api.updateNotificationSettings({ [key]: value })));

  const saveChannels = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      apply(
        await api.updateNotificationSettings({
          ntfy_url: ntfyUrl,
          ntfy_token: ntfyToken,
          webhook_url: webhookUrl,
          webhook_secret: webhookSecret,
        }),
      );
      toast.success(t('settings.saved'));
    });
  };

  const sendTest = () =>
    run(async () => {
      setResults(await api.sendTestNotification());
    });

  if (!settings) {
    return <p className="text-ink-500">{t('auth.loading')}</p>;
  }

  const disabled = !settings.enabled || busy;

  return (
    <div className="max-w-2xl">
      <h2 className="font-display text-2xl text-ink-900">{t('notifications.title')}</h2>
      <p className="mt-1 text-sm text-ink-500">{t('notifications.subtitle')}</p>

      {!settings.enabled && (
        <p role="status" className="card mt-4 text-sm text-ink-700">
          {t('notifications.serverOff')}
        </p>
      )}

      <section className="card mt-4 space-y-3">
        <h3 className="font-display text-lg text-ink-900">{t('notifications.when')}</h3>
        <label className="flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={settings.notify_on_ready}
            disabled={disabled}
            onChange={(event) => void toggle('notify_on_ready', event.target.checked)}
          />
          {t('notifications.onReady')}
        </label>
        <label className="flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={settings.notify_on_error}
            disabled={disabled}
            onChange={(event) => void toggle('notify_on_error', event.target.checked)}
          />
          {t('notifications.onError')}
        </label>
      </section>

      <section className="card mt-4 space-y-3">
        <h3 className="font-display text-lg text-ink-900">{t('notifications.device')}</h3>
        <p className="text-sm text-ink-500">{t('notifications.deviceHint')}</p>
        <p className="text-sm text-ink-700" data-testid="device-status">
          {t(`notifications.device.${device}`)}
        </p>
        {device === 'off' && (
          <button type="button" className="btn-primary" disabled={disabled} onClick={enableDevice}>
            {t('notifications.enableDevice')}
          </button>
        )}
        {device === 'on' && (
          <button type="button" className="btn-ghost" disabled={busy} onClick={disableDevice}>
            {t('notifications.disableDevice')}
          </button>
        )}
        <p className="text-xs text-ink-400">
          {t('notifications.devices', { count: settings.web_push_devices })}
        </p>
      </section>

      <form onSubmit={saveChannels} className="card mt-4 space-y-4">
        <div>
          <h3 className="font-display text-lg text-ink-900">ntfy</h3>
          <p className="text-sm text-ink-500">{t('notifications.ntfyHint')}</p>
        </div>
        <label className="block text-sm text-ink-700">
          {t('notifications.ntfyUrl')}
          <input
            value={ntfyUrl}
            onChange={(event) => setNtfyUrl(event.target.value)}
            placeholder="https://ntfy.example.com/mathom"
            className="input mt-1"
          />
        </label>
        <label className="block text-sm text-ink-700">
          {t('notifications.ntfyToken')}
          <input
            type="password"
            value={ntfyToken}
            onChange={(event) => setNtfyToken(event.target.value)}
            placeholder={settings.ntfy_token_set ? '••••••••' : t('notifications.optional')}
            className="input mt-1"
          />
        </label>

        <div className="border-t border-ink-400/20 pt-4">
          <h3 className="font-display text-lg text-ink-900">{t('notifications.webhook')}</h3>
          <p className="text-sm text-ink-500">{t('notifications.webhookHint')}</p>
        </div>
        <label className="block text-sm text-ink-700">
          {t('notifications.webhookUrl')}
          <input
            value={webhookUrl}
            onChange={(event) => setWebhookUrl(event.target.value)}
            placeholder="https://homeassistant.local:8123/api/webhook/mathom"
            className="input mt-1"
          />
        </label>
        <label className="block text-sm text-ink-700">
          {t('notifications.webhookSecret')}
          <input
            type="password"
            value={webhookSecret}
            onChange={(event) => setWebhookSecret(event.target.value)}
            placeholder={settings.webhook_secret_set ? '••••••••' : t('notifications.optional')}
            className="input mt-1"
          />
        </label>
        {!settings.public_base_url_set && (
          <p className="text-xs text-ink-500">{t('notifications.baseUrlHint')}</p>
        )}
        <div className="flex flex-wrap gap-2">
          <button type="submit" className="btn-primary" disabled={disabled}>
            {t('notifications.save')}
          </button>
          <button type="button" className="btn-ghost" disabled={disabled} onClick={sendTest}>
            {t('notifications.test')}
          </button>
        </div>
        {results && (
          <ul className="space-y-1 text-sm" aria-live="polite">
            {results.length === 0 && <li className="text-ink-500">{t('notifications.noChannels')}</li>}
            {results.map((result) => (
              <li key={result.channel} className={result.ok ? 'text-moss-700' : 'text-ink-700'}>
                {result.ok ? '✓' : '✗'} {t(`notifications.channel.${result.channel}`)} —{' '}
                {result.detail}
              </li>
            ))}
          </ul>
        )}
      </form>
    </div>
  );
}
