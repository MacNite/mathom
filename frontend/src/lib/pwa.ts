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

// ── Web Push ────────────────────────────────────────────────────────────────
//
// The service worker shows "your Mathom is ready" notifications pushed by the
// backend. These helpers only talk to the browser; the caller hands the
// resulting subscription to `api.addPushSubscription`.

export type PushSupport = 'ok' | 'unsupported' | 'insecure' | 'ios-needs-install';

/** Whether this browser can receive Web Push, and if not, why. */
export function pushSupport(): PushSupport {
  if (typeof window === 'undefined') return 'unsupported';
  if (!window.isSecureContext) return 'insecure';
  const hasApis =
    'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  // iOS/iPadOS only exposes Web Push to PWAs added to the Home Screen.
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent);
  const standalone =
    window.matchMedia?.('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true;
  if (ios && !standalone) return 'ios-needs-install';
  return hasApis ? 'ok' : 'unsupported';
}

/** Decode the server's base64url VAPID key into the bytes `subscribe` wants. */
export function urlBase64ToUint8Array(value: string): Uint8Array {
  const padded = (value + '='.repeat((4 - (value.length % 4)) % 4))
    .replace(/-/g, '+')
    .replace(/_/g, '/');
  const raw = atob(padded);
  return Uint8Array.from(raw, (char) => char.charCodeAt(0));
}

async function readyRegistration(timeoutMs = 5000): Promise<ServiceWorkerRegistration> {
  // `ready` never settles when the worker failed to register, so bound it.
  return Promise.race([
    navigator.serviceWorker.ready,
    new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error('Service worker is not active')), timeoutMs),
    ),
  ]);
}

/** This device's current push subscription, if it has one. */
export async function currentPushSubscription(): Promise<PushSubscription | null> {
  if (pushSupport() !== 'ok') return null;
  try {
    const registration = await readyRegistration();
    return await registration.pushManager.getSubscription();
  } catch {
    return null;
  }
}

/**
 * Ask for permission and subscribe this device. Resolves to the subscription,
 * or `null` when the user declined notifications.
 */
export async function subscribeToPush(publicKey: string): Promise<PushSubscription | null> {
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return null;
  const registration = await readyRegistration();
  const options: PushSubscriptionOptionsInit = {
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey),
  };
  try {
    return await registration.pushManager.subscribe(options);
  } catch (error) {
    // A subscription made with a different server key blocks a new one;
    // drop it and try once more.
    const existing = await registration.pushManager.getSubscription();
    if (!existing) throw error;
    await existing.unsubscribe();
    return registration.pushManager.subscribe(options);
  }
}

/** Unsubscribe this device. Returns the endpoint that was removed, if any. */
export async function unsubscribeFromPush(): Promise<string | null> {
  const subscription = await currentPushSubscription();
  if (!subscription) return null;
  const { endpoint } = subscription;
  await subscription.unsubscribe();
  return endpoint;
}

/** The JSON body the backend expects for a subscription. */
export function subscriptionPayload(subscription: PushSubscription): {
  endpoint: string;
  keys: { p256dh: string; auth: string };
} {
  const data = subscription.toJSON();
  return {
    endpoint: subscription.endpoint,
    keys: { p256dh: data.keys?.p256dh ?? '', auth: data.keys?.auth ?? '' },
  };
}
