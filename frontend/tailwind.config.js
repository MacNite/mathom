/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Warm archive palette: parchment, ink, amber hearth, moss shelves.
        parchment: {
          50: '#fdfaf3',
          100: '#f8f1e2',
          200: '#efe2c6',
          300: '#e2cda1',
        },
        ink: {
          900: '#2d2418',
          700: '#4a3d2c',
          500: '#6f5f48',
          400: '#94836a',
        },
        hearth: {
          600: '#b45f21',
          500: '#c97a35',
          400: '#dd9a5b',
          100: '#f7e3cc',
        },
        moss: {
          700: '#3f5233',
          500: '#5f7a4d',
          200: '#d3ddc4',
        },
      },
      fontFamily: {
        display: ['ui-serif', 'Georgia', 'Cambria', 'Times New Roman', 'serif'],
        body: ['ui-sans-serif', 'system-ui', 'Segoe UI', 'sans-serif'],
      },
      borderRadius: {
        doorway: '1.25rem 1.25rem 0.375rem 0.375rem',
      },
    },
  },
  plugins: [],
};
