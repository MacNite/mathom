import { useEffect, useId, useRef, useState } from 'react';

import { api } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { detectSourceApp } from '../lib/sourceApp';
import { useToast } from '../lib/toast';
import type { PromptTemplate, Speaker } from '../lib/types';

interface Props {
  open: boolean;
  onClose: () => void;
  onUploaded: () => void;
  // A file handed in from the Android Share Sheet. When present it is used for
  // the upload and the file picker is hidden (a File input cannot be set
  // programmatically for security reasons).
  sharedFile?: File | null;
  sharedTitle?: string;
  sharedText?: string;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

const DOCUMENT_EXTENSIONS = ['.txt', '.md', '.pdf', '.docx'];

function isDocument(file: File): boolean {
  return file.type === 'application/pdf'
    || file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    || file.type === 'text/plain'
    || file.type === 'text/markdown'
    || DOCUMENT_EXTENSIONS.some((extension) => file.name.toLowerCase().endsWith(extension));
}

export default function UploadDialog({
  open,
  onClose,
  onUploaded,
  sharedFile = null,
  sharedTitle = '',
  sharedText = '',
}: Props) {
  const { lang, t } = useI18n();
  const toast = useToast();
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [title, setTitle] = useState('');
  const [speaker, setSpeaker] = useState('');
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [speakerPickerOpen, setSpeakerPickerOpen] = useState(false);
  const [templateSlug, setTemplateSlug] = useState('general-summary');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [source, setSource] = useState<'media' | 'text' | 'document'>('media');
  const [text, setText] = useState('');
  const [analyzeVisuals, setAnalyzeVisuals] = useState(false);
  const [videoSelected, setVideoSelected] = useState(false);
  const [pickedName, setPickedName] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLFormElement>(null);
  const titleId = useId();
  const descId = useId();
  const speakerLabelId = useId();
  const speakerListId = useId();

  useEffect(() => {
    if (open) {
      setError('');
      api
        .listTemplates(lang)
        .then((loaded) => {
          setTemplates(loaded);
          // The chosen style must be one the server actually offers. The initial
          // 'general-summary' guess (or a stale earlier choice) is reconciled
          // against the loaded list so a selection is never silently dropped in
          // favour of the default when the requested style isn't available.
          setTemplateSlug((current) =>
            loaded.some((template) => template.slug === current)
              ? current
              : (loaded[0]?.slug ?? current),
          );
        })
        .catch(() => {
          // Surface the failure rather than leaving an empty picker that would
          // quietly upload with the default template.
          setTemplates([]);
          setError(t('upload.templatesFailed'));
        });
      // Some embedded/test API adapters may not yet expose speaker discovery;
      // free-form entry remains available in that case.
      api.listSpeakers?.().then(setSpeakers).catch(() => setSpeakers([]));
      setTitle(sharedTitle);
      setSpeaker('');
      setSpeakerPickerOpen(false);
      setPickedName('');
      if (sharedText) {
        setSource('text');
        setText(sharedText);
      } else if (sharedFile) {
        setSource(isDocument(sharedFile) ? 'document' : 'media');
      }
    }
  }, [lang, open, sharedFile, sharedText, sharedTitle, t]);

  // Accessible-dialog behaviour: trap focus, restore it on close, close on
  // Escape, and move focus into the dialog when it opens.
  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const node = dialogRef.current;
    node?.querySelector<HTMLElement>(FOCUSABLE)?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !node) return;
      const focusable = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const file = sharedFile ?? fileRef.current?.files?.[0];
    if (source !== 'text' && !file) {
      setError(t('upload.chooseFileFirst'));
      return;
    }
    // Without a loaded template the backend would fall back to the default
    // style, so block the upload and tell the user rather than misapplying it.
    if (templates.length === 0 || !templates.some((template) => template.slug === templateSlug)) {
      setError(t('upload.templatesFailed'));
      return;
    }
    setBusy(true);
    setError('');
    try {
      if (source === 'text') await api.createTextMathom(text, title, templateSlug, lang, speaker);
      else if (source === 'document' && file) await api.uploadDocument(file, title, templateSlug, lang, speaker);
      else if (file) await api.uploadMathom(file, title, templateSlug, lang, analyzeVisuals, speaker);
      setTitle('');
      setSpeaker('');
      if (fileRef.current) fileRef.current.value = '';
      toast.success(t('upload.success'));
      onUploaded();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('upload.uploadFailed'));
    } finally {
      setBusy(false);
    }
  };

  // Best-effort hint at the app the recording came from, inferred from the
  // filename (the platform never tells us directly). Null hides the badge.
  const sourceApp = detectSourceApp(sharedFile?.name ?? pickedName);
  const matchingSpeakers = speakers.filter((entry) =>
    entry.name.toLocaleLowerCase().includes(speaker.trim().toLocaleLowerCase()),
  );

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-ink-900/40 p-4"
      onMouseDown={(event) => {
        // Close only when the backdrop itself is pressed, not the dialog.
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <form
        ref={dialogRef}
        onSubmit={submit}
        className="card w-full max-w-md bg-parchment-50"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
      >
        <h2 id={titleId} className="font-display text-xl text-ink-900">
          {t('upload.title')}
        </h2>
        <p id={descId} className="mt-1 text-sm text-ink-500">
          {sharedFile ? t('upload.sharedSubtitle') : t('upload.subtitle')}
        </p>
        {!sharedFile && (
          <fieldset className="mt-3 flex gap-3 text-sm text-ink-700">
            <legend>{t('upload.source')}</legend>
            {(['media', 'text', 'document'] as const).map((kind) => (
              <label key={kind}>
                <input
                  type="radio"
                  checked={source === kind}
                  onChange={() => setSource(kind)}
                />{' '}
                {t(`upload.source.${kind}`)}
              </label>
            ))}
          </fieldset>
        )}
        {sharedFile ? (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-moss-200 bg-moss-200/40 px-3 py-2 text-sm text-ink-700">
            <span aria-hidden>🎧</span>
            <span className="truncate">{sharedFile.name}</span>
            {sourceApp && (
              <span className="ml-auto shrink-0 rounded-full bg-parchment-200 px-2 py-0.5 text-xs text-ink-700">
                {t('upload.sourceApp')}: {sourceApp}
              </span>
            )}
          </div>
        ) : source !== 'text' ? (
          <label className="mt-4 block text-sm text-ink-700">
            {source === 'document' ? t('upload.documentFile') : t('upload.audioFile')}
            <input
              ref={fileRef}
              type="file"
              accept={
                source === 'document'
                  ? '.txt,.md,.pdf,.docx'
                  : 'audio/*,video/mp4,video/webm,.m4a,.opus'
              }
              className="input mt-1"
              onChange={(event) => {
                const picked = event.currentTarget.files?.[0];
                setVideoSelected(Boolean(picked?.type.startsWith('video/')));
                setPickedName(picked?.name ?? '');
              }}
            />
          </label>
        ) : (
          <label className="mt-4 block text-sm text-ink-700">
            {t('upload.text')}
            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              className="input mt-1 min-h-40"
              maxLength={500000}
            />
          </label>
        )}
        {source === 'media' && (videoSelected || sharedFile?.type.startsWith('video/')) && (
          <label className="mt-3 block rounded-xl bg-parchment-100 p-3 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={analyzeVisuals}
              onChange={(event) => setAnalyzeVisuals(event.target.checked)}
            />{' '}
            {t('upload.analyzeVisuals')}
            <span className="mt-1 block text-xs text-ink-500">
              {t('upload.analyzeVisualsHelp')}
            </span>
          </label>
        )}
        <label className="mt-3 block text-sm text-ink-700">
          {t('upload.titleLabel')} <span className="text-ink-400">{t('upload.optional')}</span>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder={t('upload.titlePlaceholder')}
            className="input mt-1"
          />
        </label>
        <div className="relative mt-3 text-sm text-ink-700">
          <label id={speakerLabelId} htmlFor={`${speakerListId}-input`}>
            {t('upload.speakerLabel')} <span className="text-ink-400">{t('upload.optional')}</span>
          </label>
          <div className="relative mt-1">
            <input
              id={`${speakerListId}-input`}
              value={speaker}
              onChange={(event) => {
                setSpeaker(event.target.value);
                setSpeakerPickerOpen(true);
              }}
              onFocus={() => setSpeakerPickerOpen(true)}
              onBlur={() => setSpeakerPickerOpen(false)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') setSpeakerPickerOpen(false);
                if (event.key === 'ArrowDown') setSpeakerPickerOpen(true);
              }}
              placeholder={t('upload.speakerPlaceholder')}
              className="input pr-10"
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={speakerPickerOpen}
              aria-controls={speakerListId}
            />
            <button
              type="button"
              className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-ink-500"
              aria-label={t('upload.showSpeakers')}
              aria-expanded={speakerPickerOpen}
              tabIndex={-1}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => setSpeakerPickerOpen((current) => !current)}
            >
              <span aria-hidden className={`transition-transform ${speakerPickerOpen ? 'rotate-180' : ''}`}>⌄</span>
            </button>
          </div>
          {speakerPickerOpen && (
            <div
              id={speakerListId}
              role="listbox"
              aria-labelledby={speakerLabelId}
              className="absolute z-10 mt-1 max-h-48 w-full overflow-y-auto rounded border border-parchment-300 bg-parchment-50 py-1 shadow-lg"
            >
              {matchingSpeakers.length > 0 ? matchingSpeakers.map((entry) => (
                <button
                  key={entry.name}
                  type="button"
                  role="option"
                  aria-selected={speaker === entry.name}
                  className="block w-full px-3 py-2 text-left hover:bg-parchment-100 focus:bg-parchment-100"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => {
                    setSpeaker(entry.name);
                    setSpeakerPickerOpen(false);
                  }}
                >
                  {entry.name}
                </button>
              )) : (
                <p className="px-3 py-2 text-ink-500">{t('upload.noSpeakers')}</p>
              )}
            </div>
          )}
        </div>
        <label className="mt-3 block text-sm text-ink-700">
          {t('upload.summaryStyle')}
          <select
            value={templateSlug}
            onChange={(event) => setTemplateSlug(event.target.value)}
            className="input mt-1"
          >
            {templates.map((template) => (
              <option key={template.slug} value={template.slug}>
                {template.name}
              </option>
            ))}
          </select>
        </label>
        {error && (
          <p className="mt-3 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">
            {t('upload.cancel')}
          </button>
          <button type="submit" disabled={busy} className="btn-primary disabled:opacity-50">
            {busy ? t('upload.uploading') : t('upload.upload')}
          </button>
        </div>
      </form>
    </div>
  );
}
