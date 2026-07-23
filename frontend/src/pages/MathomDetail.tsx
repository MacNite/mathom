import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import StatusBadge from "../components/StatusBadge";
import { api } from "../lib/api";
import { formatDateTime, formatDuration } from "../lib/format";
import { useI18n } from "../lib/i18n";
import { canShareText, shareText } from "../lib/pwa";
import { chipClasses } from "../lib/tagColor";
import { useToast } from "../lib/toast";
import type {
  ChatMessage,
  Collection,
  Mathom,
  PromptTemplate,
  Summary,
} from "../lib/types";

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
  const [summarySlug, setSummarySlug] = useState("tldr");
  const [tagInput, setTagInput] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [pendingChat, setPendingChat] = useState<string | null>(null);
  const [summaryBusy, setSummaryBusy] = useState(false);
  const [streamingSummary, setStreamingSummary] = useState("");
  const [streamingSummaryId, setStreamingSummaryId] = useState<number | null>(null);
  const [editingSummaryId, setEditingSummaryId] = useState<number | null>(null);
  const [summaryDraft, setSummaryDraft] = useState("");
  const [streamingChat, setStreamingChat] = useState("");
  const [editingTranscript, setEditingTranscript] = useState(false);
  const [transcriptDraft, setTranscriptDraft] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [currentTime, setCurrentTime] = useState(0);
  // Feature-detected once: iOS/Android can pass text to the native share sheet,
  // most desktop browsers cannot, so the button only appears where it works.
  const [canShare] = useState(canShareText);

  const refresh = useCallback(() => {
    api
      .getMathom(mathomId)
      .then(setMathom)
      .catch(() => setNotFound(true));
  }, [mathomId]);

  useEffect(() => {
    refresh();
    api
      .listTemplates(lang)
      .then(setTemplates)
      .catch(() => setTemplates([]));
    api
      .listCollections()
      .then(setCollections)
      .catch(() => setCollections([]));
  }, [lang, refresh]);

  // Poll while the pipeline is still working on this mathom — but skip ticks
  // while the tab is hidden so a backgrounded PWA doesn't keep polling. Visual
  // analysis can be started after an otherwise failed or ready recording, so
  // its independent status must keep this view fresh too.
  useEffect(() => {
    if (
      !mathom ||
      (["ready", "error"].includes(mathom.status) &&
        !["pending", "processing"].includes(mathom.vision_status ?? "not_requested"))
    ) {
      return;
    }
    const timer = setInterval(() => {
      if (!document.hidden) refresh();
    }, 2500);
    return () => clearInterval(timer);
  }, [mathom, refresh]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mathom?.chat_messages.length, pendingChat]);

  if (notFound) {
    return (
      <div className="card">
        <p>{t("detail.notFound")}</p>
        <Link to="/" className="text-hearth-600 underline">
          {t("detail.backToLibrary")}
        </Link>
      </div>
    );
  }
  if (!mathom) return <p className="text-ink-500">{t("detail.fetching")}</p>;

  const patch = (changes: Parameters<typeof api.updateMathom>[1]) =>
    api
      .updateMathom(mathom.id, changes)
      .then(setMathom)
      .catch((err) =>
        toast.error(
          err instanceof Error ? err.message : t("settings.saveFailed"),
        ),
      );

  const addTag = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!tagInput.trim()) return;
    try {
      await api.addTag(mathom.id, tagInput.trim());
      setTagInput("");
      refresh();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("settings.saveFailed"),
      );
    }
  };

  const sendChat = async (event: React.FormEvent) => {
    event.preventDefault();
    const message = chatInput.trim();
    if (!message || chatBusy) return;
    setChatBusy(true);
    // Echo the question immediately so the conversation feels responsive.
    setPendingChat(message);
    setChatInput("");
    try {
      setStreamingChat("");
      await api.streamChat(mathom.id, message, (token) =>
        setStreamingChat((current) => current + token),
      );
      refresh();
    } catch (err) {
      setChatInput(message);
      toast.error(err instanceof Error ? err.message : t("detail.chatFailed"));
    } finally {
      setPendingChat(null);
      setStreamingChat("");
      setChatBusy(false);
    }
  };

  const makeSummary = async () => {
    setSummaryBusy(true);
    setStreamingSummaryId(null);
    try {
      setStreamingSummary("");
      await api.streamSummary(mathom.id, summarySlug, lang, (token) =>
        setStreamingSummary((current) => current + token),
      );
      refresh();
      toast.success(t("detail.summaryCreated"));
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("detail.summaryFailed"),
      );
    } finally {
      setStreamingSummary("");
      setStreamingSummaryId(null);
      setSummaryBusy(false);
    }
  };

  const saveSummary = async (summaryId: number) => {
    try {
      await api.updateSummary(mathom.id, summaryId, summaryDraft);
      setEditingSummaryId(null);
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("settings.saveFailed"));
    }
  };

  const regenerateSummary = async (summary: Summary) => {
    setSummaryBusy(true);
    setStreamingSummaryId(summary.id);
    setStreamingSummary("");
    try {
      await api.streamSummary(
        mathom.id,
        summary.template_slug,
        lang,
        (token) => setStreamingSummary((current) => current + token),
        summary.id,
      );
      refresh();
      toast.success(t("detail.summaryCreated"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("detail.summaryFailed"));
    } finally {
      setStreamingSummary("");
      setStreamingSummaryId(null);
      setSummaryBusy(false);
    }
  };

  const removeSummary = async (summaryId: number) => {
    if (!window.confirm(t("detail.confirmDeleteSummary"))) return;
    try {
      await api.deleteSummary(mathom.id, summaryId);
      refresh();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("settings.saveFailed"),
      );
    }
  };

  const removeMathom = async () => {
    if (!window.confirm(t("detail.confirmDelete"))) return;
    try {
      await api.deleteMathom(mathom.id);
      toast.success(t("detail.deleted"));
      navigate("/");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : t("settings.saveFailed"),
      );
    }
  };
  const shareOut = async () => {
    if (!mathom) return;
    // Prefer the newest summary as the shareable gist; fall back to the
    // transcript, then to just the title so there is always something to send.
    const body = mathom.summaries[0]?.content || mathom.transcript || "";
    const text = [mathom.title, body].filter(Boolean).join("\n\n");
    try {
      await shareText({ title: mathom.title, text });
    } catch {
      toast.error(t("detail.shareFailed"));
    }
  };

  const seekObservation = (seconds: number) => {
    const player = videoRef.current ?? audioRef.current;
    if (player) {
      player.currentTime = seconds;
      void player.play();
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm text-ink-500 hover:text-hearth-600">
          {t("detail.library")}
        </Link>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <input
            defaultValue={mathom.title}
            onKeyDown={(event) => {
              if (event.key === "Enter") event.currentTarget.blur();
            }}
            onBlur={(event) => {
              const title = event.target.value.trim();
              if (title && title !== mathom.title) void patch({ title });
            }}
            className="min-w-0 flex-1 rounded-md border-b border-dashed border-parchment-300 bg-transparent px-1 font-display text-2xl text-ink-900 hover:border-hearth-400 focus:border-solid focus:border-hearth-500 focus:outline-none"
            aria-label={t("detail.titleLabel")}
            title={t("detail.titleLabel")}
          />
          <div className="flex items-center gap-2">
            <StatusBadge status={mathom.status} />
            {canShare && (
              <button
                onClick={() => void shareOut()}
                className="btn-ghost"
                title={t("detail.share")}
              >
                {t("detail.share")}
              </button>
            )}
            <button
              onClick={() => patch({ favorite: !mathom.favorite })}
              className="btn-ghost"
              title={t("detail.toggleFavorite")}
            >
              {mathom.favorite ? t("detail.favorited") : t("detail.favorite")}
            </button>
            <button
              onClick={() => patch({ archived: !mathom.archived })}
              className="btn-ghost"
            >
              {mathom.archived ? t("detail.unarchive") : t("detail.archive")}
            </button>
            <button onClick={removeMathom} className="btn-ghost text-red-700">
              {t("detail.delete")}
            </button>
          </div>
        </div>
        <p className="mt-1 text-xs text-ink-500">
          {formatDateTime(mathom.created_at, lang)}
          {mathom.duration_seconds != null &&
            ` · ${formatDuration(mathom.duration_seconds, t)}`}
          {mathom.language && ` · ${mathom.language}`}
          {mathom.speaker && ` · ${t("detail.speakerPrefix")}: ${mathom.speaker}`}
          {mathom.original_filename && ` · ${mathom.original_filename}`}
        </p>
        {mathom.status === "error" && (
          <p className="mt-2 rounded-xl bg-red-100 p-3 text-sm text-red-700">
            {mathom.error_message ?? t("detail.errorFallback")}
          </p>
        )}
        {mathom.queue_position != null && (
          <p className="mt-2 text-sm text-ink-500">
            Waiting in processing queue: #{mathom.queue_position}
          </p>
        )}
      </div>

      {mathom.has_video_stream ? (
        <video
          ref={videoRef}
          controls
          src={api.audioUrl(mathom.id)}
          className="w-full"
          preload="metadata"
          onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
        />
      ) : (
        mathom.has_audio_stream && (
          <audio
            ref={audioRef}
            controls
            src={api.audioUrl(mathom.id)}
            className="w-full"
            preload="metadata"
            onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
          />
        )
      )}

      {mathom.has_video_stream && (
        <section className="card">
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-display text-lg">Visual analysis</h3>
            <button
              className="btn-ghost"
              disabled={["pending", "processing"].includes(mathom.vision_status ?? "not_requested")}
              onClick={() =>
                api
                  .rerunVisualAnalysis(mathom.id)
                  .then(setMathom)
                  .catch((err) =>
                    toast.error(
                      err instanceof Error ? err.message : 'Could not start visual analysis',
                    ),
                  )
              }
            >
              Run again
            </button>
          </div>
          <p className="text-sm text-ink-500">
            {mathom.vision_status}
            {mathom.vision_model ? ` · ${mathom.vision_model}` : ''}
          </p>
          {mathom.vision_error_message && (
            <p className="mt-2 text-sm text-amber-800">{mathom.vision_error_message}</p>
          )}
          {mathom.visual_summary && (
            <>
              <h4 className="mt-3 font-medium">
                Visual summary{' '}
                <span className="text-xs text-ink-500">AI-generated from sampled frames</span>
              </h4>
              <p className="mt-1 whitespace-pre-wrap">{mathom.visual_summary}</p>
            </>
          )}
          <ul className="mt-3 space-y-2">
            {(mathom.visual_observations ?? []).map((observation) => (
              <li key={observation.frame_index}>
                <button
                  className="text-hearth-600 underline"
                  onClick={() => seekObservation(observation.timestamp_seconds)}
                >
                  {observation.timestamp_seconds.toFixed(1)}s
                </button>{' '}
                · {observation.description}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-display text-lg">
            {t("detail.tagsCollections")}
          </h3>
          <div className="flex gap-2 text-sm">
            {(['md', 'txt', 'json', ...(['audio', 'video_audio'].includes(mathom.source_type ?? 'audio') ? ['srt', 'vtt'] : [])] as Array<'md' | 'txt' | 'json' | 'srt' | 'vtt'>).map((format) => (
              <a
                key={format}
                href={api.exportUrl(mathom.id, format)}
                className="text-hearth-600 underline"
                download
              >
                {t("detail.export", { format })}
              </a>
            ))}
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {mathom.tags.map((tag) => (
            <button
              key={tag.id}
              onClick={() => api.removeTag(mathom.id, tag.id).then(refresh)}
              className={`inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-[11px] uppercase tracking-wide transition-opacity hover:opacity-80 ${chipClasses(tag.color)}`}
              title={t("detail.removeTag")}
            >
              {tag.name} ×
            </button>
          ))}
          <form onSubmit={addTag}>
            <input
              value={tagInput}
              onChange={(event) => setTagInput(event.target.value)}
              placeholder={t("detail.addTag")}
              className="input w-32 py-1 text-xs"
            />
          </form>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          {collections.map((collection) => {
            const inCollection = mathom.collections.some(
              (c) => c.id === collection.id,
            );
            return (
              <button
                key={collection.id}
                onClick={() =>
                  (inCollection
                    ? api.removeFromCollection(collection.id, mathom.id)
                    : api.addToCollection(collection.id, mathom.id)
                  ).then(refresh)
                }
                className={`rounded-sm px-3 py-1 text-xs uppercase tracking-wide ${
                  inCollection
                    ? "bg-moss-700 text-parchment-50"
                    : "border border-parchment-300 text-ink-700 hover:bg-parchment-100"
                }`}
              >
                🗂️ {collection.name}
              </button>
            );
          })}
          {collections.length === 0 && (
            <span className="text-ink-400">{t("detail.noCollections")}</span>
          )}
        </div>
      </section>

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-display text-lg">{t("detail.summaries")}</h3>
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
              {summaryBusy ? t("detail.thinking") : t("detail.generate")}
            </button>
          </div>
        </div>
        {streamingSummary && streamingSummaryId === null && (
          <div className="mt-3 rounded-xl bg-parchment-100 p-4 text-sm whitespace-pre-wrap">
            {streamingSummary}
          </div>
        )}
        {mathom.summaries.length === 0 ? (
          <p className="mt-3 text-sm text-ink-500">{t("detail.noSummaries")}</p>
        ) : (
          <div className="mt-3 space-y-4">
            {mathom.summaries.map((summary) => (
              <div
                key={summary.id}
                className="relative rounded-xl bg-parchment-100 p-4"
              >
                <button
                  type="button"
                  onClick={() => void removeSummary(summary.id)}
                  className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full text-lg leading-none text-red-700 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-500"
                  aria-label={t("detail.confirmDeleteSummary")}
                  title={t("detail.delete")}
                >
                  ×
                </button>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-500">
                  {summary.template_name} · {summary.model}
                </p>
                {editingSummaryId === summary.id ? (
                  <div className="mt-2">
                    <textarea
                      value={summaryDraft}
                      onChange={(event) => setSummaryDraft(event.target.value)}
                      className="input min-h-32"
                    />
                    <div className="mt-2 flex gap-2">
                      <button className="btn-primary" onClick={() => void saveSummary(summary.id)}>
                        Save
                      </button>
                      <button className="btn-ghost" onClick={() => setEditingSummaryId(null)}>
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-ink-900">
                      {streamingSummaryId === summary.id ? streamingSummary : summary.content}
                    </p>
                    <div className="mt-2 flex gap-2">
                      <button
                        className="btn-ghost text-sm"
                        onClick={() => {
                          setSummaryDraft(summary.content);
                          setEditingSummaryId(summary.id);
                        }}
                        disabled={summaryBusy}
                      >
                        Edit
                      </button>
                      <button
                        className="btn-ghost text-sm"
                        onClick={() => void regenerateSummary(summary)}
                        disabled={summaryBusy}
                      >
                        Regenerate
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <div className="flex items-center justify-between">
          <h3 className="font-display text-lg">{t("detail.transcript")}</h3>
          {mathom.transcript && (
            <button
              className="btn-ghost text-sm"
              onClick={() => {
                setTranscriptDraft(mathom.transcript ?? "");
                setEditingTranscript(true);
              }}
            >
              Edit
            </button>
          )}
        </div>
        {mathom.transcript ? (
          editingTranscript ? (
            <div className="mt-3">
              <textarea
                value={transcriptDraft}
                onChange={(event) => setTranscriptDraft(event.target.value)}
                className="input min-h-48"
              />
              <div className="mt-2 flex gap-2">
                <button
                  className="btn-primary"
                  onClick={() =>
                    void patch({ transcript: transcriptDraft }).then(() =>
                      setEditingTranscript(false),
                    )
                  }
                >
                  Save
                </button>
                <button
                  className="btn-ghost"
                  onClick={() => setEditingTranscript(false)}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : mathom.segments.length > 0 ? (
            <div className="mt-3 space-y-1 text-sm leading-relaxed">
              {mathom.segments.map((segment, index) => {
                const active =
                  currentTime >= segment.start && currentTime < segment.end;
                return (
                  <button
                    key={`${segment.start}-${index}`}
                    type="button"
                    onClick={() => {
                      if (audioRef.current) {
                        audioRef.current.currentTime = segment.start;
                        void audioRef.current.play();
                      }
                    }}
                    className={`block w-full rounded-md px-2 py-1 text-left transition ${
                      active
                        ? "bg-hearth-100 text-ink-900"
                        : "text-ink-700 hover:bg-parchment-100"
                    }`}
                  >
                    <span className="mr-2 font-mono text-xs text-ink-400">
                      {Math.floor(segment.start / 60)}:
                      {String(Math.floor(segment.start % 60)).padStart(2, "0")}
                    </span>
                    {segment.speaker && (
                      <span className="mr-2 font-medium text-moss-700">
                        {segment.speaker}
                      </span>
                    )}
                    {segment.text}
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-ink-700">
              {mathom.transcript}
            </p>
          )
        ) : (
          <p className="mt-3 text-sm text-ink-500">
            {t("detail.transcriptPending")}
          </p>
        )}
      </section>

      <section className="card">
        <div className="flex items-center justify-between">
          <h3 className="font-display text-lg">{t("detail.askTitle")}</h3>
          {mathom.chat_messages.length > 0 && (
            <button
              onClick={() => api.clearChat(mathom.id).then(refresh)}
              className="text-sm text-ink-500 hover:text-red-700"
            >
              {t("detail.clearConversation")}
            </button>
          )}
        </div>
        <div className="mt-3 max-h-96 space-y-3 overflow-y-auto">
          {mathom.chat_messages.map((message: ChatMessage) => (
            <div
              key={message.id}
              className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm ${
                message.role === "user"
                  ? "ml-auto bg-hearth-100 text-ink-900"
                  : "bg-parchment-100 text-ink-900"
              }`}
            >
              {message.content}
            </div>
          ))}
          {streamingChat && (
            <div className="max-w-[85%] rounded-2xl bg-parchment-100 px-4 py-2 text-sm whitespace-pre-wrap">
              {streamingChat}
            </div>
          )}
          {pendingChat && (
            <>
              <div className="ml-auto max-w-[85%] rounded-2xl bg-hearth-100 px-4 py-2 text-sm text-ink-900 opacity-70">
                {pendingChat}
              </div>
              <div
                className="max-w-[85%] rounded-2xl bg-parchment-100 px-4 py-2 text-sm text-ink-400"
                aria-live="polite"
              >
                {t("detail.thinking")}
              </div>
            </>
          )}
          <div ref={chatEndRef} />
        </div>
        <form onSubmit={sendChat} className="mt-3 flex gap-2">
          <input
            value={chatInput}
            onChange={(event) => setChatInput(event.target.value)}
            placeholder={
              mathom.transcript
                ? t("detail.chatReady")
                : t("detail.chatWaiting")
            }
            disabled={!mathom.transcript || chatBusy}
            className="input"
          />
          <button
            type="submit"
            disabled={!mathom.transcript || chatBusy}
            className="btn-primary disabled:opacity-50"
          >
            {chatBusy ? "…" : t("detail.ask")}
          </button>
        </form>
      </section>
    </div>
  );
}
