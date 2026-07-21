// Mathom service worker.
//
// Its one job is to make Mathom installable and to receive files from the
// Android Share Sheet via the Web Share Target API. When another app (e.g.
// WhatsApp) shares a recording or document to Mathom, the browser POSTs a multipart
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

// Build an absolute redirect for a path within our scope. `Response.redirect`
// rejects relative URLs (it throws a TypeError), which would otherwise break
// the whole share hand-off, so always resolve against our own origin.
function shareRedirect(path) {
  return Response.redirect(new URL(path, self.location.origin).toString(), 303);
}

// Pull the shared file out of the form. The manifest asks Android to send it
// under the field name `file`, but be forgiving: if a share sheet uses a
// different name, fall back to the first File-shaped entry we can find.
function findSharedFile(formData) {
  const named = formData.get('file');
  if (named && typeof named === 'object' && 'size' in named && named.size > 0) {
    return named;
  }
  for (const value of formData.values()) {
    if (value && typeof value === 'object' && 'size' in value && value.size > 0) {
      return value;
    }
  }
  return null;
}

async function handleShareTarget(request) {
  try {
    const formData = await request.formData();
    const file = findSharedFile(formData);
    const title = (formData.get('title') || '').toString();
    // Android sends link shares in the `url` field and plain-text shares in
    // `text`; combine them so neither is silently dropped.
    const sharedText = [formData.get('text'), formData.get('url')]
      .map((value) => (value || '').toString().trim())
      .filter(Boolean)
      .join('\n');

    const cache = await caches.open(SHARE_CACHE);

    if (file) {
      const headers = new Headers();
      headers.set('Content-Type', file.type || 'application/octet-stream');
      headers.set('X-Shared-Filename', encodeURIComponent(file.name || 'shared-recording'));
      headers.set('X-Shared-Title', encodeURIComponent(title));
      headers.set('X-Shared-Text', encodeURIComponent(sharedText));
      headers.set('X-Shared-At', String(Date.now()));
      await cache.put(SHARED_FILE_KEY, new Response(file, { headers }));
      // 303 forces the follow-up request to be a GET of the React route.
      return shareRedirect('/share-target?shared=1');
    }

    if (sharedText) {
      await cache.put(
        SHARED_FILE_KEY,
        new Response(sharedText, {
          headers: { 'X-Shared-Text-Only': '1', 'X-Shared-Title': encodeURIComponent(title) },
        }),
      );
      return shareRedirect('/share-target?shared=1');
    }

    return shareRedirect('/share-target?shared=empty');
  } catch (error) {
    return shareRedirect('/share-target?shared=error');
  }
}
