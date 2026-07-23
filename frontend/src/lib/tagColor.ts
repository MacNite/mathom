// Tag colour tokens and their Tailwind classes. The token list mirrors the
// backend (app/services/tags.py TAG_COLORS); the two must stay in agreement so
// every stored colour renders. Class strings are written out in full — Tailwind
// only keeps classes it finds literally in the source, so no `bg-tag-${token}`.

export const TAG_COLORS = [
  'moss',
  'hearth',
  'ochre',
  'clay',
  'rose',
  'plum',
  'indigo',
  'teal',
  'stone',
] as const;

export type TagColor = (typeof TAG_COLORS)[number];

export const DEFAULT_TAG_COLOR: TagColor = 'moss';

// Solid pill: a muted colour ink under parchment lettering.
const CHIP: Record<TagColor, string> = {
  moss: 'bg-tag-moss text-parchment-50',
  hearth: 'bg-tag-hearth text-parchment-50',
  ochre: 'bg-tag-ochre text-parchment-50',
  clay: 'bg-tag-clay text-parchment-50',
  rose: 'bg-tag-rose text-parchment-50',
  plum: 'bg-tag-plum text-parchment-50',
  indigo: 'bg-tag-indigo text-parchment-50',
  teal: 'bg-tag-teal text-parchment-50',
  stone: 'bg-tag-stone text-parchment-50',
};

// Bare fill, for colour-picker swatches.
const SWATCH: Record<TagColor, string> = {
  moss: 'bg-tag-moss',
  hearth: 'bg-tag-hearth',
  ochre: 'bg-tag-ochre',
  clay: 'bg-tag-clay',
  rose: 'bg-tag-rose',
  plum: 'bg-tag-plum',
  indigo: 'bg-tag-indigo',
  teal: 'bg-tag-teal',
  stone: 'bg-tag-stone',
};

function normalise(color: string | undefined): TagColor {
  return color && (TAG_COLORS as readonly string[]).includes(color)
    ? (color as TagColor)
    : DEFAULT_TAG_COLOR;
}

export function chipClasses(color?: string): string {
  return CHIP[normalise(color)];
}

export function swatchClasses(color?: string): string {
  return SWATCH[normalise(color)];
}
