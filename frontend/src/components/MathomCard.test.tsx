import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import type { MathomListItem } from '../lib/types';
import MathomCard, { formatDuration } from './MathomCard';

const mathom: MathomListItem = {
  id: 7,
  title: 'Call with the carpenter',
  status: 'ready',
  duration_seconds: 95,
  language: 'en',
  favorite: true,
  archived: false,
  created_at: '2026-07-01T10:00:00Z',
  tags: [{ id: 1, name: 'house' }],
};

describe('formatDuration', () => {
  it('formats minutes and seconds', () => {
    expect(formatDuration(95)).toBe('1 min 35 s');
    expect(formatDuration(42)).toBe('42 s');
    expect(formatDuration(null)).toBe('');
  });
});

describe('MathomCard', () => {
  it('renders title, tags, and links to the detail page', () => {
    render(
      <MemoryRouter>
        <MathomCard mathom={mathom} />
      </MemoryRouter>,
    );
    expect(screen.getByText('Call with the carpenter')).toBeInTheDocument();
    expect(screen.getByText('house')).toBeInTheDocument();
    expect(screen.getByRole('link')).toHaveAttribute('href', '/mathoms/7');
  });
});
