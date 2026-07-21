// Service worker registration and Web Share Target helpers.
//
// The service worker (public/sw.js) receives files shared from the Android
// Share Sheet and stashes them in Cache Storage. These helpers register the
// worker and let the React app read and clear that stashed file.

const SHARE_CACHE = 'mathom-share-target-v1';
const SHARED_FILE_KEY = '/__shared-audio';

export interface SharedFile {
  /** The shared file, or null when only text/links were shared. */
  file: File | null;
  title: string;
  text: string;
}

/** Register the service worker. Safe to call on every load; it is idempotent. */
export function registerServiceWorker(): void {
  if (!('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // Registration failing (e.g. insecure context) must not break the app.
    });
  });
}

/**
 * Read the file most recently shared into Mathom, if any. Returns null
 * when nothing was shared or the platform lacks Cache Storage.
 */
export async function readSharedAudio(): Promise<SharedFile | null> {
  if (!('caches' in window)) return null;
  try {
    const cache = await caches.open(SHARE_CACHE);
    const response = await cache.match(SHARED_FILE_KEY);
    if (!response) return null;

    const blob = await response.blob();
    if (blob.size === 0) return null;

    const filename = decodeHeader(response.headers.get('X-Shared-Filename')) || 'shared-recording';
    const title = decodeHeader(response.headers.get('X-Shared-Title'));
    const type = response.headers.get('Content-Type') || blob.type || 'application/octet-stream';

    const textOnly = response.headers.get('X-Shared-Text-Only') === '1';
    const text = textOnly
      ? decodeHeader(response.headers.get('X-Shared-Text')) || (await blob.text())
      : decodeHeader(response.headers.get('X-Shared-Text'));
    const file = textOnly ? null : new File([blob], filename, { type });
    return { file, title, text };
  } catch {
    return null;
  }
}

/** Remove the stashed shared file so it is not re-uploaded on the next visit. */
export async function clearSharedAudio(): Promise<void> {
  if (!('caches' in window)) return;
  try {
    const cache = await caches.open(SHARE_CACHE);
    await cache.delete(SHARED_FILE_KEY);
  } catch {
    // Nothing to clean up.
  }
}

function decodeHeader(value: string | null): string {
  if (!value) return '';
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}
