import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

import { I18nProvider } from '../lib/i18n';
import { ToastProvider } from '../lib/toast';
import type { MathomListItem, Tag } from '../lib/types';
import Library from './Library';

const { api } = vi.hoisted(() => ({
  api: {
    listMathoms: vi.fn(),
    listTags: vi.fn(),
    search: vi.fn(),
    deleteMathom: vi.fn(),
  },
}));

vi.mock('../lib/api', () => ({ api }));

const recording: MathomListItem = {
  id: 1,
  title: 'Voice note from Max',
  status: 'ready',
  duration_seconds: 30,
  language: 'de',
  favorite: false,
  archived: false,
  created_at: '2026-07-01T10:00:00Z',
  tags: [],
};

const tags: Tag[] = [
  { id: 1, name: 'house', color: 'clay', kind: 'manual', mathom_count: 3 },
  { id: 2, name: 'whatsapp', color: 'stone', kind: 'source', mathom_count: 2 },
];

function renderLibrary() {
  return render(
    <MemoryRouter>
      <I18nProvider>
        <ToastProvider>
          <Library />
        </ToastProvider>
      </I18nProvider>
    </MemoryRouter>,
  );
}

describe('Library tag filter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listMathoms.mockResolvedValue([recording]);
    api.listTags.mockResolvedValue(tags);
  });

  it('offers a chip per tag — including folded-in source tags — and filters by it', async () => {
    renderLibrary();

    // Source origins now appear in the shared tag vocabulary, not a separate row.
    const house = await screen.findByRole('button', { name: 'house' });
    await screen.findByRole('button', { name: 'whatsapp' });

    fireEvent.click(house);

    await waitFor(() =>
      expect(api.listMathoms).toHaveBeenLastCalledWith(
        expect.objectContaining({ tags: ['house'] }),
      ),
    );
    expect(house).toHaveAttribute('aria-pressed', 'true');
  });

  it('reveals an any/all toggle once two tags are selected', async () => {
    renderLibrary();

    fireEvent.click(await screen.findByRole('button', { name: 'house' }));
    fireEvent.click(await screen.findByRole('button', { name: 'whatsapp' }));

    const toggle = await screen.findByRole('button', { name: 'Any tag' });
    fireEvent.click(toggle);

    await waitFor(() =>
      expect(api.listMathoms).toHaveBeenLastCalledWith(
        expect.objectContaining({ tags: ['house', 'whatsapp'], match: 'all' }),
      ),
    );
  });
});
