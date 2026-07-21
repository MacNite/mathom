import { useI18n } from '../lib/i18n';
import type { MathomStatus } from '../lib/types';

const STYLES: Record<MathomStatus, string> = {
  pending: 'bg-parchment-200 text-ink-700',
  transcribing: 'bg-hearth-100 text-hearth-600',
  analyzing_visuals: 'bg-hearth-100 text-hearth-600',
  summarizing: 'bg-hearth-100 text-hearth-600',
  ready: 'bg-moss-700 text-parchment-50',
  error: 'bg-red-100 text-red-700',
};

export default function StatusBadge({ status }: { status: MathomStatus }) {
  const { t } = useI18n();
  return (
    <span
      className={`inline-flex whitespace-nowrap rounded-sm px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${STYLES[status]}`}
    >
      {t(`status.${status}`)}
    </span>
  );
}
