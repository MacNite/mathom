import { useEffect, useState } from 'react';

import { api } from '../lib/api';
import type { TimelineBucket } from '../lib/types';

function monthLabel(month: string): string {
  const [year, monthNumber] = month.split('-').map(Number);
  return new Date(year, monthNumber - 1, 1).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
  });
}

export default function Timeline() {
  const [buckets, setBuckets] = useState<TimelineBucket[]>([]);

  useEffect(() => {
    api.timeline().then(setBuckets).catch(() => setBuckets([]));
  }, []);

  const max = Math.max(1, ...buckets.map((bucket) => bucket.count));

  return (
    <div>
      <h2 className="font-display text-2xl text-ink-900">Timeline</h2>
      <p className="mt-1 text-sm text-ink-500">Your memory house, month by month.</p>
      {buckets.length === 0 ? (
        <p className="card mt-6 text-sm text-ink-500">Nothing recorded yet.</p>
      ) : (
        <ul className="mt-6 space-y-2">
          {buckets.map((bucket) => (
            <li key={bucket.month} className="flex items-center gap-3">
              <span className="w-40 shrink-0 text-sm text-ink-700">{monthLabel(bucket.month)}</span>
              <div className="h-6 flex-1 rounded-full bg-parchment-100">
                <div
                  className="flex h-6 items-center rounded-full bg-hearth-400 px-2 text-xs text-ink-900"
                  style={{ width: `${Math.max(8, (bucket.count / max) * 100)}%` }}
                >
                  {bucket.count}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
