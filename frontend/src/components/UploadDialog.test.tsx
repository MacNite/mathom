import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

import { I18nProvider } from '../lib/i18n';
import { ToastProvider } from '../lib/toast';
import type { PromptTemplate } from '../lib/types';
import UploadDialog from './UploadDialog';

const { api } = vi.hoisted(() => ({
  api: {
    listTemplates: vi.fn(),
    uploadMathom: vi.fn(),
    uploadDocument: vi.fn(),
    createTextMathom: vi.fn(),
  },
}));

vi.mock('../lib/api', () => ({ api }));

// The server returns built-in templates ordered by name.
const templates: PromptTemplate[] = [
  { id: 1, slug: 'action-items', name: 'Action Items', description: '', prompt: '{transcript}', is_builtin: true, updated_at: '' },
  { id: 2, slug: 'general-summary', name: 'General Summary', description: '', prompt: '{transcript}', is_builtin: true, updated_at: '' },
  { id: 3, slug: 'tldr', name: 'TL;DR', description: '', prompt: '{transcript}', is_builtin: true, updated_at: '' },
];

function renderDialog() {
  return render(
    <I18nProvider>
      <ToastProvider>
        <UploadDialog open onClose={() => {}} onUploaded={() => {}} />
      </ToastProvider>
    </I18nProvider>,
  );
}

function pickFile() {
  const file = new File(['abc'], 'note.mp3', { type: 'audio/mpeg' });
  fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, {
    target: { files: [file] },
  });
}

describe('UploadDialog summary style', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends the style the user selected', async () => {
    api.listTemplates.mockResolvedValue(templates);
    api.uploadMathom.mockResolvedValue({});
    renderDialog();
    await screen.findByRole('option', { name: 'TL;DR' });

    pickFile();
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'tldr' } });
    fireEvent.click(screen.getByRole('button', { name: /^upload$/i }));

    await waitFor(() => expect(api.uploadMathom).toHaveBeenCalled());
    expect(api.uploadMathom.mock.calls[0][2]).toBe('tldr');
  });

  it('does not silently upload with the default when styles failed to load', async () => {
    api.listTemplates.mockRejectedValue(new Error('network down'));
    api.uploadMathom.mockResolvedValue({});
    renderDialog();

    await waitFor(() => expect(api.listTemplates).toHaveBeenCalled());
    pickFile();
    fireEvent.click(screen.getByRole('button', { name: /^upload$/i }));

    // The upload is blocked and the user is told, rather than the backend
    // quietly applying 'general-summary'.
    await screen.findByRole('alert');
    expect(api.uploadMathom).not.toHaveBeenCalled();
  });

  it('defaults to the first offered style when general-summary is absent', async () => {
    const custom: PromptTemplate[] = [
      { id: 9, slug: 'briefing', name: 'Briefing', description: '', prompt: '{transcript}', is_builtin: false, updated_at: '' },
      { id: 3, slug: 'tldr', name: 'TL;DR', description: '', prompt: '{transcript}', is_builtin: true, updated_at: '' },
    ];
    api.listTemplates.mockResolvedValue(custom);
    api.uploadMathom.mockResolvedValue({});
    renderDialog();
    await screen.findByRole('option', { name: 'Briefing' });

    pickFile();
    fireEvent.click(screen.getByRole('button', { name: /^upload$/i }));

    await waitFor(() => expect(api.uploadMathom).toHaveBeenCalled());
    // 'general-summary' isn't offered, so the picker resolved to a real option
    // instead of leaving the invalid default in place.
    expect(api.uploadMathom.mock.calls[0][2]).toBe('briefing');
  });
});
