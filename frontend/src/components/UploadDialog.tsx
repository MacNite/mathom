import { useEffect, useId, useRef, useState } from 'react';

import { api } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { useToast } from '../lib/toast';
import type { PromptTemplate } from '../lib/types';

interface Props {
  open: boolean;
  onClose: () => void;
  onUploaded: () => void;
  // A file handed in from the Android Share Sheet. When present it is used for
  // the upload and the file picker is hidden (a File input cannot be set
  // programmatically for security reasons).
  sharedFile?: File | null;
  sharedTitle?: string;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function UploadDialog({
  open,
  onClose,
  onUploaded,
  sharedFile = null,
  sharedTitle = '',
}: Props) {
  const { lang, t } = useI18n();
  const toast = useToast();
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [title, setTitle] = useState('');
  const [templateSlug, setTemplateSlug] = useState('general-summary');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLFormElement>(null);
  const titleId = useId();
  const descId = useId();

  useEffect(() => {
    if (open) {
      api.listTemplates(lang).then(setTemplates).catch(() => setTemplates([]));
      setError('');
      setTitle(sharedTitle);
    }
  }, [lang, open, sharedTitle]);

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
    if (!file) {
      setError(t('upload.chooseFileFirst'));
      return;
    }
    setBusy(true);
    setError('');
    try {
      await api.uploadMathom(file, title, templateSlug, lang);
      setTitle('');
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
        {sharedFile ? (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-moss-200 bg-moss-200/40 px-3 py-2 text-sm text-ink-700">
            <span aria-hidden>🎧</span>
            <span className="truncate">{sharedFile.name}</span>
          </div>
        ) : (
          <label className="mt-4 block text-sm text-ink-700">
            {t('upload.audioFile')}
            <input
              ref={fileRef}
              type="file"
              accept="audio/*,video/mp4,.m4a,.opus"
              className="input mt-1"
            />
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
