import { useCallback, useEffect, useRef, useState } from 'react';

import MathomCard from '../components/MathomCard';
import UploadDialog from '../components/UploadDialog';
import { api } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { useToast } from '../lib/toast';
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
  const { t } = useI18n();
  const toast = useToast();
  const [mathoms, setMathoms] = useState<MathomListItem[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [shelf, setShelf] = useState<Shelf>('all');
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(
    (options: { silent?: boolean } = {}) => {
      if (!options.silent) setLoading(true);
      api
        .listMathoms({
          favorite: shelf === 'favorites' ? true : undefined,
          archived: shelf === 'archived',
          tag: activeTag ?? undefined,
        })
        .then((list) => {
          setMathoms(list);
          setLoadError(false);
        })
        .catch(() => setLoadError(true))
        .finally(() => setLoading(false));
      api.listTags().then(setTags).catch(() => setTags([]));
    },
    [shelf, activeTag],
  );

  useEffect(() => refresh(), [refresh]);

  // Poll while any mathom is still being processed — but not while the tab is
  // hidden, so a backgrounded PWA doesn't keep hammering the API.
  useEffect(() => {
    const busy = mathoms.some((m) => !['ready', 'error'].includes(m.status));
    if (!busy) return;
    const tick = () => {
      if (!document.hidden) refresh({ silent: true });
    };
    const timer = setInterval(tick, 3000);
    return () => clearInterval(timer);
  }, [mathoms, refresh]);

  useEffect(() => {
    if (!query.trim()) {
      setHits(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    const timer = setTimeout(() => {
      api
        .search(query)
        .then(setHits)
        .catch(() => {
          setHits([]);
          toast.error(t('library.searchError'));
        })
        .finally(() => setSearching(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [query, toast, t]);

  // A "/" shortcut jumps focus to search, the way a keyboard-first archive should.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName);
      if (event.key === '/' && !typing) {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, []);

  const shelves: { key: Shelf; label: string }[] = [
    { key: 'all', label: t('library.shelf.all') },
    { key: 'favorites', label: t('library.shelf.favorites') },
    { key: 'archived', label: t('library.shelf.archived') },
  ];

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-2xl text-ink-900">{t('library.title')}</h2>
        <button onClick={() => setUploadOpen(true)} className="btn-primary">
          {t('library.newMathom')}
        </button>
      </div>

      <input
        ref={searchRef}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={t('library.searchPlaceholder')}
        className="input mt-4"
        type="search"
        aria-label={t('library.searchPlaceholder')}
      />

      {hits === null && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {shelves.map((entry) => (
            <button
              key={entry.key}
              onClick={() => setShelf(entry.key)}
              aria-pressed={shelf === entry.key}
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
              aria-pressed={activeTag === tag.name}
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
          <p className="text-sm text-ink-500" aria-live="polite">
            {searching ? t('library.searching') : t('library.results', { count: hits.length, query })}
          </p>
          {hits.map((hit) => (
            <div key={hit.mathom.id}>
              <MathomCard mathom={hit.mathom} />
              <p className="mt-1 px-5 text-sm text-ink-500">{renderSnippet(hit.snippet)}</p>
            </div>
          ))}
        </div>
      ) : loading ? (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-hidden>
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="card h-28 animate-pulse bg-parchment-100" />
          ))}
        </div>
      ) : loadError ? (
        <div className="card mt-8 text-center">
          <p className="font-display text-lg text-ink-700">{t('common.loadError')}</p>
          <button onClick={() => refresh()} className="btn-ghost mt-3">
            {t('common.retry')}
          </button>
        </div>
      ) : mathoms.length === 0 ? (
        <div className="card mt-8 text-center">
          <p className="font-display text-lg text-ink-700">{t('library.emptyTitle')}</p>
          <p className="mt-1 text-sm text-ink-500">{t('library.emptyBody')}</p>
        </div>
      ) : (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {mathoms.map((mathom) => (
            <MathomCard key={mathom.id} mathom={mathom} />
          ))}
        </div>
      )}

      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={() => refresh({ silent: true })}
      />
    </div>
  );
}
