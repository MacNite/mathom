import { useEffect, useState } from 'react';

import { api } from '../lib/api';
import type { PromptTemplate } from '../lib/types';

export default function Templates() {
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [selected, setSelected] = useState<PromptTemplate | null>(null);
  const [draft, setDraft] = useState({ name: '', description: '', prompt: '' });
  const [creating, setCreating] = useState(false);
  const [newSlug, setNewSlug] = useState('');
  const [message, setMessage] = useState('');

  const refresh = () =>
    api.listTemplates().then((list) => {
      setTemplates(list);
      return list;
    });

  useEffect(() => {
    void refresh();
  }, []);

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
        setMessage('Template created.');
      } else if (selected) {
        const updated = await api.updateTemplate(selected.id, draft);
        await refresh();
        select(updated);
        setMessage('Saved.');
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Saving failed');
    }
  };

  const remove = async () => {
    if (!selected) return;
    if (!window.confirm(`Delete template “${selected.name}”?`)) return;
    await api.deleteTemplate(selected.id);
    setSelected(null);
    await refresh();
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="font-display text-2xl text-ink-900">Prompt Templates</h2>
        <button onClick={startCreate} className="btn-primary">
          + New template
        </button>
      </div>
      <p className="mt-1 text-sm text-ink-500">
        Templates shape how Mathom writes summaries. Use{' '}
        <code className="rounded bg-parchment-200 px-1">{'{transcript}'}</code> where the
        transcript should go.
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
                {template.is_builtin && <span className="ml-1 text-xs text-ink-400">· built-in</span>}
              </button>
            </li>
          ))}
        </ul>

        {(selected || creating) && (
          <div className="card">
            {creating && (
              <label className="block text-sm text-ink-700">
                Slug
                <input
                  value={newSlug}
                  onChange={(event) => setNewSlug(event.target.value)}
                  placeholder="my-template"
                  className="input mt-1"
                />
              </label>
            )}
            <label className="mt-3 block text-sm text-ink-700">
              Name
              <input
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                className="input mt-1"
              />
            </label>
            <label className="mt-3 block text-sm text-ink-700">
              Description
              <input
                value={draft.description}
                onChange={(event) => setDraft({ ...draft, description: event.target.value })}
                className="input mt-1"
              />
            </label>
            <label className="mt-3 block text-sm text-ink-700">
              Prompt
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
                    Delete
                  </button>
                )}
                <button onClick={save} className="btn-primary">
                  {creating ? 'Create' : 'Save'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
