import { Link } from 'react-router-dom';

import { formatDate, formatDuration } from '../lib/format';
import { useI18n } from '../lib/i18n';
import type { MathomListItem } from '../lib/types';
import StatusBadge from './StatusBadge';

export default function MathomCard({ mathom }: { mathom: MathomListItem }) {
  const { lang, t } = useI18n();
  return (
    <Link
      to={`/mathoms/${mathom.id}`}
      className="card block rounded-doorway hover:border-hearth-400"
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-display text-lg text-ink-900">
          {mathom.favorite && (
            <span aria-label={t('card.favorite')} className="mr-1">
              ★
            </span>
          )}
          {mathom.title}
        </h3>
        <StatusBadge status={mathom.status} />
      </div>
      <p className="mt-1 text-xs text-ink-500">
        {formatDate(mathom.created_at, lang)}
        {mathom.duration_seconds != null && ` · ${formatDuration(mathom.duration_seconds, t)}`}
        {mathom.language && ` · ${mathom.language}`}
      </p>
      {mathom.tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {mathom.tags.map((tag) => (
            <span key={tag.id} className="chip">
              {tag.name}
            </span>
          ))}
        </div>
      )}
    </Link>
  );
}
