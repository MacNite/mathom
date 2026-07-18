import { useEffect, useState } from 'react';

import MathomCard from '../components/MathomCard';
import { api } from '../lib/api';
import type { Collection } from '../lib/types';

export default function Collections() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');

  const refresh = () => api.listCollections().then(setCollections);

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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create collection');
    }
  };

  const remove = async (collection: Collection) => {
    if (!window.confirm(`Delete collection “${collection.name}”? Mathoms stay in the library.`))
      return;
    await api.deleteCollection(collection.id);
    await refresh();
  };

  return (
    <div>
      <h2 className="font-display text-2xl text-ink-900">Collections</h2>
      <p className="mt-1 text-sm text-ink-500">Shelves for related recordings.</p>

      <form onSubmit={create} className="card mt-4 flex flex-wrap items-end gap-3">
        <label className="flex-1 text-sm text-ink-700">
          Name
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. House renovation"
            className="input mt-1"
          />
        </label>
        <label className="flex-[2] text-sm text-ink-700">
          Description
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="input mt-1"
          />
        </label>
        <button type="submit" className="btn-primary">
          Create
        </button>
        {error && <p className="w-full text-sm text-red-700">{error}</p>}
      </form>

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
                Delete
              </button>
            </div>
            {collection.mathoms.length === 0 ? (
              <p className="mt-3 text-sm text-ink-400">
                Empty — add Mathoms from their detail page.
              </p>
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
