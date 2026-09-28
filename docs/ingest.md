# Automated ingest — watched folder & API tokens

Two ways to get recordings into Mathom without opening the upload dialog. Both
end in the same pipeline as a normal upload (same validation, transcription,
summary, origin tag), and both trigger
[“your Mathom is ready” notifications](notifications.md).

| | Watched folder | API tokens |
| --- | --- | --- |
| Direction | Mathom **pulls** from a mounted folder | A tool **pushes** to Mathom |
| Typical sender | Syncthing, an SMB share, a recorder | Tasker, iOS Shortcuts, scripts, a future WhatsApp bridge |
| Auth | None — being in the folder is enough | A personal token (per user, revocable) |
| Metadata | Date/app from the filename | Sender, tags, recorded time, message ID, template |
| iPhone | ✗ | ✓ (Shortcuts) |

---

## Watched folder

Mathom scans a folder every `INBOX_POLL_SECONDS` (default 30) and imports new
audio/video files (the same extension allowlist as uploads).

- A file is imported once it looks the same on **two consecutive scans**, so
  half-synced files are never picked up. Hidden files/folders (Syncthing's
  `.stfolder`, `.syncthing.*.tmp`) and `*.tmp`/`*.part` files are ignored.
- **Files are never modified.** A read-only mount is fine. The
  `ingest_ledger` table remembers every handled path and its SHA-256, so:
  - a file imports exactly once, even if you later delete its Mathom;
  - the same content under another name (or merely touched) is skipped;
  - files Mathom can't use (not audio, too large) are remembered and not
    retried.
- Imported Mathoms get an AI-written title, the origin tag (WhatsApp, Telegram,
  Signal, …) and a **recorded time** guessed from the filename
  (`PTT-20260722-WA0004`, `audio_2026-07-22_14-03-11`, …) or the file's
  modification time, which Syncthing preserves. The Timeline files them under
  that date.
- A full processing queue (`MAX_QUEUED_JOBS`) just defers the rest to a later
  scan, so a large backfill trickles in instead of failing.
- **Who owns an import** depends on sign-in:
  - *Sign-in off* (single user): everything in the folder, at any depth, is
    yours.
  - *Sign-in on* (`AUTH_ENABLED=true`): every user has a **folder name**, and
    `/inbox/<folder name>/…` belongs to them. It is filled in from the display
    name (`Alice Baker` → `alice-baker`), unique, and editable under
    **📥 Automation → Your inbox folder**.

    ```
    /inbox/
      alice-baker/            ← Alice's phone syncs here
        WhatsApp Voice Notes/…
      bob/                    ← Bob's
    ```

    Files lying directly in `/inbox`, and folders that match no active
    account, are left alone; admins see them listed on the Automation page.
    Content is de-duplicated **per person**, so a voice note forwarded to both
    Alice and Bob becomes one Mathom for each. Renaming a folder name means
    renaming the folder on disk too; files already imported are recognised by
    their content and not imported again.

### Setup

1. **Mount the folder** — in `compose.yaml`, uncomment the inbox volume and set
   the host path in `.env`:

   ```yaml
       volumes:
         - mathom-data:/data
         - whisper-models:/models
         - ${INBOX_HOST_DIR:?set INBOX_HOST_DIR}:/inbox:ro
   ```

   ```dotenv
   INBOX_HOST_DIR=/mnt/tank/sync/whatsapp-voice-notes
   INBOX_DIR=/inbox
   ```

   The container runs as UID 1000, which needs **read** access to the folder.
2. `docker compose up -d`. The **📥 Automation** page shows each user their
   folder (with sign-in on) and admins the overall status: every user's folder,
   last scan, imports, unmatched folders and loose files. **Scan now** skips
   the wait.

### Android: WhatsApp voice notes via Syncthing

1. Install **Syncthing** on the NAS (TrueNAS app or container) and
   **Syncthing-Fork** on the phone, and pair the two devices.
2. On the phone, add a folder:
   `Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Voice Notes`
   (older WhatsApp versions: `WhatsApp/Media/WhatsApp Voice Notes`), with
   **Folder type: Send Only**.
