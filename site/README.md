# Mathom — GitHub Pages site

This directory holds the public landing site for Mathom, deployed to GitHub
Pages by [`.github/workflows/pages.yml`](../.github/workflows/pages.yml).

It is a fully **static, self-contained** site — plain HTML, one CSS file, and a
sprinkle of vanilla JS for scroll reveals. No build step, no framework, no
external network calls (fonts are system fonts, matching the app's Tailwind
theme). This keeps it in the spirit of the project: local-first and dependency-light.

```
site/
├── index.html      # the landing page
├── demo.html       # interactive, static demo of the app (see below)
├── demo.css        # demo styles (app-like sidebar + cards)
├── demo.js         # demo runtime: seeded data, no backend, no network
├── 404.html        # friendly not-found page
├── styles.css      # warm archive palette (parchment / ink / hearth / moss)
├── assets/         # logo + icons copied from frontend/public/branding
└── .nojekyll       # skip Jekyll processing on Pages
```

## The demo (`demo.html`)

A click-around, **fully client-side** reproduction of the real app — Library,
Mathom detail (summaries, transcript, chat), Timeline, Templates, and
Collections. It runs on seeded sample data held in memory, so:

- **No backend, no network, no real transcription or LLM.** Summaries and chat
  replies are canned but plausible, on a short simulated delay.
- **Nothing persists.** Reload to reset to the seed data.
- It exists to show the shape and feel of Mathom to someone who hasn't
  installed it — not to process real recordings.

Interactions that work: searching, shelf/tag filters, opening a Mathom,
favoriting, archiving, deleting, editing the title, adding/removing tags,
toggling collections, generating a summary from any template, asking follow-up
questions, and a simulated "New Mathom" upload that walks through
`pending → transcribing → summarizing → ready`.

## Preview locally

Any static file server works:

```bash
cd site
python3 -m http.server 4000
# open http://localhost:4000
```

## Deployment

On every push to `main` that touches `site/**` (or the workflow itself), the
`pages` workflow uploads this directory as a Pages artifact and deploys it. The
workflow can also be run manually via **Actions → pages → Run workflow**.

> **One-time setup:** in the repository settings, set
> **Settings → Pages → Build and deployment → Source** to **GitHub Actions**.

The site will be served at:

```
https://macnite.github.io/mathom/
```

## Updating brand assets

The images in `assets/` are copied from `frontend/public/branding` and
`frontend/public/icons`. If the branding changes there, refresh them:

```bash
cp ../frontend/public/branding/mathom-logo-mark-color.png assets/logo-mark.png
cp ../frontend/public/branding/mathom-bag-icon-color.png  assets/bag-icon.png
cp ../frontend/public/icons/icon-192.png                  assets/favicon-192.png
cp ../frontend/public/icons/apple-touch-icon.png          assets/apple-touch-icon.png
cp ../frontend/public/icons/icon-512.png                  assets/icon-512.png
```
