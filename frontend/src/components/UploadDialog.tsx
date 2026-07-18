import { useEffect, useRef, useState } from 'react';

import { api } from '../lib/api';
import type { PromptTemplate } from '../lib/types';

interface Props {
  open: boolean;
  onClose: () => void;
  onUploaded: () => void;
}

export default function UploadDialog({ open, onClose, onUploaded }: Props) {
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [title, setTitle] = useState('');
  const [templateSlug, setTemplateSlug] = useState('general-summary');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      api.listTemplates().then(setTemplates).catch(() => setTemplates([]));
      setError('');
    }
  }, [open]);

  if (!open) return null;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError('Choose an audio file first.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await api.uploadMathom(file, title, templateSlug);
      setTitle('');
      if (fileRef.current) fileRef.current.value = '';
      onUploaded();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink-900/40 p-4">
      <form onSubmit={submit} className="card w-full max-w-md bg-parchment-50">
        <h2 className="font-display text-xl text-ink-900">Bring a recording home</h2>
        <p className="mt-1 text-sm text-ink-500">
          It will be transcribed and summarized, then shelved in your Mathom-house.
        </p>
        <label className="mt-4 block text-sm text-ink-700">
          Audio file
          <input
            ref={fileRef}
            type="file"
            accept="audio/*,video/mp4,.m4a,.opus"
            className="input mt-1"
          />
        </label>
        <label className="mt-3 block text-sm text-ink-700">
          Title <span className="text-ink-400">(optional)</span>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="e.g. Call with the roofing company"
            className="input mt-1"
          />
        </label>
        <label className="mt-3 block text-sm text-ink-700">
          Summary style
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
        {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">
            Cancel
          </button>
          <button type="submit" disabled={busy} className="btn-primary disabled:opacity-50">
            {busy ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </form>
    </div>
  );
}