3. Share it with the NAS and accept it there into the host folder you mounted
   (on the NAS side use **Receive Only**). With sign-in on, accept it into
   **your** subfolder, e.g. `<inbox host folder>/alice-baker/Voice Notes`. Each
   family member pairs their own phone into their own subfolder.
4. Optional: add `WhatsApp Audio` too (forwarded audio files) as a second
   Syncthing folder next to it, e.g. `…/alice-baker/Audio`.

New voice notes — sent **and** received — now appear in Mathom a minute or two
after they reach the phone. Remember this collects other people's voice
messages too; point Syncthing at a narrower folder if that isn't wanted.

---

## API tokens

Create a token on **📥 Automation → API tokens** (name it after the device,
optionally let it expire). It is shown **once**; only a hash is stored. A token
can only upload — it can't read or change anything else, and it doesn't work on
the rest of the API. Revoke it any time.

Tokens are required even when sign-in is disabled, so the automation endpoints
are never open. With sign-in enabled, **each user creates their own tokens**
and uploads land in the archive of the token's owner — so several people can
each automate their own phone with no shared configuration.

### Endpoints

`POST /api/ingest/audio` — multipart form, field `file`.

`POST /api/ingest/audio/raw?filename=<name>` — the file as the raw request body;
every other field below becomes a query parameter.

Header: `Authorization: Bearer mth_…`

| Field | Meaning |
| --- | --- |
| `title` | Optional; blank lets the model write one. |
| `speaker` | Who is speaking (fills the Speaker filter). |
| `tags` | Comma-separated tag names. |
| `recorded_at` | ISO 8601 time the recording was made, e.g. `2026-07-22T09:14:00+02:00`. |
| `template_slug`, `template_language` | Summary template and language (`en`/`de`/`es`). |
| `source_app` | Override the origin label detected from the filename. |
| `external_source`, `external_id` | Idempotency key, e.g. `whatsapp` + message ID. |

Responses are the Mathom as JSON: `201` when created; `200` with
`X-Mathom-Duplicate: true` when the same `external_source`/`external_id` — or,
without an ID, the same file bytes — was already ingested for this user.
Errors: `401` bad/expired token, `413` too large, `415` unsupported type,
`422` not audio/video, `503` queue full (with `Retry-After`).

### curl

```sh
curl -H "Authorization: Bearer $MATHOM_TOKEN" \
  -F "file=@PTT-20260722-WA0004.opus" \
  -F "speaker=Rosie" -F "tags=family" \
  https://mathom.example.com/api/ingest/audio
```

### Tasker (Android)

Profile *File Modified* (or *Event → File Closed*) on the voice-notes folder →
Task **HTTP Request**:

- Method `POST`, URL
  `https://mathom.example.com/api/ingest/audio/raw?filename=<name>`, with
  `<name>` the file-name variable your trigger provides
- Headers `Authorization: Bearer mth_…`
- File To Send: the recording's path

This needs no Syncthing and works away from home if Mathom is reachable over
HTTPS (VPN or reverse proxy).

### iOS Shortcuts

Share-sheet shortcut accepting *Files/Media* → **Get Contents of URL**:
method `POST`, URL `https://mathom.example.com/api/ingest/audio`, header
`Authorization: Bearer mth_…`, request body **Form** with a *File* field named
`file` set to the Shortcut Input. Save a WhatsApp voice note via *Share → Save
to Files* or share it straight to the shortcut.

## Security notes

- Anyone who can write into a user's subfolder can file recordings into that
  user's archive. With Syncthing each phone only reaches its own folder; don't
  hand out one shared drop folder if users shouldn't be able to fill each
  other's archives.
- Tokens are 256-bit random secrets (`mth_` prefix, easy to spot in logs or
  secret scanners); the database holds only SHA-256 digests. Last use is shown
  on the Automation page.
- Ingest shares the upload validation: extension allowlist, `MAX_UPLOAD_MB`,
  ffprobe stream check, server-generated storage names (the sent filename is
  only used for its extension and display).
- The ingest endpoints count against the "heavy" rate limit like uploads.
- The watched folder skips symlinks (so a synced link can't point Mathom at
  other files in the container) and never writes to the mounted folder.
