// Locale-aware formatting helpers. Dates and durations follow the app's chosen
// UI language rather than the browser locale, so a German UI shows German dates.
import type { Lang } from './i18n';

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export function formatDate(iso: string, lang: Lang): string {
  return new Date(iso).toLocaleDateString(lang, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatDateTime(iso: string, lang: Lang): string {
  return new Date(iso).toLocaleString(lang);
}

export function formatMonth(month: string, lang: Lang): string {
  const [year, monthNumber] = month.split('-').map(Number);
  return new Date(year, monthNumber - 1, 1).toLocaleDateString(lang, {
    year: 'numeric',
    month: 'long',
  });
}

export function formatDuration(seconds: number | null, t: Translate): string {
  if (seconds == null) return '';
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return minutes > 0
    ? t('duration.minSec', { m: minutes, s: rest })
    : t('duration.sec', { s: rest });
}
