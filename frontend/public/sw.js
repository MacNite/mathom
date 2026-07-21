// Mathom service worker.
//
// Its one job is to make Mathom installable and to receive files from the
// Android Share Sheet via the Web Share Target API. When another app (e.g.
// WhatsApp) shares a voice message to Mathom, the browser POSTs a multipart
// form to `/share-target`. A page cannot read that POST directly, so the
// service worker intercepts it, stashes the shared file in the Cache Storage,
// and redirects to the `/share-target` route where the React app picks it up.
//
// Everything stays local: the file only ever moves from the device to the
// user's own Mathom server. No caching of app assets or offline behaviour is
// implemented here on purpose — Mathom is served from the user's own machine.

const SHARE_CACHE = 'mathom-share-target-v1';
const SHARED_FILE_KEY = '/__shared-audio';

self.addEventListener('install', () => {
  // Activate this worker immediately so share-target works on first install.
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method === 'POST' && url.pathname === '/share-target') {
    event.respondWith(handleShareTarget(event.request));
  }
  // All other requests fall through to the network (the user's own server).
});

async function handleShareTarget(request) {
  try {
    const formData = await request.formData();
    const file = formData.get('audio');
    const title = (formData.get('title') || '').toString();
    const sharedText = (formData.get('text') || '').toString();

    if (file && typeof file === 'object' && file.size > 0) {
      const cache = await caches.open(SHARE_CACHE);
      const headers = new Headers();
      headers.set('Content-Type', file.type || 'application/octet-stream');
      headers.set('X-Shared-Filename', encodeURIComponent(file.name || 'shared-recording'));
      headers.set('X-Shared-Title', encodeURIComponent(title));
      headers.set('X-Shared-Text', encodeURIComponent(sharedText));
      headers.set('X-Shared-At', String(Date.now()));
      await cache.put(SHARED_FILE_KEY, new Response(file, { headers }));
      // 303 forces the follow-up request to be a GET of the React route.
      return Response.redirect('/share-target?shared=1', 303);
    }

    if (sharedText.trim()) {
      const cache = await caches.open(SHARE_CACHE);
      await cache.put(SHARED_FILE_KEY, new Response(sharedText, { headers: { 'X-Shared-Text-Only': '1', 'X-Shared-Title': encodeURIComponent(title) } }));
      return Response.redirect('/share-target?shared=1', 303);
    }

    return Response.redirect('/share-target?shared=empty', 303);
  } catch (error) {
    return Response.redirect('/share-target?shared=error', 303);
  }
}
