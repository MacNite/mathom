/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Cartographer's Table palette: aged survey paper, sepia ink, a deep
        // moss legend panel, and an aged-gold "gild" that only appears on the
        // dark sidebar. All greys carry a warm bias so nothing reads as flat.
        paper: '#e9e2cf', // the page ground — a map left open on the table
        parchment: {
          50: '#f6f1e2', // raised surfaces: cards, inputs, buttons
          100: '#eee4cf', // subtle fills, hovers, skeletons, summary blocks
          200: '#ddd0b0', // soft chips / pending badge
          300: '#cdbf9d', // hairline borders + input strokes
          400: '#bcab84', // stronger rule / double border
        },
        ink: {
          900: '#2b2a20', // primary text
          700: '#463f30', // strong secondary
          // 500/400 are tuned to clear WCAG AA (4.5:1) on both the paper ground
          // (#e9e2cf) and the lighter card surface (#f6f1e2).
          500: '#5e5540',
          400: '#665c43',
        },
        // The accent is a sepia map-ink brown, not the old hearth orange.
        hearth: {
          600: '#8a5a2b',
          500: '#a06a30',
          400: '#b98a4e',
          100: '#ece0c8',
        },
        moss: {
          900: '#223027', // deep legend-panel green (the sidebar)
          800: '#2c3d30', // sidebar hover
          700: '#3f5233',
          500: '#5f7a4d',
          200: '#d3ddc4',
        },
        gild: {
          300: '#e9c88a', // aged gold — brand + primary action on the dark panel
          200: '#d8ccb0', // muted parchment text on the dark panel
        },
        // Tag label inks: a small, muted set that stays in the cartographer's
        // key — deep enough to carry parchment-50 text at AA. Tokens mirror
        // backend app/services/tags.py TAG_COLORS; keep the two lists in step.
        tag: {
          moss: '#4f6a3f',
          hearth: '#8a5a2b',
          ochre: '#7d6410',
          clay: '#9c4f3a',
          rose: '#97445d',
          plum: '#5f4a7a',
          indigo: '#3f5578',
          teal: '#2f6b60',
          stone: '#5c5647',
        },
      },
      fontFamily: {
        display: ['ui-serif', '"Iowan Old Style"', '"Hoefler Text"', 'Georgia', 'Cambria', 'serif'],
        body: ['ui-sans-serif', 'system-ui', '"Segoe UI"', 'sans-serif'],
      },
      boxShadow: {
        // A small hard offset, like a card resting on the table.
        inset: '3px 3px 0 rgba(90, 70, 40, 0.06)',
      },
    },
  },
  plugins: [],
};
