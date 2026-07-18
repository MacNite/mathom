import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { formatDuration } from '../components/MathomCard';
import StatusBadge from '../components/StatusBadge';
import { api } from '../lib/api';
import type { Collection, Mathom, PromptTemplate } from '../lib/types';

export default function MathomDetail() {
  const { id } = useParams();
  const mathomId = Number(id);
  const navigate = useNavigate();

  const [mathom, setMathom] = useState<Mathom | null>(null);
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [notFound, setNotFound] = useState(false);
  const [summarySlug, setSummarySlug] = useState('tldr');
  const [tagInput, setTagInput] = useState('');
  const [chatInput, setChatInput] = useState('');
  const [chatBusy, setChatBusy] = useState(false);
  const [summaryBusy, setSummaryBusy] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(() => {
    api
      .getMathom(mathomId)
      .then(setMathom)
      .catch(() => setNotFound(true));
  }, [mathomId]);

  useEffect(() => {
    refresh();
    api.listTemplates().then(setTemplates).catch(() => setTemplates([]));
    api.listCollections().then(setCollections).catch(() => setCollections([]));
  }, [refresh]);

  // Poll while the pipeline is still working on this mathom.
  useEffect(() => {
    if (!mathom || ['ready', 'error'].includes(mathom.status)) return;
    const timer = setInterval(refresh, 2500);
    return () => clearInterval(timer);
  }, [mathom, refresh]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [mathom?.chat_messages.length]);

  if (notFound) {
    return (
      <div className="card">
        <p>This Mathom is not on the shelves.</p>
        <Link to="/" className="text-hearth-600 underline">
          Back to the Library
        </Link>
      </div>
    );
  }
  if (!mathom) return <p className="text-ink-500">Fetching from the shelves…</p>;

  const patch = (changes: Parameters<typeof api.updateMathom>[1]) =>
    api.updateMathom(mathom.id, changes).then(setMathom);

  const addTag = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!tagInput.trim()) return;
    await api.addTag(mathom.id, tagInput.trim());
    setTagInput('');
    refresh();
  };

  const sendChat = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!chatInput.trim() || chatBusy) return;
    setChatBusy(true);
    try {
      await api.sendChat(mathom.id, chatInput.trim());
      setChatInput('');
      refresh();
    } finally {
      setChatBusy(false);
    }
  };

  const makeSummary = async () => {
    setSummaryBusy(true);
    try {
      await api.createSummary(mathom.id, summarySlug);
      refresh();
    } finally {
      setSummaryBusy(false);
    }
  };

  const removeMathom = async () => {
    if (!window.confirm('Remove this Mathom and its audio for good?')) return;
    await api.deleteMathom(mathom.id);
    navigate('/');
  };

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm text-ink-500 hover:text-hearth-600">
          ← Library
        </Link>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <input
            defaultValue={mathom.title}
            onBlur={(event) => {
              const title = event.target.value.trim();
              if (title && title !== mathom.title) void patch({ title });
            }}
            className="min-w-0 flex-1 border-b border-transparent bg-transparent font-display text-2xl text-ink-900 focus:border-hearth-500 focus:outline-none"
            aria-label="Title"
          />
          <div className="flex items-center gap-2">
            <StatusBadge status={mathom.status} />
            <button
              onClick={() => patch({ favorite: !mathom.favorite })}
              className="btn-ghost"
              title="Toggle favorite"
            >
              {mathom.favorite ? '★ Favorited' : '☆ Favorite'}
            </button>
            <button onClick={() => patch({ archived: !mathom.archived })} className="btn-ghost">
              {mathom.archived ? 'Unarchive' : 'Archive'}
            </button>
            <button onClick={removeMathom} className="btn-ghost text-red-700">
              Delete
            </button>
          </div>
        </div>
        <p className="mt-1 text-xs text-ink-500">
          {new Date(mathom.created_at).toLocaleString()}
          {mathom.duration_seconds != null && ` · ${formatDuration(mathom.duration_seconds)}`}
          {mathom.language && ` · ${mathom.language}`}
          {mathom.original_filename && ` · ${mathom.original_filename}`}
        </p>
        {mathom.status === 'error' && (
          <p className="mt-2 rounded-xl bg-red-100 p-3 text-sm text-red-700">
            {mathom.error_message ?? 'Something went wrong while processing this recording.'}
          </p>
        )}
      </div>

      <audio controls src={api.audioUrl(mathom.id)} className="w-full" preload="metadata" />

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-display text-lg">Tags & Collections</h3>
          <div className="flex gap-2 text-sm">
            {(['md', 'txt', 'json'] as const).map((format) => (
              <a
                key={format}
                href={api.exportUrl(mathom.id, format)}
                className="text-hearth-600 underline"
                download
              >
                export .{format}
              </a>
            ))}
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {mathom.tags.map((tag) => (
            <button
              key={tag.id}
              onClick={() => api.removeTag(mathom.id, tag.id).then(refresh)}
              className="chip hover:bg-red-100 hover:text-red-700"
              title="Remove tag"
            >
              #{tag.name} ×
            </button>
          ))}
          <form onSubmit={addTag}>
            <input
              value={tagInput}
              onChange={(event) => setTagInput(event.target.value)}
              placeholder="add tag ⏎"
              className="input w-32 py-1 text-xs"
            />
          </form>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          {collections.map((collection) => {
            const inCollection = mathom.collections.some((c) => c.id === collection.id);
            return (
              <button
                key={collection.id}
                onClick={() =>
                  (inCollection
                    ? api.removeFromCollection(collection.id, mathom.id)
                    : api.addToCollection(collection.id, mathom.id)
                  ).then(refresh)
                }
                className={`rounded-full px-3 py-1 ${
                  inCollection
                    ? 'bg-ink-900 text-parchment-50'
                    : 'border border-parchment-300 text-ink-700 hover:bg-parchment-100'
                }`}
              >
                🗂️ {collection.name}
              </button>
            );
          })}
          {collections.length === 0 && (
            <span className="text-ink-400">
              No collections yet — create one on the Collections page.
            </span>
          )}
        </div>
      </section>

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-display text-lg">Summaries</h3>
          <div className="flex items-center gap-2">
            <select
              value={summarySlug}
              onChange={(event) => setSummarySlug(event.target.value)}
              className="input w-auto py-1 text-sm"
            >
              {templates.map((template) => (
                <option key={template.slug} value={template.slug}>
                  {template.name}
                </option>
              ))}
            </select>
            <button
              onClick={makeSummary}
              disabled={summaryBusy || !mathom.transcript}
              className="btn-primary disabled:opacity-50"
            >
              {summaryBusy ? 'Thinking…' : 'Generate'}
            </button>
          </div>
        </div>
        {mathom.summaries.length === 0 ? (
          <p className="mt-3 text-sm text-ink-500">No summaries yet.</p>
        ) : (
          <div className="mt-3 space-y-4">
            {mathom.summaries.map((summary) => (
              <div key={summary.id} className="rounded-xl bg-parchment-100 p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-ink-500">
                  {summary.template_name} · {summary.model}
                </p>
                <p className="mt-2 whitespace-pre-wrap text-sm text-ink-900">{summary.content}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <h3 className="font-display text-lg">Transcript</h3>
        {mathom.transcript ? (
          <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-ink-700">
            {mathom.transcript}
          </p>
        ) : (
          <p className="mt-3 text-sm text-ink-500">
            The transcript will appear here once processing finishes.
          </p>
        )}
      </section>

      <section className="card">
        <div className="flex items-center justify-between">
          <h3 className="font-display text-lg">Ask about this recording</h3>
          {mathom.chat_messages.length > 0 && (
            <button
              onClick={() => api.clearChat(mathom.id).then(refresh)}
              className="text-sm text-ink-500 hover:text-red-700"
            >
              Clear conversation
            </button>
          )}
        </div>
        <div className="mt-3 max-h-96 space-y-3 overflow-y-auto">
          {mathom.chat_messages.map((message) => (
            <div
              key={message.id}
              className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm ${
                message.role === 'user'
                  ? 'ml-auto bg-hearth-100 text-ink-900'
                  : 'bg-parchment-100 text-ink-900'
              }`}
            >
              {message.content}
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>
        <form onSubmit={sendChat} className="mt-3 flex gap-2">
          <input
            value={chatInput}
            onChange={(event) => setChatInput(event.target.value)}
            placeholder={
              mathom.transcript
                ? 'e.g. What did we agree on?'
                : 'Available once the transcript is ready'
            }
            disabled={!mathom.transcript || chatBusy}
            className="input"
          />
          <button
            type="submit"
            disabled={!mathom.transcript || chatBusy}
            className="btn-primary disabled:opacity-50"
          >
            {chatBusy ? '…' : 'Ask'}
          </button>
        </form>
      </section>
    </div>
  );
}
