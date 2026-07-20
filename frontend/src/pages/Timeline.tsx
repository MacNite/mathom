import { useEffect, useState } from 'react';

import { api } from '../lib/api';
import { formatMonth } from '../lib/format';
import { useI18n } from '../lib/i18n';
import type { TimelineBucket } from '../lib/types';

export default function Timeline() {
  const { lang, t } = useI18n();
  const [buckets, setBuckets] = useState<TimelineBucket[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setLoadError(false);
    api
      .timeline()
      .then(setBuckets)
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  }, []);

  const max = Math.max(1, ...buckets.map((bucket) => bucket.count));

  return (
    <div>
      <h2 className="font-display text-2xl text-ink-900">{t('timeline.title')}</h2>
      <p className="mt-1 text-sm text-ink-500">{t('timeline.subtitle')}</p>
      {loading ? (
        <p className="card mt-6 text-sm text-ink-500">{t('common.loading')}</p>
      ) : loadError ? (
        <p className="card mt-6 text-sm text-red-700">{t('common.loadError')}</p>
      ) : buckets.length === 0 ? (
        <p className="card mt-6 text-sm text-ink-500">{t('timeline.empty')}</p>
      ) : (
        <ul className="mt-6 space-y-2">
          {buckets.map((bucket) => (
            <li key={bucket.month} className="flex items-center gap-3">
              <span className="w-40 shrink-0 text-sm text-ink-700">
                {formatMonth(bucket.month, lang)}
              </span>
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
