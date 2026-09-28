import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';

import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { formatDateTime } from '../lib/format';
import { useI18n } from '../lib/i18n';
import { useToast } from '../lib/toast';
import type { ApiToken, ApiTokenCreated, InboxStatus } from '../lib/types';

const EXPIRY_OPTIONS = [null, 30, 90, 365] as const;

export default function Automation() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const { status, isAdmin } = useAuth();
  const canSeeInbox = !status.auth_enabled || isAdmin;

  const [tokens, setTokens] = useState<ApiToken[] | null>(null);
  const [name, setName] = useState('');
  const [expiry, setExpiry] = useState<number | null>(null);
  const [created, setCreated] = useState<ApiTokenCreated | null>(null);
  const [inbox, setInbox] = useState<InboxStatus | null>(null);
  const [busy, setBusy] = useState(false);

  const refreshTokens = useCallback(async () => setTokens(await api.listApiTokens()), []);
  const refreshInbox = useCallback(async () => {
    if (canSeeInbox) setInbox(await api.getInboxStatus());
  }, [canSeeInbox]);

  useEffect(() => {
    void Promise.all([refreshTokens(), refreshInbox()]).catch(() =>
      toast.error(t('common.loadError')),
    );
  }, [refreshTokens, refreshInbox, t, toast]);

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

  const createToken = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    void run(async () => {
      setCreated(await api.createApiToken(name.trim(), expiry));
      setName('');
      await refreshTokens();
    });
  };

  const revoke = (token: ApiToken) => {
    if (!window.confirm(t('automation.confirmRevoke', { name: token.name }))) return;
    void run(async () => {
      await api.deleteApiToken(token.id);
      if (created?.id === token.id) setCreated(null);
      await refreshTokens();
    });
  };

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(t('automation.copied'));
    } catch {
      toast.error(t('automation.copyFailed'));
    }
  };

  const scanNow = () =>
    run(async () => {
      await api.scanInboxNow();
      toast.success(t('automation.inbox.scanStarted'));
      window.setTimeout(() => void refreshInbox().catch(() => undefined), 3000);
    });

  const origin = typeof window === 'undefined' ? '' : window.location.origin;
  const tokenForExample = created?.token ?? 'mth_…';
  const curlExample = [
    `curl -H "Authorization: Bearer ${tokenForExample}" \\`,
    `  -F "file=@PTT-20260722-WA0004.opus" \\`,
    `  -F "speaker=Rosie" -F "tags=family" \\`,
    `  ${origin}/api/ingest/audio`,
  ].join('\n');
  const rawExample = `${origin}/api/ingest/audio/raw?filename=%FILE_NAME`;

  return (
    <div className="max-w-3xl">
      <h2 className="font-display text-2xl text-ink-900">{t('automation.title')}</h2>
      <p className="mt-1 text-sm text-ink-500">{t('automation.subtitle')}</p>

      <section className="card mt-4 space-y-4">
        <div>
          <h3 className="font-display text-lg text-ink-900">{t('automation.tokens')}</h3>
          <p className="text-sm text-ink-500">{t('automation.tokensHint')}</p>
        </div>

        <form onSubmit={createToken} className="flex flex-wrap items-end gap-2">
          <label className="block flex-1 text-sm text-ink-700">
            {t('automation.tokenName')}
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t('automation.tokenNameHint')}
              maxLength={100}
              className="input mt-1"
            />
          </label>
          <label className="block text-sm text-ink-700">
            {t('automation.expires')}
            <select
              value={expiry ?? ''}
              onChange={(event) =>
                setExpiry(event.target.value ? Number(event.target.value) : null)
              }
              className="input mt-1"
            >
              {EXPIRY_OPTIONS.map((days) => (
                <option key={days ?? 'never'} value={days ?? ''}>
                  {days ? t('automation.expiresDays', { count: days }) : t('automation.never')}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" className="btn-primary" disabled={busy || !name.trim()}>
            {t('automation.createToken')}
          </button>
        </form>

        {created && (
          <div role="status" className="rounded border border-gild-300 bg-gild-200/30 p-3">
            <p className="text-sm font-medium text-ink-900">{t('automation.createdOnce')}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <code className="break-all font-mono text-xs text-ink-900">{created.token}</code>
              <button type="button" className="btn-ghost" onClick={() => void copy(created.token)}>
                {t('automation.copy')}
              </button>
            </div>
          </div>
        )}

        {tokens && tokens.length === 0 && (
          <p className="text-sm text-ink-500">{t('automation.noTokens')}</p>
        )}
        {tokens && tokens.length > 0 && (
          <ul className="divide-y divide-ink-400/20">
            {tokens.map((token) => (
              <li key={token.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <div className="text-sm">
                  <p className="font-medium text-ink-900">
                    {token.name}{' '}
                    <span className="font-mono text-xs text-ink-400">{token.prefix}…</span>
                  </p>
                  <p className="text-xs text-ink-500">
                    {t('automation.lastUsed')}:{' '}
                    {token.last_used_at
                      ? formatDateTime(token.last_used_at, lang)
                      : t('automation.neverUsed')}
                    {' · '}
                    {t('automation.expires')}:{' '}
                    {token.expires_at ? formatDateTime(token.expires_at, lang) : t('automation.never')}
                  </p>
                </div>
                <button
                  type="button"
                  className="btn-ghost"
                  disabled={busy}
                  onClick={() => revoke(token)}
                >
                  {t('automation.revoke')}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card mt-4 space-y-3">
        <h3 className="font-display text-lg text-ink-900">{t('automation.send')}</h3>
        <p className="text-sm text-ink-500">{t('automation.sendHint')}</p>
        <pre className="overflow-x-auto rounded bg-moss-900 p-3 font-mono text-xs text-gild-200">
          {curlExample}
        </pre>
        <p className="text-sm text-ink-700">
          <strong>Tasker</strong> — {t('automation.tasker')}
        </p>
        <pre className="overflow-x-auto rounded bg-moss-900 p-3 font-mono text-xs text-gild-200">
          {rawExample}
        </pre>
        <p className="text-sm text-ink-700">
          <strong>iOS Shortcuts</strong> — {t('automation.shortcuts')}
        </p>
        <p className="text-xs text-ink-500">{t('automation.fields')}</p>
      </section>

      {canSeeInbox && inbox && (
        <section className="card mt-4 space-y-3">
          <h3 className="font-display text-lg text-ink-900">{t('automation.inbox')}</h3>
          {!inbox.enabled ? (
            <p className="text-sm text-ink-500">{t('automation.inbox.off')}</p>
          ) : (
            <>
              <dl className="grid grid-cols-[auto,1fr] gap-x-4 gap-y-1 text-sm">
                <dt className="text-ink-500">{t('automation.inbox.folder')}</dt>
                <dd className="font-mono text-xs text-ink-900">{inbox.path}</dd>
                {inbox.owner_email && (
                  <>
                    <dt className="text-ink-500">{t('automation.inbox.owner')}</dt>
                    <dd className="text-ink-900">{inbox.owner_email}</dd>
                  </>
                )}
                <dt className="text-ink-500">{t('automation.inbox.lastScan')}</dt>
                <dd className="text-ink-900">
                  {inbox.last_scan_at
                    ? formatDateTime(inbox.last_scan_at, lang)
                    : t('automation.inbox.notYet')}
                </dd>
                <dt className="text-ink-500">{t('automation.inbox.imported')}</dt>
                <dd className="text-ink-900">{inbox.imported_total}</dd>
                <dt className="text-ink-500">{t('automation.inbox.waiting')}</dt>
                <dd className="text-ink-900">{inbox.waiting}</dd>
              </dl>
              {inbox.last_error && (
                <p role="alert" className="text-sm text-hearth-600">
                  {inbox.last_error}
                </p>
              )}
              <button
                type="button"
                className="btn-ghost"
                disabled={busy || !inbox.running}
                onClick={() => void scanNow()}
              >
                {t('automation.inbox.scanNow')}
              </button>
            </>
          )}
        </section>
      )}
    </div>
  );
}
