import { useEffect, useState } from 'react';

import MathomCard from '../components/MathomCard';
import { api } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { useToast } from '../lib/toast';
import type { Collection } from '../lib/types';

export default function Collections() {
  const { t } = useI18n();
  const toast = useToast();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const refresh = () => {
    setLoading(true);
    return api
      .listCollections()
      .then((list) => {
        setCollections(list);
        setLoadError(false);
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    void refresh();
  }, []);

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    setError('');
    try {
      await api.createCollection(name.trim(), description.trim());
      setName('');
      setDescription('');
      await refresh();
      toast.success(t('collections.created'));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('collections.createError'));
    }
  };

  const remove = async (collection: Collection) => {
    if (!window.confirm(t('collections.confirmDelete', { name: collection.name }))) return;
    try {
      await api.deleteCollection(collection.id);
      await refresh();
      toast.success(t('collections.deleted'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('settings.saveFailed'));
    }
  };

  return (
    <div>
      <h2 className="font-display text-2xl text-ink-900">{t('collections.title')}</h2>
      <p className="mt-1 text-sm text-ink-500">{t('collections.subtitle')}</p>

      <form onSubmit={create} className="card mt-4 flex flex-wrap items-end gap-3">
        <label className="flex-1 text-sm text-ink-700">
          {t('collections.name')}
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={t('collections.namePlaceholder')}
            className="input mt-1"
          />
        </label>
        <label className="flex-[2] text-sm text-ink-700">
          {t('collections.description')}
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="input mt-1"
          />
        </label>
        <button type="submit" className="btn-primary">
          {t('collections.create')}
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
      {!loading && !loadError && collections.length === 0 && (
        <p className="card mt-6 text-sm text-ink-500">{t('collections.none')}</p>
      )}

      <div className="mt-6 space-y-6">
        {collections.map((collection) => (
          <section key={collection.id} className="card">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-display text-lg text-ink-900">🗂️ {collection.name}</h3>
                {collection.description && (
                  <p className="text-sm text-ink-500">{collection.description}</p>
                )}
              </div>
              <button
                onClick={() => remove(collection)}
                className="text-sm text-ink-400 hover:text-red-700"
              >
                {t('collections.delete')}
              </button>
            </div>
            {collection.mathoms.length === 0 ? (
              <p className="mt-3 text-sm text-ink-400">{t('collections.empty')}</p>
            ) : (
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {collection.mathoms.map((mathom) => (
                  <MathomCard key={mathom.id} mathom={mathom} />
                ))}
              </div>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}
