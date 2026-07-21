# Progressive Web App & Share Target

Mathom's frontend is an installable Progressive Web App (PWA). Once installed
on an Android device it registers as a destination in the system **Share
Sheet**, so you can send a voice message straight from another app (WhatsApp,
Telegram, Signal, a web-meeting download, your recorder, or a file manager) into
your own mathom.

```
WhatsApp → Share → Mathom → title / template → Upload → Transcribe → Summarize
```

Everything stays local: the shared audio moves from your device to your own
Mathom server and nowhere else. No cloud services are involved.

## How it works

- **`frontend/public/manifest.webmanifest`** declares the app (name, icons,
  theme) and a [`share_target`](https://developer.mozilla.org/en-US/docs/Web/Manifest/share_target)
  that accepts supported audio/video files and text via an HTTP `POST` to `/share-target`.
- **`frontend/public/sw.js`** is a service worker whose only jobs are to make
  the app installable and to receive the share. A web page cannot read a
  `POST`ed file directly, so the worker intercepts the request, stashes the
  file in Cache Storage, and redirects (`303`) to the `/share-target` route.
- **`frontend/src/pages/ShareTarget.tsx`** reads the stashed file back from
  Cache Storage and opens the normal upload dialog pre-filled with it. From
  there the user confirms the source. Text-only shares become text Mathoms;
  file-plus-text shares keep text as a suggested title and never merge it into a transcript.

## Why PWA instead of a Play Store app

Mathom deliberately has **no Google Play Store app**. Installing the PWA directly
from your browser keeps the app as a direct connection to your own server, avoids
an app-store distribution account and its associated tracking/policy surface, and
lets the browser provide the native-feeling share-sheet integration. The PWA is
the recommended mobile installation method.

## Installing on Android

1. Open Mathom in Chrome (or another Chromium browser) on your phone.
2. Use the browser menu → **Install app** / **Add to Home screen**.
3. Mathom now appears in the Android Share Sheet. In WhatsApp, Telegram, a
   recorder, or a file manager, choose **Share** → **Mathom**. Pick a title and
   summary template (for example TL;DR, action items, meeting minutes, or
   calendar events), then tap **Upload**.

## Requirements & limitations

For a video selected in the upload dialog, the optional visual-analysis switch explains that only
sampled still frames go to the configured local Ollama vision model. The backend remains
authoritative because it classifies streams with ffprobe.

- **HTTPS or `localhost`.** Service workers (and therefore the Share Target)
  require a [secure context](https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts).
  A plain `http://<lan-ip>:8080` origin will install neither the worker nor the
  share target. Terminate TLS in front of the proxy (e.g. a reverse proxy or
  tunnel) when serving Mathom to a phone over the network.
- **Android / Chromium only.** Web Share Target is well supported by installed
  PWAs in Chromium browsers. iOS Safari does not support it; a small native
  companion app remains the better long-term option there. On iOS the PWA still
  installs and works — it just does not appear in the Share Sheet.
- The proxy serves `sw.js` with `Cache-Control: no-cache` and
  `Service-Worker-Allowed: /` so worker updates ship promptly and can control
  the whole origin.
