import { afterEach, describe, expect, it, vi } from 'vitest';

import { canShareText, clearSharedAudio, readSharedAudio, shareText } from './pwa';

// Minimal in-memory stand-in for the Cache Storage API used by the helpers.
function installCaches(entry: Response | null) {
  const store = new Map<string, Response>();
  if (entry) store.set('/__shared-audio', entry);
  const cache = {
    match: vi.fn(async (key: string) => store.get(key) ?? undefined),
    delete: vi.fn(async (key: string) => store.delete(key)),
    put: vi.fn(async (key: string, res: Response) => void store.set(key, res)),
  };
  const caches = { open: vi.fn(async () => cache) };
  vi.stubGlobal('caches', caches);
  return { cache, store };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('readSharedAudio', () => {
  it('reconstructs a File from the cached response and decodes its metadata', async () => {
    const response = new Response(new Blob(['audio-bytes'], { type: 'audio/ogg' }), {
      headers: {
        'Content-Type': 'audio/ogg',
        'X-Shared-Filename': encodeURIComponent('voice note.ogg'),
        'X-Shared-Title': encodeURIComponent('Grandma’s recipe'),
      },
    });
    installCaches(response);

    const shared = await readSharedAudio();

    expect(shared).not.toBeNull();
    expect(shared?.file).toBeInstanceOf(File);
    expect(shared?.file?.name).toBe('voice note.ogg');
    expect(shared?.file?.type).toBe('audio/ogg');
    expect(shared?.title).toBe('Grandma’s recipe');
  });

  it('returns a null file for text-only shares and keeps the shared text', async () => {
    const response = new Response('https://example.com/article', {
      headers: {
        'X-Shared-Text-Only': '1',
        'X-Shared-Title': encodeURIComponent('A link worth keeping'),
      },
    });
    installCaches(response);

    const shared = await readSharedAudio();

    expect(shared).not.toBeNull();
    expect(shared?.file).toBeNull();
    expect(shared?.text).toBe('https://example.com/article');
    expect(shared?.title).toBe('A link worth keeping');
  });

  it('returns null when nothing was shared', async () => {
    installCaches(null);
    expect(await readSharedAudio()).toBeNull();
  });

  it('returns null when Cache Storage is unavailable', async () => {
    vi.stubGlobal('caches', undefined);
    expect(await readSharedAudio()).toBeNull();
  });
});

describe('canShareText', () => {
  it('is true when the browser exposes navigator.share', () => {
    vi.stubGlobal('navigator', { share: vi.fn() });
    expect(canShareText()).toBe(true);
  });

  it('is false when navigator.share is missing (e.g. most desktop browsers)', () => {
    vi.stubGlobal('navigator', {});
    expect(canShareText()).toBe(false);
  });
});

describe('shareText', () => {
  it('hands the title and text to the native share sheet', async () => {
    const share = vi.fn(async () => undefined);
    vi.stubGlobal('navigator', { share });

    const shared = await shareText({ title: 'Roof call', text: 'Roof call\n\nWe agreed on slate.' });

    expect(shared).toBe(true);
    expect(share).toHaveBeenCalledWith({
      title: 'Roof call',
      text: 'Roof call\n\nWe agreed on slate.',
    });
  });

  it('returns false without sharing when the API is unavailable', async () => {
    vi.stubGlobal('navigator', {});
    expect(await shareText({ text: 'anything' })).toBe(false);
  });

  it('treats a user-cancelled share (AbortError) as a quiet no-op', async () => {
    const share = vi.fn(async () => {
      throw new DOMException('The user cancelled the share.', 'AbortError');
    });
    vi.stubGlobal('navigator', { share });

    expect(await shareText({ text: 'anything' })).toBe(false);
  });

  it('re-throws unexpected share failures so the caller can report them', async () => {
    const share = vi.fn(async () => {
      throw new DOMException('Permission denied', 'NotAllowedError');
    });
    vi.stubGlobal('navigator', { share });

    await expect(shareText({ text: 'anything' })).rejects.toThrow('Permission denied');
  });
});

describe('clearSharedAudio', () => {
  it('deletes the stashed shared file', async () => {
    const response = new Response(new Blob(['x'], { type: 'audio/ogg' }));
    const { cache } = installCaches(response);

    await clearSharedAudio();

    expect(cache.delete).toHaveBeenCalledWith('/__shared-audio');
  });
});
