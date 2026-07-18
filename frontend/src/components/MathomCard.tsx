import { Link } from 'react-router-dom';

import type { MathomListItem } from '../lib/types';
import StatusBadge from './StatusBadge';

export function formatDuration(seconds: number | null): string {
  if (seconds == null) return '';
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return minutes > 0 ? `${minutes} min ${rest} s` : `${rest} s`;
}

export default function MathomCard({ mathom }: { mathom: MathomListItem }) {
  const date = new Date(mathom.created_at).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
  return (
    <Link to={`/mathoms/${mathom.id}`} className="card block hover:border-hearth-400">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-display text-lg text-ink-900">
          {mathom.favorite && (
            <span aria-label="favorite" className="mr-1">
              ★
            </span>
          )}
          {mathom.title}
        </h3>
        <StatusBadge status={mathom.status} />
      </div>
      <p className="mt-1 text-xs text-ink-500">
        {date}
        {mathom.duration_seconds != null && ` · ${formatDuration(mathom.duration_seconds)}`}
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
