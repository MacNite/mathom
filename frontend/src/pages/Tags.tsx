import { useEffect, useState } from 'react';

import { api } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { chipClasses, swatchClasses, TAG_COLORS } from '../lib/tagColor';
import { useToast } from '../lib/toast';
import type { Tag } from '../lib/types';

export default function Tags() {
  const { t } = useI18n();
  const toast = useToast();
  const [tags, setTags] = useState<Tag[]>([]);
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [mergeTargets, setMergeTargets] = useState<Record<number, number>>({});

  const refresh = () => {
    setLoading(true);
    return api
      .listTags()
      .then((list) => {
        setTags(list);
        setLoadError(false);
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    void refresh();
  }, []);

  const fail = (err: unknown) =>
    toast.error(err instanceof Error ? err.message : t('settings.saveFailed'));

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    setError('');
    try {
      await api.createTag(name.trim());
      setName('');
      await refresh();
      toast.success(t('tags.created'));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('settings.saveFailed'));
    }
  };

  const recolour = async (tag: Tag, color: string) => {
    try {
      await api.updateTag(tag.id, { color });
      await refresh();
    } catch (err) {
      fail(err);
    }
  };

  const rename = async (tag: Tag) => {
    if (!editName.trim() || editName.trim() === tag.name) {
      setEditingId(null);
      return;
    }
    try {
      await api.updateTag(tag.id, { name: editName.trim() });
      setEditingId(null);
      await refresh();
      toast.success(t('tags.saved'));
    } catch (err) {
      fail(err);
    }
  };

  const remove = async (tag: Tag) => {
    if (!window.confirm(t('tags.confirmDelete', { name: tag.name }))) return;
    try {
      await api.deleteTag(tag.id);
      await refresh();
      toast.success(t('tags.deleted'));
    } catch (err) {
      fail(err);
    }
  };

  const merge = async (tag: Tag) => {
    const into = mergeTargets[tag.id];
    if (!into) return;
    try {
      await api.mergeTag(tag.id, into);
      setMergeTargets((current) => {
        const next = { ...current };
        delete next[tag.id];
        return next;
      });
      await refresh();
      toast.success(t('tags.merged'));
    } catch (err) {
      fail(err);
    }
  };

  return (
    <div>
      <h2 className="font-display text-2xl text-ink-900">{t('tags.title')}</h2>
      <p className="mt-1 text-sm text-ink-500">{t('tags.subtitle')}</p>

      <form onSubmit={create} className="card mt-4 flex flex-wrap items-end gap-3">
        <label className="flex-1 text-sm text-ink-700">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={t('tags.newPlaceholder')}
            className="input mt-1"
          />
        </label>
        <button type="submit" className="btn-primary">
          {t('tags.create')}
        </button>
        {error && <p className="w-full text-sm text-red-700">{error}</p>}
      </form>

      {loading && <p className="mt-6 text-sm text-ink-500">{t('common.loading')}</p>}
      {loadError && !loading && (
        <div className="card mt-6 text-center">
          <p className="text-sm text-red-700">{t('common.loadError')}</p>
          <button onClick={() => void refresh()} className="btn-ghost mt-3">
            {t('common.retry')}
          </button>
        </div>
      )}
      {!loading && !loadError && tags.length === 0 && (
        <p className="card mt-6 text-sm text-ink-500">{t('tags.empty')}</p>
      )}

      <div className="mt-6 space-y-3">
        {tags.map((tag) => (
          <section key={tag.id} className="card">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                {editingId === tag.id ? (
                  <TagNameEditor
                    value={editName}
                    onChange={setEditName}
                    onSave={() => rename(tag)}
                    onCancel={() => setEditingId(null)}
                    saveLabel={t('tags.save')}
                    cancelLabel={t('tags.cancel')}
                  />
                ) : (
                  <span
                    className={`inline-flex items-center rounded-sm px-2 py-0.5 text-[11px] uppercase tracking-wide ${chipClasses(
                      tag.color,
                    )}`}
                  >
                    {tag.name}
                  </span>
                )}
                {tag.kind === 'source' && (
                  <span
                    className="rounded-sm border border-parchment-300 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-ink-400"
                    title={t('tags.sourceLocked')}
                  >
                    {t('tags.source')}
                  </span>
                )}
                <span className="text-xs text-ink-400">
                  {t('tags.count', { count: tag.mathom_count ?? 0 })}
                </span>
              </div>

              <div className="flex items-center gap-3 text-sm">
                {tag.kind !== 'source' && editingId !== tag.id && (
                  <button
                    onClick={() => {
                      setEditingId(tag.id);
                      setEditName(tag.name);
                    }}
                    className="text-ink-500 hover:text-hearth-600"
                  >
                    {t('tags.rename')}
                  </button>
                )}
                <button onClick={() => remove(tag)} className="text-ink-400 hover:text-red-700">
                  {t('tags.delete')}
                </button>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              {TAG_COLORS.map((color) => (
                <button
                  key={color}
                  onClick={() => recolour(tag, color)}
                  aria-label={color}
                  aria-pressed={tag.color === color}
                  className={`h-5 w-5 rounded-sm ${swatchClasses(color)} ${
                    tag.color === color
                      ? 'ring-2 ring-ink-900 ring-offset-1 ring-offset-parchment-50'
                      : 'opacity-70 hover:opacity-100'
                  }`}
                />
              ))}
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
              <span className="text-xs uppercase tracking-wide text-ink-400">
                {t('tags.mergeInto', { name: tag.name })}
              </span>
              <select
                value={mergeTargets[tag.id] ?? ''}
                onChange={(event) =>
                  setMergeTargets((current) => ({
                    ...current,
                    [tag.id]: Number(event.target.value),
                  }))
                }
                className="rounded border border-parchment-300 bg-parchment-50 px-2 py-1 text-sm text-ink-900"
              >
                <option value="">{t('tags.mergePick')}</option>
                {tags
                  .filter((other) => other.id !== tag.id)
                  .map((other) => (
                    <option key={other.id} value={other.id}>
                      {other.name}
                    </option>
                  ))}
              </select>
              <button
                onClick={() => merge(tag)}
                disabled={!mergeTargets[tag.id]}
                className="btn-ghost px-3 py-1 text-xs disabled:opacity-40"
              >
                {t('tags.mergeConfirm')}
              </button>
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

interface TagNameEditorProps {
  value: string;
  onChange: (value: string) => void;
  onSave: () => void;
  onCancel: () => void;
  saveLabel: string;
  cancelLabel: string;
}

function TagNameEditor({
  value,
  onChange,
  onSave,
  onCancel,
  saveLabel,
  cancelLabel,
}: TagNameEditorProps) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSave();
      }}
      className="flex items-center gap-2"
    >
      <input
        autoFocus
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="input w-40 py-1 text-xs"
      />
      <button type="submit" className="text-xs text-hearth-600 hover:underline">
        {saveLabel}
      </button>
      <button type="button" onClick={onCancel} className="text-xs text-ink-400 hover:underline">
        {cancelLabel}
      </button>
    </form>
  );
}
