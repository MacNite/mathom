# Mathom Website

A dependency-free product website for Mathom, including:

- Product positioning and feature overview
- Architecture and local-first workflow
- Docker, GPU, and TrueNAS setup guidance
- Links to the repository documentation
- Responsive interactive demo dashboard
- Clearly labeled fixed/static demo data

## Preview locally

From the repository root:

```bash
python3 -m http.server 4173 --directory website
```

Then open <http://localhost:4173>.

You can also open `website/index.html` directly in a browser. Running a local server is recommended so all browser features behave consistently.

## Files

- `index.html` — complete page structure and content
- `styles.css` — responsive visual design
- `app.js` — dashboard filtering, search, sorting, navigation, and fixed demo records

## Demo data

All dashboard records are hard-coded in `app.js`. The demo does not call the Mathom API, upload files, process recordings, or persist user input.

## Deployment

The folder can be deployed without a build step to GitHub Pages, Netlify, Cloudflare Pages, nginx, or any static host. Set the publish directory to `website`.

For GitHub Pages, either configure a Pages workflow that uploads `website/`, or move/copy these files into the repository's selected Pages source directory.
