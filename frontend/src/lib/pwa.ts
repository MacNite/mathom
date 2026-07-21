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

/**
 * Whether the device can hand text off to the native share sheet. iOS Safari
 * has no Web Share *Target* (nothing can be shared *into* Mathom there), but it
 * does support the outbound Web Share API, so this is how iOS users get a
 * summary or transcript back out into Messages, Mail, Notes, and the rest.
 */
export function canShareText(): boolean {
  return typeof navigator !== 'undefined' && typeof navigator.share === 'function';
}

/**
 * Open the native share sheet with the given text. Returns true when the share
 * completed, false when it was unavailable or the user dismissed the sheet.
 * Any other failure is re-thrown so the caller can surface it.
 */
export async function shareText(data: { title?: string; text: string }): Promise<boolean> {
  if (!canShareText()) return false;
  try {
    await navigator.share({ title: data.title, text: data.text });
    return true;
  } catch (error) {
    // The user tapping "cancel" rejects with AbortError; that is not an error
    // worth reporting, so swallow it and report every other failure.
    if (error instanceof DOMException && error.name === 'AbortError') return false;
    throw error;
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
