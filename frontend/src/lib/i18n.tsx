import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

// Lightweight, dependency-free i18n. English is the source language and the
// fallback for any missing key. Add a language by extending `Lang`, `LANGUAGES`,
// and the `translations` table below.

export type Lang = 'en' | 'de' | 'es';

export const LANGUAGES: { code: Lang; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'de', label: 'Deutsch' },
  { code: 'es', label: 'Español' },
];

const STORAGE_KEY = 'mathom-lang';

type Vars = Record<string, string | number>;

// Each key maps to a string per language. `*_one` / `*_other` variants are
// selected automatically when a `count` variable is passed to `t`.
const translations: Record<Lang, Record<string, string>> = {
  en: {
    'app.tagline': 'mathom',
    'language.label': 'Language',

    'nav.library': 'Library',
    'nav.collections': 'Collections',
    'nav.timeline': 'Timeline',
    'nav.templates': 'Templates',

    'library.title': 'mathom',
    'library.newMathom': '+ New Mathom',
    'library.searchPlaceholder': 'Search transcripts, summaries, titles…',
    'library.shelf.all': 'All',
    'library.shelf.favorites': '★ Favorites',
    'library.shelf.archived': 'Archived',
    'library.results_one': '{count} result for “{query}”',
    'library.results_other': '{count} results for “{query}”',
    'library.emptyTitle': 'The shelves are empty — for now.',
    'library.emptyBody': 'Upload your first recording and Mathom will remember it for you.',

    'detail.notFound': 'This Mathom is not on the shelves.',
    'detail.backToLibrary': 'Back to the Library',
    'detail.fetching': 'Fetching from the shelves…',
    'detail.library': '← Library',
    'detail.favorited': '★ Favorited',
    'detail.favorite': '☆ Favorite',
    'detail.toggleFavorite': 'Toggle favorite',
    'detail.unarchive': 'Unarchive',
    'detail.archive': 'Archive',
    'detail.delete': 'Delete',
    'detail.confirmDelete': 'Remove this Mathom and its audio for good?',
    'detail.errorFallback': 'Something went wrong while processing this recording.',
    'detail.tagsCollections': 'Tags & Collections',
    'detail.export': 'export .{format}',
    'detail.removeTag': 'Remove tag',
    'detail.addTag': 'add tag ⏎',
    'detail.noCollections': 'No collections yet — create one on the Collections page.',
    'detail.summaries': 'Summaries',
    'detail.thinking': 'Thinking…',
    'detail.generate': 'Generate',
    'detail.noSummaries': 'No summaries yet.',
    'detail.confirmDeleteSummary': 'Do you really want to delete this summary?',
    'detail.transcript': 'Transcript',
    'detail.transcriptPending': 'The transcript will appear here once processing finishes.',
    'detail.askTitle': 'Ask about this recording',
    'detail.clearConversation': 'Clear conversation',
    'detail.chatReady': 'e.g. What did we agree on?',
    'detail.chatWaiting': 'Available once the transcript is ready',
    'detail.ask': 'Ask',

    'collections.title': 'Collections',
    'collections.subtitle': 'Shelves for related recordings.',
    'collections.name': 'Name',
    'collections.namePlaceholder': 'e.g. House renovation',
    'collections.description': 'Description',
    'collections.create': 'Create',
    'collections.createError': 'Could not create collection',
    'collections.confirmDelete': 'Delete collection “{name}”? Mathoms stay in the library.',
    'collections.delete': 'Delete',
    'collections.empty': 'Empty — add Mathoms from their detail page.',

    'templates.title': 'Prompt Templates',
    'templates.new': '+ New template',
    'templates.helpBefore': 'Templates shape how Mathom writes summaries. Use ',
    'templates.helpAfter': ' where the transcript should go.',
    'templates.builtin': 'built-in',
    'templates.slug': 'Slug',
    'templates.slugPlaceholder': 'my-template',
    'templates.name': 'Name',
    'templates.description': 'Description',
    'templates.prompt': 'Prompt',
    'templates.created': 'Template created.',
    'templates.saved': 'Saved.',
    'templates.saveFailed': 'Saving failed',
    'templates.confirmDelete': 'Delete template “{name}”?',
    'templates.delete': 'Delete',
    'templates.create': 'Create',
    'templates.save': 'Save',

    'timeline.title': 'Timeline',
    'timeline.subtitle': 'Your mathom, month by month.',
    'timeline.empty': 'Nothing recorded yet.',

    'upload.title': 'Bring a recording home',
    'upload.subtitle':
      'It will be transcribed and summarized, then shelved in your mathom.',
    'upload.audioFile': 'Audio file',
    'upload.chooseFileFirst': 'Choose an audio file first.',
    'upload.titleLabel': 'Title',
    'upload.optional': '(optional)',
    'upload.titlePlaceholder': 'e.g. Call with the roofing company',
    'upload.summaryStyle': 'Summary style',
    'upload.uploadFailed': 'Upload failed',
    'upload.cancel': 'Cancel',
    'upload.uploading': 'Uploading…',
    'upload.upload': 'Upload',
    'upload.sharedSubtitle':
      'Shared from another app. It will be transcribed and summarized, then shelved.',

    'share.receiving': 'Receiving your recording…',
    'share.emptyTitle': 'Nothing was shared.',
    'share.emptyBody': 'Share an audio message to Mathom to bring it home.',
    'share.backToLibrary': 'Back to the Library',

    'status.pending': 'Waiting',
    'status.transcribing': 'Transcribing…',
    'status.summarizing': 'Summarizing…',
    'status.ready': 'Ready',
    'status.error': 'Error',

    'card.favorite': 'favorite',

    'nav.users': 'Users',
    'nav.settings': 'Sign-in',

    'auth.welcome': 'Welcome to Mathom',
    'auth.subtitle': 'Sign in to open your mathom.',
    'auth.signIn': 'Sign in with Authentik',
    'auth.signOut': 'Sign out',
    'auth.loading': 'Opening the archive…',
    'auth.notConfigured':
      'Single sign-on is not configured yet. Ask the archive Owner to finish setup.',
    'auth.error.expired': 'Your sign-in link expired. Please try again.',
    'auth.error.not_provisioned': 'Your account is not set up for Mathom yet.',
    'auth.error.account_disabled': 'Your account has been disabled.',
    'auth.error.generic': 'Sign-in failed. Please try again.',

    'users.title': 'Users',
    'users.subtitle': 'Who can use this mathom.',
    'users.add': 'Add user',
    'users.addHint': 'New accounts are created as users, not administrators.',
    'users.name': 'Display name',
    'users.email': 'Email',
    'users.password': 'Password',
    'users.confirmPassword': 'Confirm password',
    'users.mustChangePassword': 'Require a password change on first sign-in',
    'users.create': 'Create user',
    'users.creating': 'Creating user…',
    'users.passwordMismatch': 'Passwords do not match',
    'users.createError': 'Could not create user',
    'users.role': 'Role',
    'users.active': 'Active',
    'users.disabled': 'Disabled',
    'users.activate': 'Activate',
    'users.deactivate': 'Deactivate',
    'users.delete': 'Delete',
    'users.confirmDelete': 'Remove {email} and all of their Mathoms?',
    'users.you': 'you',
    'users.lastLogin': 'Last sign-in',
    'users.never': 'never',
    'users.loadError': 'Could not load users',
    'role.owner': 'Owner',
    'role.admin': 'Admin',
    'role.user': 'User',

    'settings.title': 'Authentik single sign-on',
    'settings.subtitle': 'Connect Mathom to your Authentik server.',
    'settings.status': 'Status',
    'settings.configured': 'Connected',
    'settings.notConfigured': 'Not configured yet',
    'settings.issuer': 'Issuer URL',
    'settings.issuerHint': 'e.g. https://auth.example.com/application/o/mathom/',
    'settings.clientId': 'Client ID',
    'settings.clientSecret': 'Client secret',
    'settings.clientSecretSet': 'A secret is saved — leave blank to keep it.',
    'settings.scopes': 'Scopes',
    'settings.publicBaseUrl': 'Public base URL',
    'settings.publicBaseUrlHint': 'Where users reach Mathom, e.g. https://mathom.example.com',
    'settings.autoCreate': 'Create accounts automatically on first sign-in',
    'settings.verifySsl': 'Verify the Authentik TLS certificate',
    'settings.save': 'Save',
    'settings.saved': 'Saved.',
    'settings.saveFailed': 'Saving failed',

    'common.loading': 'Fetching from the shelves…',
    'common.loadError': 'Could not reach the archive. Check your connection and try again.',
    'common.retry': 'Try again',

    'duration.minSec': '{m} min {s} s',
    'duration.sec': '{s} s',

    'error.boundaryTitle': 'Something slipped off the shelf.',
    'error.boundaryBody': 'An unexpected error interrupted the page. Nothing was lost.',
    'error.boundaryRetry': 'Reload this view',

    'library.searching': 'Searching…',
    'library.searchError': 'Search is unavailable right now.',

    'collections.created': 'Collection created.',
    'collections.deleted': 'Collection deleted.',
    'collections.none': 'No collections yet — create one above.',

    'users.created': 'User created.',
    'users.deleted': 'User removed.',

    'upload.success': 'Recording added — transcription has begun.',

    'detail.titleLabel': 'Title — click to rename',
    'detail.chatFailed': 'Could not send your question.',
    'detail.summaryCreated': 'Summary generated.',
    'detail.summaryFailed': 'Could not generate a summary.',
    'detail.deleted': 'Mathom removed.',

    'login.title': 'Sign in',
    'login.email': 'Email',
    'login.password': 'Password',
    'login.signIn': 'Sign in',
    'login.signingIn': 'Signing in…',
    'login.invalid': 'Invalid email or password.',
    'login.authentik': 'Continue with Authentik',

    'onboarding.title': 'Set up Mathom',
    'onboarding.subtitle':
      'Create the first administrator account. Passwords must be at least 12 characters.',
    'onboarding.name': 'Display name',
    'onboarding.email': 'Email',
    'onboarding.password': 'Password',
    'onboarding.confirmPassword': 'Confirm password',
    'onboarding.passwordMismatch': 'Passwords do not match',
    'onboarding.failed': 'Setup failed',
    'onboarding.creating': 'Creating administrator…',
    'onboarding.create': 'Create administrator',
  },
  de: {
    'app.tagline': 'mathom',
    'language.label': 'Sprache',

    'nav.library': 'Bibliothek',
    'nav.collections': 'Sammlungen',
    'nav.timeline': 'Zeitleiste',
    'nav.templates': 'Vorlagen',

    'library.title': 'mathom',
    'library.newMathom': '+ Neues Mathom',
    'library.searchPlaceholder': 'Transkripte, Zusammenfassungen, Titel durchsuchen…',
    'library.shelf.all': 'Alle',
    'library.shelf.favorites': '★ Favoriten',
    'library.shelf.archived': 'Archiviert',
    'library.results_one': '{count} Ergebnis für „{query}“',
    'library.results_other': '{count} Ergebnisse für „{query}“',
    'library.emptyTitle': 'Die Regale sind leer — noch.',
    'library.emptyBody': 'Lade deine erste Aufnahme hoch und Mathom bewahrt sie für dich auf.',

    'detail.notFound': 'Dieses Mathom steht nicht im Regal.',
    'detail.backToLibrary': 'Zurück zur Bibliothek',
    'detail.fetching': 'Wird aus dem Regal geholt…',
    'detail.library': '← Bibliothek',
    'detail.favorited': '★ Favorisiert',
    'detail.favorite': '☆ Favorit',
    'detail.toggleFavorite': 'Favorit umschalten',
    'detail.unarchive': 'Aus Archiv holen',
    'detail.archive': 'Archivieren',
    'detail.delete': 'Löschen',
    'detail.confirmDelete': 'Dieses Mathom und seine Audiodatei endgültig entfernen?',
    'detail.errorFallback': 'Beim Verarbeiten dieser Aufnahme ist etwas schiefgelaufen.',
    'detail.tagsCollections': 'Schlagwörter & Sammlungen',
    'detail.export': 'als .{format} exportieren',
    'detail.removeTag': 'Schlagwort entfernen',
    'detail.addTag': 'Schlagwort hinzufügen ⏎',
    'detail.noCollections': 'Noch keine Sammlungen — lege eine auf der Sammlungen-Seite an.',
    'detail.summaries': 'Zusammenfassungen',
    'detail.thinking': 'Denkt nach…',
    'detail.generate': 'Erstellen',
    'detail.noSummaries': 'Noch keine Zusammenfassungen.',
    'detail.confirmDeleteSummary': 'Möchtest du diese Zusammenfassung wirklich löschen?',
    'detail.transcript': 'Transkript',
    'detail.transcriptPending': 'Das Transkript erscheint hier, sobald die Verarbeitung fertig ist.',
    'detail.askTitle': 'Frage zu dieser Aufnahme stellen',
    'detail.clearConversation': 'Unterhaltung löschen',
    'detail.chatReady': 'z. B. Worauf haben wir uns geeinigt?',
    'detail.chatWaiting': 'Verfügbar, sobald das Transkript bereit ist',
    'detail.ask': 'Fragen',

    'collections.title': 'Sammlungen',
    'collections.subtitle': 'Regale für zusammengehörige Aufnahmen.',
    'collections.name': 'Name',
    'collections.namePlaceholder': 'z. B. Hausrenovierung',
    'collections.description': 'Beschreibung',
    'collections.create': 'Anlegen',
    'collections.createError': 'Sammlung konnte nicht angelegt werden',
    'collections.confirmDelete':
      'Sammlung „{name}“ löschen? Die Mathoms bleiben in der Bibliothek.',
    'collections.delete': 'Löschen',
    'collections.empty': 'Leer — füge Mathoms über ihre Detailseite hinzu.',

    'templates.title': 'Prompt-Vorlagen',
    'templates.new': '+ Neue Vorlage',
    'templates.helpBefore':
      'Vorlagen bestimmen, wie Mathom Zusammenfassungen schreibt. Verwende ',
    'templates.helpAfter': ', wo das Transkript stehen soll.',
    'templates.builtin': 'integriert',
    'templates.slug': 'Kennung',
    'templates.slugPlaceholder': 'meine-vorlage',
    'templates.name': 'Name',
    'templates.description': 'Beschreibung',
    'templates.prompt': 'Prompt',
    'templates.created': 'Vorlage erstellt.',
    'templates.saved': 'Gespeichert.',
    'templates.saveFailed': 'Speichern fehlgeschlagen',
    'templates.confirmDelete': 'Vorlage „{name}“ löschen?',
    'templates.delete': 'Löschen',
    'templates.create': 'Anlegen',
    'templates.save': 'Speichern',

    'timeline.title': 'Zeitleiste',
    'timeline.subtitle': 'Dein mathom, Monat für Monat.',
    'timeline.empty': 'Noch nichts aufgenommen.',

    'upload.title': 'Eine Aufnahme nach Hause bringen',
    'upload.subtitle':
      'Sie wird transkribiert und zusammengefasst, dann in deinem mathom einsortiert.',
    'upload.audioFile': 'Audiodatei',
    'upload.chooseFileFirst': 'Wähle zuerst eine Audiodatei aus.',
    'upload.titleLabel': 'Titel',
    'upload.optional': '(optional)',
    'upload.titlePlaceholder': 'z. B. Anruf mit der Dachdeckerfirma',
    'upload.summaryStyle': 'Zusammenfassungsstil',
    'upload.uploadFailed': 'Hochladen fehlgeschlagen',
    'upload.cancel': 'Abbrechen',
    'upload.uploading': 'Wird hochgeladen…',
    'upload.upload': 'Hochladen',
    'upload.sharedSubtitle':
      'Aus einer anderen App geteilt. Wird transkribiert, zusammengefasst und abgelegt.',

    'share.receiving': 'Deine Aufnahme wird empfangen…',
    'share.emptyTitle': 'Es wurde nichts geteilt.',
    'share.emptyBody': 'Teile eine Audionachricht an Mathom, um sie nach Hause zu bringen.',
    'share.backToLibrary': 'Zurück zur Bibliothek',

    'status.pending': 'Wartet',
    'status.transcribing': 'Transkribiert…',
    'status.summarizing': 'Fasst zusammen…',
    'status.ready': 'Fertig',
    'status.error': 'Fehler',

    'card.favorite': 'Favorit',

    'nav.users': 'Benutzer',
    'nav.settings': 'Anmeldung',

    'auth.welcome': 'Willkommen bei Mathom',
    'auth.subtitle': 'Melde dich an, um dein mathom zu öffnen.',
    'auth.signIn': 'Mit Authentik anmelden',
    'auth.signOut': 'Abmelden',
    'auth.loading': 'Das Archiv wird geöffnet…',
    'auth.notConfigured':
      'Single Sign-on ist noch nicht eingerichtet. Bitte den Eigentümer, die Einrichtung abzuschließen.',
    'auth.error.expired': 'Dein Anmeldelink ist abgelaufen. Bitte versuche es erneut.',
    'auth.error.not_provisioned': 'Dein Konto ist noch nicht für Mathom eingerichtet.',
    'auth.error.account_disabled': 'Dein Konto wurde deaktiviert.',
    'auth.error.generic': 'Anmeldung fehlgeschlagen. Bitte versuche es erneut.',

    'users.title': 'Benutzer',
    'users.subtitle': 'Wer dieses mathom nutzen darf.',
    'users.add': 'Benutzer hinzufügen',
    'users.addHint': 'Neue Konten werden als Benutzer, nicht als Administratoren angelegt.',
    'users.name': 'Anzeigename',
    'users.email': 'E-Mail',
    'users.password': 'Passwort',
    'users.confirmPassword': 'Passwort bestätigen',
    'users.mustChangePassword': 'Passwortänderung bei der ersten Anmeldung verlangen',
    'users.create': 'Benutzer erstellen',
    'users.creating': 'Benutzer wird erstellt…',
    'users.passwordMismatch': 'Passwörter stimmen nicht überein',
    'users.createError': 'Benutzer konnte nicht erstellt werden',
    'users.role': 'Rolle',
    'users.active': 'Aktiv',
    'users.disabled': 'Deaktiviert',
    'users.activate': 'Aktivieren',
    'users.deactivate': 'Deaktivieren',
    'users.delete': 'Löschen',
    'users.confirmDelete': '{email} und alle zugehörigen Mathoms entfernen?',
    'users.you': 'du',
    'users.lastLogin': 'Letzte Anmeldung',
    'users.never': 'nie',
    'users.loadError': 'Benutzer konnten nicht geladen werden',
    'role.owner': 'Eigentümer',
    'role.admin': 'Administrator',
    'role.user': 'Benutzer',

    'settings.title': 'Authentik Single Sign-on',
    'settings.subtitle': 'Verbinde Mathom mit deinem Authentik-Server.',
    'settings.status': 'Status',
    'settings.configured': 'Verbunden',
    'settings.notConfigured': 'Noch nicht eingerichtet',
    'settings.issuer': 'Issuer-URL',
    'settings.clientId': 'Client-ID',
    'settings.clientSecret': 'Client-Secret',
    'settings.clientSecretSet': 'Ein Secret ist gespeichert — leer lassen, um es zu behalten.',
    'settings.scopes': 'Scopes',
    'settings.publicBaseUrl': 'Öffentliche Basis-URL',
    'settings.autoCreate': 'Konten bei der ersten Anmeldung automatisch anlegen',
    'settings.verifySsl': 'TLS-Zertifikat von Authentik prüfen',
    'settings.save': 'Speichern',
    'settings.saved': 'Gespeichert.',
    'settings.saveFailed': 'Speichern fehlgeschlagen',

    'common.loading': 'Wird aus den Regalen geholt…',
    'common.loadError': 'Das Archiv ist nicht erreichbar. Prüfe die Verbindung und versuche es erneut.',
    'common.retry': 'Erneut versuchen',

    'duration.minSec': '{m} Min. {s} Sek.',
    'duration.sec': '{s} Sek.',

    'error.boundaryTitle': 'Etwas ist aus dem Regal gefallen.',
    'error.boundaryBody': 'Ein unerwarteter Fehler hat die Seite unterbrochen. Es ging nichts verloren.',
    'error.boundaryRetry': 'Ansicht neu laden',

    'library.searching': 'Wird gesucht…',
    'library.searchError': 'Die Suche ist gerade nicht verfügbar.',

    'collections.created': 'Sammlung erstellt.',
    'collections.deleted': 'Sammlung gelöscht.',
    'collections.none': 'Noch keine Sammlungen – erstelle oben eine.',

    'users.created': 'Benutzer erstellt.',
    'users.deleted': 'Benutzer entfernt.',

    'upload.success': 'Aufnahme hinzugefügt – die Transkription hat begonnen.',

    'detail.titleLabel': 'Titel – zum Umbenennen klicken',
    'detail.chatFailed': 'Deine Frage konnte nicht gesendet werden.',
    'detail.summaryCreated': 'Zusammenfassung erstellt.',
    'detail.summaryFailed': 'Zusammenfassung konnte nicht erstellt werden.',
    'detail.deleted': 'Mathom entfernt.',

    'login.title': 'Anmelden',
    'login.email': 'E-Mail',
    'login.password': 'Passwort',
    'login.signIn': 'Anmelden',
    'login.signingIn': 'Anmeldung läuft…',
    'login.invalid': 'Ungültige E-Mail oder ungültiges Passwort.',
    'login.authentik': 'Mit Authentik fortfahren',

    'onboarding.title': 'Mathom einrichten',
    'onboarding.subtitle':
      'Erstelle das erste Administratorkonto. Passwörter müssen mindestens 12 Zeichen lang sein.',
    'onboarding.name': 'Anzeigename',
    'onboarding.email': 'E-Mail',
    'onboarding.password': 'Passwort',
    'onboarding.confirmPassword': 'Passwort bestätigen',
    'onboarding.passwordMismatch': 'Passwörter stimmen nicht überein',
    'onboarding.failed': 'Einrichtung fehlgeschlagen',
    'onboarding.creating': 'Administrator wird erstellt…',
    'onboarding.create': 'Administrator erstellen',
  },
  es: {
    'app.tagline': 'mathom',
    'language.label': 'Idioma',

    'nav.library': 'Biblioteca',
    'nav.collections': 'Colecciones',
    'nav.timeline': 'Cronología',
    'nav.templates': 'Plantillas',

    'library.title': 'mathom',
    'library.newMathom': '+ Nuevo Mathom',
    'library.searchPlaceholder': 'Buscar transcripciones, resúmenes, títulos…',
    'library.shelf.all': 'Todos',
    'library.shelf.favorites': '★ Favoritos',
    'library.shelf.archived': 'Archivados',
    'library.results_one': '{count} resultado para «{query}»',
    'library.results_other': '{count} resultados para «{query}»',
    'library.emptyTitle': 'Los estantes están vacíos — por ahora.',
    'library.emptyBody': 'Sube tu primera grabación y Mathom la recordará por ti.',

    'detail.notFound': 'Este Mathom no está en los estantes.',
    'detail.backToLibrary': 'Volver a la Biblioteca',
    'detail.fetching': 'Sacándolo de los estantes…',
    'detail.library': '← Biblioteca',
    'detail.favorited': '★ Favorito',
    'detail.favorite': '☆ Favorito',
    'detail.toggleFavorite': 'Alternar favorito',
    'detail.unarchive': 'Desarchivar',
    'detail.archive': 'Archivar',
    'detail.delete': 'Eliminar',
    'detail.confirmDelete': '¿Eliminar este Mathom y su audio para siempre?',
    'detail.errorFallback': 'Algo salió mal al procesar esta grabación.',
    'detail.tagsCollections': 'Etiquetas y colecciones',
    'detail.export': 'exportar .{format}',
    'detail.removeTag': 'Quitar etiqueta',
    'detail.addTag': 'añadir etiqueta ⏎',
    'detail.noCollections': 'Aún no hay colecciones — crea una en la página de Colecciones.',
    'detail.summaries': 'Resúmenes',
    'detail.thinking': 'Pensando…',
    'detail.generate': 'Generar',
    'detail.noSummaries': 'Aún no hay resúmenes.',
    'detail.confirmDeleteSummary': '¿Realmente quieres eliminar este resumen?',
    'detail.transcript': 'Transcripción',
    'detail.transcriptPending': 'La transcripción aparecerá aquí cuando termine el procesamiento.',
    'detail.askTitle': 'Pregunta sobre esta grabación',
    'detail.clearConversation': 'Borrar conversación',
    'detail.chatReady': 'p. ej. ¿En qué quedamos?',
    'detail.chatWaiting': 'Disponible cuando la transcripción esté lista',
    'detail.ask': 'Preguntar',

    'collections.title': 'Colecciones',
    'collections.subtitle': 'Estantes para grabaciones relacionadas.',
    'collections.name': 'Nombre',
    'collections.namePlaceholder': 'p. ej. Reforma de la casa',
    'collections.description': 'Descripción',
    'collections.create': 'Crear',
    'collections.createError': 'No se pudo crear la colección',
    'collections.confirmDelete':
      '¿Eliminar la colección «{name}»? Los Mathoms permanecen en la biblioteca.',
    'collections.delete': 'Eliminar',
    'collections.empty': 'Vacía — añade Mathoms desde su página de detalle.',

    'templates.title': 'Plantillas de prompt',
    'templates.new': '+ Nueva plantilla',
    'templates.helpBefore': 'Las plantillas definen cómo Mathom escribe los resúmenes. Usa ',
    'templates.helpAfter': ' donde deba ir la transcripción.',
    'templates.builtin': 'integrada',
    'templates.slug': 'Identificador',
    'templates.slugPlaceholder': 'mi-plantilla',
    'templates.name': 'Nombre',
    'templates.description': 'Descripción',
    'templates.prompt': 'Prompt',
    'templates.created': 'Plantilla creada.',
    'templates.saved': 'Guardado.',
    'templates.saveFailed': 'Error al guardar',
    'templates.confirmDelete': '¿Eliminar la plantilla «{name}»?',
    'templates.delete': 'Eliminar',
    'templates.create': 'Crear',
    'templates.save': 'Guardar',

    'timeline.title': 'Cronología',
    'timeline.subtitle': 'Tu mathom, mes a mes.',
    'timeline.empty': 'Aún no hay nada grabado.',

    'upload.title': 'Trae una grabación a casa',
    'upload.subtitle':
      'Se transcribirá y resumirá, y luego se guardará en tu mathom.',
    'upload.audioFile': 'Archivo de audio',
    'upload.chooseFileFirst': 'Elige primero un archivo de audio.',
    'upload.titleLabel': 'Título',
    'upload.optional': '(opcional)',
    'upload.titlePlaceholder': 'p. ej. Llamada con la empresa de tejados',
    'upload.summaryStyle': 'Estilo de resumen',
    'upload.uploadFailed': 'Error al subir',
    'upload.cancel': 'Cancelar',
    'upload.uploading': 'Subiendo…',
    'upload.upload': 'Subir',
    'upload.sharedSubtitle':
      'Compartido desde otra app. Se transcribirá, se resumirá y se guardará.',

    'share.receiving': 'Recibiendo tu grabación…',
    'share.emptyTitle': 'No se compartió nada.',
    'share.emptyBody': 'Comparte un mensaje de audio con Mathom para traerlo a casa.',
    'share.backToLibrary': 'Volver a la Biblioteca',

    'status.pending': 'En espera',
    'status.transcribing': 'Transcribiendo…',
    'status.summarizing': 'Resumiendo…',
    'status.ready': 'Listo',
    'status.error': 'Error',

    'card.favorite': 'favorito',

    'nav.users': 'Usuarios',
    'nav.settings': 'Acceso',

    'auth.welcome': 'Bienvenido a Mathom',
    'auth.subtitle': 'Inicia sesión para abrir tu mathom.',
    'auth.signIn': 'Iniciar sesión con Authentik',
    'auth.signOut': 'Cerrar sesión',
    'auth.loading': 'Abriendo el archivo…',
    'auth.notConfigured':
      'El inicio de sesión único aún no está configurado. Pide al propietario que termine la configuración.',
    'auth.error.expired': 'Tu enlace de acceso caducó. Inténtalo de nuevo.',
    'auth.error.not_provisioned': 'Tu cuenta aún no está configurada para Mathom.',
    'auth.error.account_disabled': 'Tu cuenta ha sido deshabilitada.',
    'auth.error.generic': 'Error al iniciar sesión. Inténtalo de nuevo.',

    'users.title': 'Usuarios',
    'users.subtitle': 'Quién puede usar este mathom.',
    'users.add': 'Añadir usuario',
    'users.addHint': 'Las cuentas nuevas se crean como usuarios, no como administradores.',
    'users.name': 'Nombre visible',
    'users.email': 'Correo electrónico',
    'users.password': 'Contraseña',
    'users.confirmPassword': 'Confirmar contraseña',
    'users.mustChangePassword': 'Exigir un cambio de contraseña al iniciar sesión por primera vez',
    'users.create': 'Crear usuario',
    'users.creating': 'Creando usuario…',
    'users.passwordMismatch': 'Las contraseñas no coinciden',
    'users.createError': 'No se pudo crear el usuario',
    'users.role': 'Rol',
    'users.active': 'Activo',
    'users.disabled': 'Deshabilitado',
    'users.activate': 'Activar',
    'users.deactivate': 'Desactivar',
    'users.delete': 'Eliminar',
    'users.confirmDelete': '¿Eliminar a {email} y todos sus Mathoms?',
    'users.you': 'tú',
    'users.lastLogin': 'Último acceso',
    'users.never': 'nunca',
    'users.loadError': 'No se pudieron cargar los usuarios',
    'role.owner': 'Propietario',
    'role.admin': 'Administrador',
    'role.user': 'Usuario',

    'settings.title': 'Inicio de sesión único con Authentik',
    'settings.subtitle': 'Conecta Mathom con tu servidor Authentik.',
    'settings.status': 'Estado',
    'settings.configured': 'Conectado',
    'settings.notConfigured': 'Aún no configurado',
    'settings.issuer': 'URL del emisor',
    'settings.clientId': 'ID de cliente',
    'settings.clientSecret': 'Secreto de cliente',
    'settings.clientSecretSet': 'Hay un secreto guardado — déjalo en blanco para conservarlo.',
    'settings.scopes': 'Ámbitos',
    'settings.publicBaseUrl': 'URL base pública',
    'settings.autoCreate': 'Crear cuentas automáticamente en el primer acceso',
    'settings.verifySsl': 'Verificar el certificado TLS de Authentik',
    'settings.save': 'Guardar',
    'settings.saved': 'Guardado.',
    'settings.saveFailed': 'Error al guardar',

    'common.loading': 'Buscando en los estantes…',
    'common.loadError': 'No se pudo acceder al archivo. Revisa tu conexión e inténtalo de nuevo.',
    'common.retry': 'Intentar de nuevo',

    'duration.minSec': '{m} min {s} s',
    'duration.sec': '{s} s',

    'error.boundaryTitle': 'Algo se cayó del estante.',
    'error.boundaryBody': 'Un error inesperado interrumpió la página. No se perdió nada.',
    'error.boundaryRetry': 'Recargar esta vista',

    'library.searching': 'Buscando…',
    'library.searchError': 'La búsqueda no está disponible en este momento.',

    'collections.created': 'Colección creada.',
    'collections.deleted': 'Colección eliminada.',
    'collections.none': 'Aún no hay colecciones: crea una arriba.',

    'users.created': 'Usuario creado.',
    'users.deleted': 'Usuario eliminado.',

    'upload.success': 'Grabación añadida: la transcripción ha comenzado.',

    'detail.titleLabel': 'Título: haz clic para renombrar',
    'detail.chatFailed': 'No se pudo enviar tu pregunta.',
    'detail.summaryCreated': 'Resumen generado.',
    'detail.summaryFailed': 'No se pudo generar el resumen.',
    'detail.deleted': 'Mathom eliminado.',

    'login.title': 'Iniciar sesión',
    'login.email': 'Correo electrónico',
    'login.password': 'Contraseña',
    'login.signIn': 'Iniciar sesión',
    'login.signingIn': 'Iniciando sesión…',
    'login.invalid': 'Correo o contraseña no válidos.',
    'login.authentik': 'Continuar con Authentik',

    'onboarding.title': 'Configurar Mathom',
    'onboarding.subtitle':
      'Crea la primera cuenta de administrador. Las contraseñas deben tener al menos 12 caracteres.',
    'onboarding.name': 'Nombre visible',
    'onboarding.email': 'Correo electrónico',
    'onboarding.password': 'Contraseña',
    'onboarding.confirmPassword': 'Confirmar contraseña',
    'onboarding.passwordMismatch': 'Las contraseñas no coinciden',
    'onboarding.failed': 'Error en la configuración',
    'onboarding.creating': 'Creando administrador…',
    'onboarding.create': 'Crear administrador',
  },
};

