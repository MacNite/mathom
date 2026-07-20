import { act, render, screen } from '@testing-library/react';

import { ToastProvider, useToast } from './toast';

function Trigger() {
  const toast = useToast();
  return (
    <button onClick={() => toast.error('Something broke')}>raise</button>
  );
}

describe('ToastProvider', () => {
  it('shows a toast when one is raised and auto-dismisses it', () => {
    vi.useFakeTimers();
    try {
      render(
        <ToastProvider>
          <Trigger />
        </ToastProvider>,
      );

      act(() => {
        screen.getByText('raise').click();
      });
      expect(screen.getByRole('alert')).toHaveTextContent('Something broke');

      // Errors linger for 6s, then clear themselves.
      act(() => {
        vi.advanceTimersByTime(6000);
      });
      expect(screen.queryByText('Something broke')).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
