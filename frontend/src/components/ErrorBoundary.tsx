import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

import { useI18n } from '../lib/i18n';

function Fallback({ onReset }: { onReset: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="card max-w-md text-center">
        <div className="text-4xl" aria-hidden>
          🕯️
        </div>
        <h1 className="mt-2 font-display text-xl text-ink-900">{t('error.boundaryTitle')}</h1>
        <p className="mt-1 text-sm text-ink-500">{t('error.boundaryBody')}</p>
        <button onClick={onReset} className="btn-primary mt-4">
          {t('error.boundaryRetry')}
        </button>
      </div>
    </div>
  );
}

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

// A single top-level boundary so an uncaught render error shows a calm,
// on-brand recovery card instead of a blank white screen.
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Local-first: log to the console only, never phone home.
    console.error('Unhandled render error', error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false });
  };

  render() {
    if (this.state.hasError) {
      return <Fallback onReset={this.handleReset} />;
    }
    return this.props.children;
  }
}
