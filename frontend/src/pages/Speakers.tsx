import { useCallback, useEffect, useMemo, useState } from 'react';

import { api } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { useToast } from '../lib/toast';
import type { Speaker } from '../lib/types';

export default function Speakers() {
  const { t } = useI18n();
  const toast = useToast();
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(
    () => api.listSpeakers().then(setSpeakers).finally(() => setLoading(false)),
    [],
  );
  useEffect(() => {
    void refresh().catch(() => toast.error(t('common.loadError')));
  }, [refresh, t, toast]);

  const visible = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return needle ? speakers.filter((speaker) => speaker.name.toLocaleLowerCase().includes(needle)) : speakers;
  }, [query, speakers]);

  const rename = async (speaker: Speaker) => {
    if (!name.trim() || name.trim() === speaker.name) return setEditing(null);
    try {
      await api.renameSpeaker(speaker.name, name.trim());
      setEditing(null);
      await refresh();
      toast.success(t('speakers.saved'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('settings.saveFailed'));
    }
  };

  const remove = async (speaker: Speaker) => {
    if (!window.confirm(t('speakers.confirmDelete', { name: speaker.name }))) return;
    try {
      await api.deleteSpeaker(speaker.name);
      await refresh();
      toast.success(t('speakers.deleted'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('settings.saveFailed'));
    }
  };

  return <div>
    <h2 className="font-display text-2xl text-ink-900">{t('speakers.title')}</h2>
    <p className="mt-1 text-sm text-ink-500">{t('speakers.subtitle')}</p>
    <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('speakers.search')} aria-label={t('speakers.search')} className="input mt-4" />
    {loading && <p className="mt-6 text-sm text-ink-500">{t('common.loading')}</p>}
    {!loading && visible.length === 0 && <p className="card mt-6 text-sm text-ink-500">{t('speakers.empty')}</p>}
    <div className="mt-6 space-y-3">
      {visible.map((speaker) => <section key={speaker.name} className="card flex flex-wrap items-center justify-between gap-3">
        <div>
          {editing === speaker.name ? <input autoFocus value={name} onChange={(event) => setName(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void rename(speaker); if (event.key === 'Escape') setEditing(null); }} className="input max-w-xs" aria-label={t('speakers.name')} /> : <strong className="text-ink-900">{speaker.name}</strong>}
          <span className="ml-3 text-xs text-ink-400">{t('speakers.count', { count: speaker.mathom_count })}</span>
        </div>
        <div className="flex gap-3 text-sm">
          {editing === speaker.name ? <><button onClick={() => void rename(speaker)} className="text-hearth-600">{t('speakers.save')}</button><button onClick={() => setEditing(null)} className="text-ink-500">{t('speakers.cancel')}</button></> : <button onClick={() => { setEditing(speaker.name); setName(speaker.name); }} className="text-ink-500 hover:text-hearth-600">{t('speakers.rename')}</button>}
          <button onClick={() => void remove(speaker)} className="text-ink-400 hover:text-red-700">{t('speakers.delete')}</button>
        </div>
      </section>)}
    </div>
  </div>;
}
