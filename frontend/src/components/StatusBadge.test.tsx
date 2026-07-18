import { render, screen } from '@testing-library/react';

import StatusBadge from './StatusBadge';

describe('StatusBadge', () => {
  it('shows a friendly label for each status', () => {
    render(<StatusBadge status="ready" />);
    expect(screen.getByText('Ready')).toBeInTheDocument();
  });

  it('marks in-flight states', () => {
    render(<StatusBadge status="transcribing" />);
    expect(screen.getByText('Transcribing…')).toBeInTheDocument();
  });
});