function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in vars ? String(vars[name]) : match,
  );
}

export function translate(lang: Lang, key: string, vars?: Vars): string {
  const table = translations[lang];
  const fallback = translations.en;

  let lookupKey = key;
  if (vars && 'count' in vars) {
    const plural = Number(vars.count) === 1 ? `${key}_one` : `${key}_other`;
    if (plural in table || plural in fallback) lookupKey = plural;
  }

  const template = table[lookupKey] ?? fallback[lookupKey] ?? key;
  return interpolate(template, vars);
}

function detectInitialLang(): Lang {
  if (typeof window === 'undefined') return 'en';
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === 'en' || stored === 'de' || stored === 'es') return stored;
  const browser = window.navigator.language?.slice(0, 2).toLowerCase();
  if (browser === 'de' || browser === 'es') return browser;
  return 'en';
}

interface I18nValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, vars?: Vars) => string;
}

const I18nContext = createContext<I18nValue>({
  lang: 'en',
  setLang: () => undefined,
  t: (key, vars) => translate('en', key, vars),
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(detectInitialLang);

  useEffect(() => {
    if (typeof document !== 'undefined') document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    if (typeof window !== 'undefined') window.localStorage.setItem(STORAGE_KEY, next);
  }, []);

  const value = useMemo<I18nValue>(
    () => ({ lang, setLang, t: (key, vars) => translate(lang, key, vars) }),
    [lang, setLang],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  return useContext(I18nContext);
}
