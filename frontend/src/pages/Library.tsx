import { useCallback, useEffect, useState } from 'react';

import MathomCard from '../components/MathomCard';
import UploadDialog from '../components/UploadDialog';
import { api } from '../lib/api';
import type { MathomListItem, SearchHit, Tag } from '../lib/types';

type Shelf = 'all' | 'favorites' | 'archived';

// Snippets arrive as plain text with <mark>…</mark> around matches. Render the
// highlights without injecting the transcript text as HTML.
export function renderSnippet(snippet: string) {
  return snippet.split(/<mark>(.*?)<\/mark>/g).map((part, index) =>
    index % 2 === 1 ? (
      <mark key={index} className="rounded bg-hearth-100 px-0.5 text-hearth-600">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

export default function Library() {
  const [mathoms, setMathoms] = useState<MathomListItem[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [shelf, setShelf] = useState<Shelf>('all');
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  const refresh = useCallback(() => {
    api
      .listMathoms({
        favorite: shelf === 'favorites' ? true : undefined,
        archived: shelf === 'archived',
        tag: activeTag ?? undefined,
      })
      .then(setMathoms)
      .catch(() => setMathoms([]));
    api.listTags().then(setTags).catch(() => setTags([]));
  }, [shelf, activeTag]);

  useEffect(refresh, [refresh]);

  // Poll while any mathom is still being processed.
  useEffect(() => {
    const busy = mathoms.some((m) => !['ready', 'error'].includes(m.status));
    if (!busy) return;
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, [mathoms, refresh]);

  useEffect(() => {
    if (!query.trim()) {
      setHits(null);
      return;
    }
    const timer = setTimeout(() => {
      api.search(query).then(setHits).catch(() => setHits([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);

  const shelves: { key: Shelf; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'favorites', label: '★ Favorites' },
    { key: 'archived', label: 'Archived' },
  ];

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-2xl text-ink-900">The Mathom-house</h2>
        <button onClick={() => setUploadOpen(true)} className="btn-primary">
          + New Mathom
        </button>
      </div>

      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search transcripts, summaries, titles…"
        className="input mt-4"
        type="search"
      />

      {hits === null && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {shelves.map((entry) => (
            <button
              key={entry.key}
              onClick={() => setShelf(entry.key)}
              className={`rounded-full px-3 py-1 text-sm ${
                shelf === entry.key
                  ? 'bg-ink-900 text-parchment-50'
                  : 'border border-parchment-300 text-ink-700 hover:bg-parchment-100'
              }`}
            >
              {entry.label}
            </button>
          ))}
          {tags.map((tag) => (
            <button
              key={tag.id}
              onClick={() => setActiveTag(activeTag === tag.name ? null : tag.name)}
              className={`rounded-full px-3 py-1 text-sm ${
                activeTag === tag.name
                  ? 'bg-moss-700 text-parchment-50'
                  : 'bg-moss-200 text-moss-700 hover:bg-moss-500 hover:text-parchment-50'
              }`}
            >
              #{tag.name}
            </button>
          ))}
        </div>
      )}

      {hits !== null ? (
        <div className="mt-6 space-y-3">
          <p className="text-sm text-ink-500">
            {hits.length} result{hits.length === 1 ? '' : 's'} for “{query}”
          </p>
          {hits.map((hit) => (
            <div key={hit.mathom.id}>
              <MathomCard mathom={hit.mathom} />
              <p className="mt-1 px-5 text-sm text-ink-500">{renderSnippet(hit.snippet)}</p>
            </div>
          ))}
        </div>
      ) : mathoms.length === 0 ? (
        <div className="card mt-8 text-center">
          <p className="font-display text-lg text-ink-700">The shelves are empty — for now.</p>
          <p className="mt-1 text-sm text-ink-500">
            Upload your first recording and Mathom will remember it for you.
          </p>
        </div>
      ) : (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {mathoms.map((mathom) => (
            <MathomCard key={mathom.id} mathom={mathom} />
          ))}
        </div>
      )}

      <UploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} onUploaded={refresh} />
    </div>
  );
}
