import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

import { I18nProvider } from '../lib/i18n';
import { ToastProvider } from '../lib/toast';
import type { PromptTemplate } from '../lib/types';
import UploadDialog from './UploadDialog';

const { api } = vi.hoisted(() => ({
  api: {
    listTemplates: vi.fn(),
    listSpeakers: vi.fn(),
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
    api.listSpeakers.mockResolvedValue([]);
  });

  it('sends the style the user selected', async () => {
    api.listTemplates.mockResolvedValue(templates);
    api.uploadMathom.mockResolvedValue({});
    renderDialog();
    await screen.findByRole('option', { name: 'TL;DR' });

    pickFile();
    fireEvent.change(screen.getByLabelText(/summary style/i), { target: { value: 'tldr' } });
    fireEvent.click(screen.getByRole('button', { name: /^upload$/i }));

    await waitFor(() => expect(api.uploadMathom).toHaveBeenCalled());
    expect(api.uploadMathom.mock.calls[0][2]).toBe('tldr');
  });

  it('sends the speaker the user entered', async () => {
    api.listTemplates.mockResolvedValue(templates);
    api.uploadMathom.mockResolvedValue({});
    renderDialog();
    await screen.findByRole('option', { name: 'TL;DR' });

    pickFile();
    fireEvent.change(screen.getByRole('combobox', { name: /speaker/i }), { target: { value: 'Max' } });
    fireEvent.click(screen.getByRole('button', { name: /^upload$/i }));

    await waitFor(() => expect(api.uploadMathom).toHaveBeenCalled());
    // speaker is the final positional argument to uploadMathom.
    expect(api.uploadMathom.mock.calls[0][5]).toBe('Max');
  });

  it('shows all known speakers and filters them while typing', async () => {
    api.listTemplates.mockResolvedValue(templates);
    api.listSpeakers.mockResolvedValue([
      { name: 'Max', mathom_count: 2 },
      { name: 'Mama and me', mathom_count: 1 },
      { name: 'Alice', mathom_count: 3 },
    ]);
    renderDialog();

    const picker = screen.getByRole('combobox', { name: /^speaker/i });
    fireEvent.focus(picker);
    expect(await screen.findByRole('option', { name: 'Max' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Alice' })).toBeInTheDocument();

    fireEvent.change(picker, { target: { value: 'ma' } });
    expect(screen.getByRole('option', { name: 'Max' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Mama and me' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Alice' })).not.toBeInTheDocument();

    fireEvent.mouseDown(screen.getByRole('option', { name: 'Mama and me' }));
    fireEvent.click(screen.getByRole('option', { name: 'Mama and me' }));
    expect(picker).toHaveValue('Mama and me');
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
