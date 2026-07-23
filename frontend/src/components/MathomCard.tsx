import { Link } from 'react-router-dom';

import { formatDate, formatDuration } from '../lib/format';
import { useI18n } from '../lib/i18n';
import { chipClasses } from '../lib/tagColor';
import type { MathomListItem } from '../lib/types';
import StatusBadge from './StatusBadge';

interface MathomCardProps {
  mathom: MathomListItem;
  onDelete?: (mathom: MathomListItem) => void;
  deleting?: boolean;
}

export default function MathomCard({ mathom, onDelete, deleting = false }: MathomCardProps) {
  const { lang, t } = useI18n();
  return (
    <div className="card relative transition-colors hover:border-hearth-400">
      <Link to={`/mathoms/${mathom.id}`} className="block">
        <div className="flex items-start justify-between gap-3 pr-10">
          <h3 className="font-display text-lg text-ink-900">
            {mathom.favorite && (
              <span aria-label={t('card.favorite')} className="mr-1 text-hearth-500">
                ★
              </span>
            )}
            {mathom.title}
          </h3>
          <StatusBadge status={mathom.status} />
        </div>
        <p className="mt-1.5 text-[11px] uppercase tracking-wide text-ink-500 [font-variant-numeric:tabular-nums]">
          {formatDate(mathom.created_at, lang)}
          {mathom.duration_seconds != null && ` · ${formatDuration(mathom.duration_seconds, t)}`}
          {mathom.language && ` · ${mathom.language}`}
        </p>
        {mathom.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {mathom.tags.map((tag) => (
              <span
                key={tag.id}
                className={`inline-flex items-center rounded-sm px-2 py-0.5 text-[11px] uppercase tracking-wide ${chipClasses(tag.color)}`}
              >
                {tag.name}
              </span>
            ))}
          </div>
        )}
      </Link>
      {onDelete && (
        <button
          type="button"
          onClick={() => onDelete(mathom)}
          disabled={deleting}
          aria-label={t('library.deleteMathom', { title: mathom.title })}
          className="absolute right-3 top-3 rounded p-0.5 text-ink-500 hover:bg-red-100 hover:text-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-hearth-500 disabled:cursor-wait disabled:opacity-50"
        >
          <span aria-hidden="true">×</span>
        </button>
      )}
    </div>
  );
}
