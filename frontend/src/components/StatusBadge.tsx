import type { MathomStatus } from '../lib/types';

const STYLES: Record<MathomStatus, string> = {
  pending: 'bg-parchment-200 text-ink-700',
  transcribing: 'bg-hearth-100 text-hearth-600',
  summarizing: 'bg-hearth-100 text-hearth-600',
  ready: 'bg-moss-200 text-moss-700',
  error: 'bg-red-100 text-red-700',
};

const LABELS: Record<MathomStatus, string> = {
  pending: 'Waiting',
  transcribing: 'Transcribing…',
  summarizing: 'Summarizing…',
  ready: 'Ready',
  error: 'Error',
};

export default function StatusBadge({ status }: { status: MathomStatus }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLES[status]}`}>
      {LABELS[status]}
    </span>
  );
}
