import { useCallback, useEffect, useState } from 'react';

import { api } from '../lib/api';
import { useI18n } from '../lib/i18n';
import type { PromptTemplate } from '../lib/types';

export default function Templates() {
  const { lang, t } = useI18n();
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [selected, setSelected] = useState<PromptTemplate | null>(null);
  const [draft, setDraft] = useState({ name: '', description: '', prompt: '' });
  const [creating, setCreating] = useState(false);
  const [newSlug, setNewSlug] = useState('');
  const [message, setMessage] = useState('');

  const refresh = useCallback(
    () =>
      api.listTemplates(lang).then((list) => {
        setTemplates(list);
        return list;
      }),
    [lang],
  );

  useEffect(() => {
    setSelected(null);
    setCreating(false);
    void refresh();
  }, [refresh]);

  const select = (template: PromptTemplate) => {
    setSelected(template);
    setCreating(false);
    setDraft({
      name: template.name,
      description: template.description,
      prompt: template.prompt,
    });
    setMessage('');
  };

  const startCreate = () => {
    setSelected(null);
    setCreating(true);
    setDraft({ name: '', description: '', prompt: 'Do something useful with:\n\n{transcript}' });
    setNewSlug('');
    setMessage('');
  };

  const save = async () => {
    try {
      if (creating) {
        const created = await api.createTemplate({ slug: newSlug, ...draft });
        await refresh();
        select(created);
        setMessage(t('templates.created'));
      } else if (selected) {
        const updated = await api.updateTemplate(selected.id, draft);
        await refresh();
        select(updated);
        setMessage(t('templates.saved'));
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : t('templates.saveFailed'));
    }
  };

  const remove = async () => {
    if (!selected) return;
    if (!window.confirm(t('templates.confirmDelete', { name: selected.name }))) return;
    await api.deleteTemplate(selected.id);
    setSelected(null);
    await refresh();
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="font-display text-2xl text-ink-900">{t('templates.title')}</h2>
        <button onClick={startCreate} className="btn-primary">
          {t('templates.new')}
        </button>
      </div>
      <p className="mt-1 text-sm text-ink-500">
        {t('templates.helpBefore')}
        <code className="rounded bg-parchment-200 px-1">{'{transcript}'}</code>
        {t('templates.helpAfter')}
      </p>

      <div className="mt-6 grid gap-6 md:grid-cols-[240px,1fr]">
        <ul className="space-y-1">
          {templates.map((template) => (
            <li key={template.id}>
              <button
                onClick={() => select(template)}
                className={`w-full rounded-xl px-3 py-2 text-left text-sm ${
                  selected?.id === template.id
                    ? 'bg-hearth-100 font-medium text-hearth-600'
                    : 'text-ink-700 hover:bg-parchment-100'
                }`}
              >
                {template.name}
                {template.is_builtin && (
                  <span className="ml-1 text-xs text-ink-400">· {t('templates.builtin')}</span>
                )}
              </button>
            </li>
          ))}
        </ul>

        {(selected || creating) && (
          <div className="card">
            {creating && (
              <label className="block text-sm text-ink-700">
                {t('templates.slug')}
                <input
                  value={newSlug}
                  onChange={(event) => setNewSlug(event.target.value)}
                  placeholder={t('templates.slugPlaceholder')}
                  className="input mt-1"
                />
              </label>
            )}
            <label className="mt-3 block text-sm text-ink-700">
              {t('templates.name')}
              <input
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                className="input mt-1"
              />
            </label>
            <label className="mt-3 block text-sm text-ink-700">
              {t('templates.description')}
              <input
                value={draft.description}
                onChange={(event) => setDraft({ ...draft, description: event.target.value })}
                className="input mt-1"
              />
            </label>
            <label className="mt-3 block text-sm text-ink-700">
              {t('templates.prompt')}
              <textarea
                value={draft.prompt}
                onChange={(event) => setDraft({ ...draft, prompt: event.target.value })}
                rows={10}
                className="input mt-1 font-mono text-xs"
              />
            </label>
            <div className="mt-4 flex items-center justify-between">
              <span className="text-sm text-moss-700">{message}</span>
              <div className="flex gap-2">
                {selected && (
                  <button onClick={remove} className="btn-ghost text-red-700">
                    {t('templates.delete')}
                  </button>
                )}
                <button onClick={save} className="btn-primary">
                  {creating ? t('templates.create') : t('templates.save')}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
