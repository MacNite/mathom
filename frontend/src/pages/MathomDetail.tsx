import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import StatusBadge from '../components/StatusBadge';
import { api } from '../lib/api';
import { formatDateTime, formatDuration } from '../lib/format';
import { useI18n } from '../lib/i18n';
import { useToast } from '../lib/toast';
import type { ChatMessage, Collection, Mathom, PromptTemplate } from '../lib/types';

export default function MathomDetail() {
  const { lang, t } = useI18n();
  const toast = useToast();
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
  const [pendingChat, setPendingChat] = useState<string | null>(null);
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
    api.listTemplates(lang).then(setTemplates).catch(() => setTemplates([]));
    api.listCollections().then(setCollections).catch(() => setCollections([]));
  }, [lang, refresh]);

  // Poll while the pipeline is still working on this mathom — but skip ticks
  // while the tab is hidden so a backgrounded PWA doesn't keep polling.
  useEffect(() => {
    if (!mathom || ['ready', 'error'].includes(mathom.status)) return;
    const timer = setInterval(() => {
      if (!document.hidden) refresh();
    }, 2500);
    return () => clearInterval(timer);
  }, [mathom, refresh]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [mathom?.chat_messages.length, pendingChat]);

  if (notFound) {
    return (
      <div className="card">
        <p>{t('detail.notFound')}</p>
        <Link to="/" className="text-hearth-600 underline">
          {t('detail.backToLibrary')}
        </Link>
      </div>
    );
  }
  if (!mathom) return <p className="text-ink-500">{t('detail.fetching')}</p>;

  const patch = (changes: Parameters<typeof api.updateMathom>[1]) =>
    api
      .updateMathom(mathom.id, changes)
      .then(setMathom)
      .catch((err) => toast.error(err instanceof Error ? err.message : t('settings.saveFailed')));

  const addTag = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!tagInput.trim()) return;
    try {
      await api.addTag(mathom.id, tagInput.trim());
      setTagInput('');
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('settings.saveFailed'));
    }
  };

  const sendChat = async (event: React.FormEvent) => {
    event.preventDefault();
    const message = chatInput.trim();
    if (!message || chatBusy) return;
    setChatBusy(true);
    // Echo the question immediately so the conversation feels responsive.
    setPendingChat(message);
    setChatInput('');
    try {
      await api.sendChat(mathom.id, message);
      refresh();
    } catch (err) {
      setChatInput(message);
      toast.error(err instanceof Error ? err.message : t('detail.chatFailed'));
    } finally {
      setPendingChat(null);
      setChatBusy(false);
    }
  };

  const makeSummary = async () => {
    setSummaryBusy(true);
    try {
      await api.createSummary(mathom.id, summarySlug, lang);
      refresh();
      toast.success(t('detail.summaryCreated'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('detail.summaryFailed'));
    } finally {
      setSummaryBusy(false);
    }
  };

  const removeSummary = async (summaryId: number) => {
    if (!window.confirm(t('detail.confirmDeleteSummary'))) return;
    try {
      await api.deleteSummary(mathom.id, summaryId);
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('settings.saveFailed'));
    }
  };

  const removeMathom = async () => {
    if (!window.confirm(t('detail.confirmDelete'))) return;
    try {
      await api.deleteMathom(mathom.id);
      toast.success(t('detail.deleted'));
      navigate('/');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('settings.saveFailed'));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm text-ink-500 hover:text-hearth-600">
          {t('detail.library')}
        </Link>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <input
            defaultValue={mathom.title}
            onKeyDown={(event) => {
              if (event.key === 'Enter') event.currentTarget.blur();
            }}
            onBlur={(event) => {
              const title = event.target.value.trim();
              if (title && title !== mathom.title) void patch({ title });
            }}
            className="min-w-0 flex-1 rounded-md border-b border-dashed border-parchment-300 bg-transparent px-1 font-display text-2xl text-ink-900 hover:border-hearth-400 focus:border-solid focus:border-hearth-500 focus:outline-none"
            aria-label={t('detail.titleLabel')}
            title={t('detail.titleLabel')}
          />
          <div className="flex items-center gap-2">
            <StatusBadge status={mathom.status} />
            <button
              onClick={() => patch({ favorite: !mathom.favorite })}
              className="btn-ghost"
              title={t('detail.toggleFavorite')}
            >
              {mathom.favorite ? t('detail.favorited') : t('detail.favorite')}
            </button>
            <button onClick={() => patch({ archived: !mathom.archived })} className="btn-ghost">
              {mathom.archived ? t('detail.unarchive') : t('detail.archive')}
            </button>
            <button onClick={removeMathom} className="btn-ghost text-red-700">
              {t('detail.delete')}
            </button>
          </div>
        </div>
        <p className="mt-1 text-xs text-ink-500">
          {formatDateTime(mathom.created_at, lang)}
          {mathom.duration_seconds != null && ` · ${formatDuration(mathom.duration_seconds, t)}`}
          {mathom.language && ` · ${mathom.language}`}
          {mathom.original_filename && ` · ${mathom.original_filename}`}
        </p>
        {mathom.status === 'error' && (
          <p className="mt-2 rounded-xl bg-red-100 p-3 text-sm text-red-700">
            {mathom.error_message ?? t('detail.errorFallback')}
          </p>
        )}
      </div>

      <audio controls src={api.audioUrl(mathom.id)} className="w-full" preload="metadata" />

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-display text-lg">{t('detail.tagsCollections')}</h3>
          <div className="flex gap-2 text-sm">
            {(['md', 'txt', 'json'] as const).map((format) => (
              <a
                key={format}
                href={api.exportUrl(mathom.id, format)}
                className="text-hearth-600 underline"
                download
              >
                {t('detail.export', { format })}
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
              title={t('detail.removeTag')}
            >
              #{tag.name} ×
            </button>
          ))}
          <form onSubmit={addTag}>
            <input
              value={tagInput}
              onChange={(event) => setTagInput(event.target.value)}
              placeholder={t('detail.addTag')}
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
            <span className="text-ink-400">{t('detail.noCollections')}</span>
          )}
        </div>
      </section>

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-display text-lg">{t('detail.summaries')}</h3>
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
              {summaryBusy ? t('detail.thinking') : t('detail.generate')}
            </button>
          </div>
        </div>
        {mathom.summaries.length === 0 ? (
          <p className="mt-3 text-sm text-ink-500">{t('detail.noSummaries')}</p>
        ) : (
          <div className="mt-3 space-y-4">
            {mathom.summaries.map((summary) => (
              <div key={summary.id} className="relative rounded-xl bg-parchment-100 p-4">
                <button
                  type="button"
                  onClick={() => void removeSummary(summary.id)}
                  className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full text-lg leading-none text-red-700 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-500"
                  aria-label={t('detail.confirmDeleteSummary')}
                  title={t('detail.delete')}
                >
                  ×
                </button>
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
        <h3 className="font-display text-lg">{t('detail.transcript')}</h3>
        {mathom.transcript ? (
          <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-ink-700">
            {mathom.transcript}
          </p>
        ) : (
          <p className="mt-3 text-sm text-ink-500">{t('detail.transcriptPending')}</p>
        )}
      </section>

      <section className="card">
        <div className="flex items-center justify-between">
          <h3 className="font-display text-lg">{t('detail.askTitle')}</h3>
          {mathom.chat_messages.length > 0 && (
            <button
              onClick={() => api.clearChat(mathom.id).then(refresh)}
              className="text-sm text-ink-500 hover:text-red-700"
            >
              {t('detail.clearConversation')}
            </button>
          )}
        </div>
        <div className="mt-3 max-h-96 space-y-3 overflow-y-auto">
          {mathom.chat_messages.map((message: ChatMessage) => (
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
          {pendingChat && (
            <>
              <div className="ml-auto max-w-[85%] rounded-2xl bg-hearth-100 px-4 py-2 text-sm text-ink-900 opacity-70">
                {pendingChat}
              </div>
              <div
                className="max-w-[85%] rounded-2xl bg-parchment-100 px-4 py-2 text-sm text-ink-400"
                aria-live="polite"
              >
                {t('detail.thinking')}
              </div>
            </>
          )}
          <div ref={chatEndRef} />
        </div>
        <form onSubmit={sendChat} className="mt-3 flex gap-2">
          <input
            value={chatInput}
            onChange={(event) => setChatInput(event.target.value)}
            placeholder={mathom.transcript ? t('detail.chatReady') : t('detail.chatWaiting')}
            disabled={!mathom.transcript || chatBusy}
            className="input"
          />
          <button
            type="submit"
            disabled={!mathom.transcript || chatBusy}
            className="btn-primary disabled:opacity-50"
          >
            {chatBusy ? '…' : t('detail.ask')}
          </button>
        </form>
      </section>
    </div>
  );
}
