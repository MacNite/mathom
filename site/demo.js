/* ==========================================================================
   Mathom — static demo runtime. No backend, no network. All state lives in
   memory and resets on reload. Mirrors the real app's Library / Detail /
   Timeline / Templates / Collections views.
   ========================================================================== */
(function () {
  'use strict';

  // ----- i18n ---------------------------------------------------------------
  // Mirrors the real app's frontend/src/lib/i18n.tsx: same language list, same
  // localStorage key, same English-fallback + `_one`/`_other` plural logic.
  // Shared UI strings reuse the app's exact translations; demo-only chrome
  // (banner, toasts, sample notes) is translated to match.
  const LANGUAGES = [
    { code: 'en', label: 'English' },
    { code: 'de', label: 'Deutsch' },
    { code: 'es', label: 'Español' },
  ];
  const LANG_STORAGE_KEY = 'mathom-lang';

  const translations = {
    en: {
      'app.tagline': 'Your Local AI Memory House',
      'language.label': 'Language',

      'nav.library': 'Library',
      'nav.collections': 'Collections',
      'nav.timeline': 'Timeline',
      'nav.templates': 'Templates',

      'library.title': 'The Mathom-house',
      'library.newMathom': '+ New Mathom',
      'library.searchPlaceholder': 'Search transcripts, summaries, titles…',
      'library.shelf.all': 'All',
      'library.shelf.favorites': '★ Favorites',
      'library.shelf.archived': 'Archived',
      'library.results_one': '{count} result for “{query}”',
      'library.results_other': '{count} results for “{query}”',
      'library.emptyTitle': 'The shelves are empty — for now.',
      'library.emptyBody': 'Upload your first recording and Mathom will remember it for you.',
      'library.noMatches': 'No matches.',

      'detail.library': '← Library',
      'detail.favorited': '★ Favorited',
      'detail.favorite': '☆ Favorite',
      'detail.unarchive': 'Unarchive',
      'detail.archive': 'Archive',
      'detail.delete': 'Delete',
      'detail.tagsCollections': 'Tags & Collections',
      'detail.export': 'export .{format}',
      'detail.removeTag': 'Remove tag',
      'detail.addTag': 'add tag ⏎',
      'detail.noCollections': 'No collections yet — create one on the Collections page.',
      'detail.summaries': 'Summaries',
      'detail.thinking': 'Thinking…',
      'detail.generate': 'Generate',
      'detail.noSummaries': 'No summaries yet.',
      'detail.transcript': 'Transcript',
      'detail.transcriptPending': 'The transcript will appear here once processing finishes.',
      'detail.askTitle': 'Ask about this recording',
      'detail.clearConversation': 'Clear conversation',
      'detail.chatReady': 'e.g. What did we agree on?',
      'detail.chatWaiting': 'Available once the transcript is ready',
      'detail.ask': 'Ask',

      'collections.title': 'Collections',
      'collections.subtitle': 'Shelves for related recordings.',
      'collections.count_one': '{count} Mathom',
      'collections.count_other': '{count} Mathoms',

      'templates.title': 'Prompt Templates',
      'templates.subtitle': 'Editable in the real app — the database copy is authoritative.',

      'timeline.title': 'Timeline',
      'timeline.subtitle': 'Your memory house, month by month.',
      'timeline.empty': 'Nothing recorded yet.',

      'status.pending': 'Waiting',
      'status.transcribing': 'Transcribing…',
      'status.summarizing': 'Summarizing…',
      'status.ready': 'Ready',
      'status.error': 'Error',

      'demo.badge': 'Demo mode',
      'demo.bannerRest': '— sample data, all in your browser. Nothing is uploaded or transcribed here.',
      'demo.backToSite': '← Back to site',
      'demo.runReal': 'Run the real thing ↗',
      'demo.sidebarNote': 'This is a guided sample of the app.',
      'demo.starGitHub': 'Star on GitHub',
      'demo.audioPlay': 'Play (demo)',

      'demo.toast.added': 'Recording added — transcribing…',
      'demo.toast.ready': '“{title}” is ready.',
      'demo.toast.favorited': 'Marked as favorite.',
      'demo.toast.unfavorited': 'Removed from favorites.',
      'demo.toast.archived': 'Archived.',
      'demo.toast.unarchived': 'Unarchived.',
      'demo.toast.deleted': 'Mathom deleted.',
      'demo.toast.playback': 'Audio playback is disabled in the demo.',
      'demo.toast.export': 'Export ({format}) is available in the real app.',
      'demo.toast.titleSaved': 'Title saved.',
      'demo.toast.summaryGenerated': '{name} summary generated.',
      'demo.confirmDelete': 'Delete this Mathom? (demo only — reload to restore)',
    },
    de: {
      'app.tagline': 'Dein lokales KI-Gedächtnishaus',
      'language.label': 'Sprache',

      'nav.library': 'Bibliothek',
      'nav.collections': 'Sammlungen',
      'nav.timeline': 'Zeitleiste',
      'nav.templates': 'Vorlagen',

      'library.title': 'Das Mathom-Haus',
      'library.newMathom': '+ Neues Mathom',
      'library.searchPlaceholder': 'Transkripte, Zusammenfassungen, Titel durchsuchen…',
      'library.shelf.all': 'Alle',
      'library.shelf.favorites': '★ Favoriten',
      'library.shelf.archived': 'Archiviert',
      'library.results_one': '{count} Ergebnis für „{query}“',
      'library.results_other': '{count} Ergebnisse für „{query}“',
      'library.emptyTitle': 'Die Regale sind leer — noch.',
      'library.emptyBody': 'Lade deine erste Aufnahme hoch und Mathom bewahrt sie für dich auf.',
      'library.noMatches': 'Keine Treffer.',

      'detail.library': '← Bibliothek',
      'detail.favorited': '★ Favorisiert',
      'detail.favorite': '☆ Favorit',
      'detail.unarchive': 'Aus Archiv holen',
      'detail.archive': 'Archivieren',
      'detail.delete': 'Löschen',
      'detail.tagsCollections': 'Schlagwörter & Sammlungen',
      'detail.export': 'als .{format} exportieren',
      'detail.removeTag': 'Schlagwort entfernen',
      'detail.addTag': 'Schlagwort hinzufügen ⏎',
      'detail.noCollections': 'Noch keine Sammlungen — lege eine auf der Sammlungen-Seite an.',
      'detail.summaries': 'Zusammenfassungen',
      'detail.thinking': 'Denkt nach…',
      'detail.generate': 'Erstellen',
      'detail.noSummaries': 'Noch keine Zusammenfassungen.',
      'detail.transcript': 'Transkript',
      'detail.transcriptPending': 'Das Transkript erscheint hier, sobald die Verarbeitung fertig ist.',
      'detail.askTitle': 'Frage zu dieser Aufnahme stellen',
      'detail.clearConversation': 'Unterhaltung löschen',
      'detail.chatReady': 'z. B. Worauf haben wir uns geeinigt?',
      'detail.chatWaiting': 'Verfügbar, sobald das Transkript bereit ist',
      'detail.ask': 'Fragen',

      'collections.title': 'Sammlungen',
      'collections.subtitle': 'Regale für zusammengehörige Aufnahmen.',
      'collections.count_one': '{count} Mathom',
      'collections.count_other': '{count} Mathoms',

      'templates.title': 'Prompt-Vorlagen',
      'templates.subtitle': 'In der echten App bearbeitbar — die Datenbankkopie ist maßgeblich.',

      'timeline.title': 'Zeitleiste',
      'timeline.subtitle': 'Dein Gedächtnishaus, Monat für Monat.',
      'timeline.empty': 'Noch nichts aufgenommen.',

      'status.pending': 'Wartet',
      'status.transcribing': 'Transkribiert…',
      'status.summarizing': 'Fasst zusammen…',
      'status.ready': 'Fertig',
      'status.error': 'Fehler',

      'demo.badge': 'Demo-Modus',
      'demo.bannerRest': '— Beispieldaten, komplett im Browser. Nichts wird hochgeladen oder transkribiert.',
      'demo.backToSite': '← Zurück zur Seite',
      'demo.runReal': 'Das Original ausführen ↗',
      'demo.sidebarNote': 'Dies ist ein geführtes Beispiel der App.',
      'demo.starGitHub': 'Auf GitHub favorisieren',
      'demo.audioPlay': 'Abspielen (Demo)',

      'demo.toast.added': 'Aufnahme hinzugefügt — wird transkribiert…',
      'demo.toast.ready': '„{title}“ ist fertig.',
      'demo.toast.favorited': 'Als Favorit markiert.',
      'demo.toast.unfavorited': 'Aus Favoriten entfernt.',
      'demo.toast.archived': 'Archiviert.',
      'demo.toast.unarchived': 'Aus Archiv geholt.',
      'demo.toast.deleted': 'Mathom gelöscht.',
      'demo.toast.playback': 'Audiowiedergabe ist in der Demo deaktiviert.',
      'demo.toast.export': 'Export ({format}) ist in der echten App verfügbar.',
      'demo.toast.titleSaved': 'Titel gespeichert.',
      'demo.toast.summaryGenerated': 'Zusammenfassung „{name}“ erstellt.',
      'demo.confirmDelete': 'Dieses Mathom löschen? (nur Demo — zum Wiederherstellen neu laden)',
    },
    es: {
      'app.tagline': 'Tu casa de memoria con IA local',
      'language.label': 'Idioma',

      'nav.library': 'Biblioteca',
      'nav.collections': 'Colecciones',
      'nav.timeline': 'Cronología',
      'nav.templates': 'Plantillas',

      'library.title': 'La casa Mathom',
      'library.newMathom': '+ Nuevo Mathom',
      'library.searchPlaceholder': 'Buscar transcripciones, resúmenes, títulos…',
      'library.shelf.all': 'Todos',
      'library.shelf.favorites': '★ Favoritos',
      'library.shelf.archived': 'Archivados',
      'library.results_one': '{count} resultado para «{query}»',
      'library.results_other': '{count} resultados para «{query}»',
      'library.emptyTitle': 'Los estantes están vacíos — por ahora.',
      'library.emptyBody': 'Sube tu primera grabación y Mathom la recordará por ti.',
      'library.noMatches': 'Sin coincidencias.',

      'detail.library': '← Biblioteca',
      'detail.favorited': '★ Favorito',
      'detail.favorite': '☆ Favorito',
      'detail.unarchive': 'Desarchivar',
      'detail.archive': 'Archivar',
      'detail.delete': 'Eliminar',
      'detail.tagsCollections': 'Etiquetas y colecciones',
      'detail.export': 'exportar .{format}',
      'detail.removeTag': 'Quitar etiqueta',
      'detail.addTag': 'añadir etiqueta ⏎',
      'detail.noCollections': 'Aún no hay colecciones — crea una en la página de Colecciones.',
      'detail.summaries': 'Resúmenes',
      'detail.thinking': 'Pensando…',
      'detail.generate': 'Generar',
      'detail.noSummaries': 'Aún no hay resúmenes.',
      'detail.transcript': 'Transcripción',
      'detail.transcriptPending': 'La transcripción aparecerá aquí cuando termine el procesamiento.',
      'detail.askTitle': 'Pregunta sobre esta grabación',
      'detail.clearConversation': 'Borrar conversación',
      'detail.chatReady': 'p. ej. ¿En qué quedamos?',
      'detail.chatWaiting': 'Disponible cuando la transcripción esté lista',
      'detail.ask': 'Preguntar',

      'collections.title': 'Colecciones',
      'collections.subtitle': 'Estantes para grabaciones relacionadas.',
      'collections.count_one': '{count} Mathom',
      'collections.count_other': '{count} Mathoms',

      'templates.title': 'Plantillas de prompt',
      'templates.subtitle': 'Editable en la app real — la copia de la base de datos es la autoritativa.',

      'timeline.title': 'Cronología',
      'timeline.subtitle': 'Tu casa de memoria, mes a mes.',
      'timeline.empty': 'Aún no hay nada grabado.',

      'status.pending': 'En espera',
      'status.transcribing': 'Transcribiendo…',
      'status.summarizing': 'Resumiendo…',
      'status.ready': 'Listo',
      'status.error': 'Error',

      'demo.badge': 'Modo demo',
      'demo.bannerRest': '— datos de ejemplo, todo en tu navegador. Nada se sube ni se transcribe aquí.',
      'demo.backToSite': '← Volver al sitio',
      'demo.runReal': 'Ejecutar la app real ↗',
      'demo.sidebarNote': 'Esta es una muestra guiada de la app.',
      'demo.starGitHub': 'Marcar con estrella en GitHub',
      'demo.audioPlay': 'Reproducir (demo)',

      'demo.toast.added': 'Grabación añadida — transcribiendo…',
      'demo.toast.ready': '«{title}» está lista.',
      'demo.toast.favorited': 'Marcado como favorito.',
      'demo.toast.unfavorited': 'Quitado de favoritos.',
      'demo.toast.archived': 'Archivado.',
      'demo.toast.unarchived': 'Desarchivado.',
      'demo.toast.deleted': 'Mathom eliminado.',
      'demo.toast.playback': 'La reproducción de audio está desactivada en la demo.',
      'demo.toast.export': 'La exportación ({format}) está disponible en la app real.',
      'demo.toast.titleSaved': 'Título guardado.',
      'demo.toast.summaryGenerated': 'Resumen «{name}» generado.',
      'demo.confirmDelete': '¿Eliminar este Mathom? (solo demo — recarga para restaurar)',
    },
  };

  function interpolate(template, vars) {
    if (!vars) return template;
    return template.replace(/\{(\w+)\}/g, (m, name) => (name in vars ? String(vars[name]) : m));
  }

  function detectInitialLang() {
    try {
      const stored = window.localStorage.getItem(LANG_STORAGE_KEY);
      if (stored === 'en' || stored === 'de' || stored === 'es') return stored;
    } catch (_) {}
    const browser = (window.navigator.language || 'en').slice(0, 2).toLowerCase();
    if (browser === 'de' || browser === 'es') return browser;
    return 'en';
  }

  let lang = detectInitialLang();

  function t(key, vars) {
    const table = translations[lang] || translations.en;
    const fallback = translations.en;
    let lookup = key;
    if (vars && 'count' in vars) {
      const plural = Number(vars.count) === 1 ? `${key}_one` : `${key}_other`;
      if (plural in table || plural in fallback) lookup = plural;
    }
    const template = table[lookup] != null ? table[lookup] : fallback[lookup] != null ? fallback[lookup] : key;
    return interpolate(template, vars);
  }

  // Translate the static chrome that lives in demo.html (banner, sidebar).
  function applyStaticI18n() {
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      el.textContent = t(el.getAttribute('data-i18n'));
    });
    document.querySelectorAll('[data-i18n-aria]').forEach((el) => {
      el.setAttribute('aria-label', t(el.getAttribute('data-i18n-aria')));
    });
  }

  function setLang(next) {
    lang = next;
    try { window.localStorage.setItem(LANG_STORAGE_KEY, next); } catch (_) {}
    applyStaticI18n();
    render();
  }

  // ----- tiny helpers -------------------------------------------------------
  const $ = (sel, root) => (root || document).querySelector(sel);
  const main = $('#main');
  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmtDate = (iso) =>
    new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  const fmtDuration = (s) => {
    if (s == null) return '';
    const t = Math.round(s), m = Math.floor(t / 60), r = t % 60;
    return m > 0 ? `${m} min ${r} s` : `${r} s`;
  };
  const clock = (s) => {
    if (!s) return '0:00';
    const t = Math.round(s);
    return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
  };
  let uid = 1000;
  const nextId = () => ++uid;

  function toast(msg) {
    const wrap = $('#toasts');
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = msg;
    wrap.appendChild(el);
    setTimeout(() => el.remove(), 2600);
  }

  // ----- seed data ----------------------------------------------------------
  const templates = [
    { id: 1, slug: 'tldr', name: 'TL;DR', description: 'A two-sentence gist of the whole recording.' },
    { id: 2, slug: 'meeting-minutes', name: 'Meeting Minutes', description: 'Structured minutes: attendees, decisions, next steps.' },
    { id: 3, slug: 'action-items', name: 'Action Items', description: 'A checklist of every commitment made.' },
    { id: 4, slug: 'email-draft', name: 'Email Draft', description: 'A ready-to-send recap email.' },
    { id: 5, slug: 'github-issue', name: 'GitHub Issue', description: 'A well-formed issue with context and acceptance criteria.' },
    { id: 6, slug: 'exec-brief', name: 'Executive Brief', description: 'The high-level story for a busy stakeholder.' },
  ];

  const collections = [
    { id: 1, name: 'Product', description: 'Roadmap and planning conversations.' },
    { id: 2, name: 'Personal', description: 'Notes to future me.' },
  ];

  function mkMathom(o) {
    return Object.assign(
      { favorite: false, archived: false, summaries: [], chat_messages: [], collections: [], tags: [], language: 'en', duration_seconds: 0 },
      o
    );
  }

  const mathoms = [
    mkMathom({
      id: 1, title: 'Kitchen renovation ideas', status: 'ready',
      duration_seconds: 214, created_at: '2026-07-15T18:22:00',
      original_filename: 'voice-memo-071526.m4a', favorite: true,
      tags: [{ id: 1, name: 'home' }, { id: 2, name: 'ideas' }],
      collections: [{ id: 2, name: 'Personal' }],
      transcript:
        "Okay, thinking out loud about the kitchen. The main thing is the counter space — it's just too cramped near the stove. I'd like to move the island a bit to the left so there's a proper prep zone. Warm oak for the cabinets, not the grey everyone does. Open shelving on the far wall for the nice bowls. Budget-wise, let's cap it at eight thousand and do it in two phases: cabinets first, then the island. Ask Dana whether her contractor is free in September.",
      summaries: [
        { id: 1, template_slug: 'tldr', template_name: 'TL;DR', model: 'llama3.2',
          content: 'A plan to reconfigure the kitchen for more prep space — move the island left, warm oak cabinets, open shelving — capped at $8k across two phases. Next step: check contractor availability with Dana for September.' },
      ],
      chat_messages: [
        { id: 1, role: 'user', content: 'What was the budget again?' },
        { id: 2, role: 'assistant', content: 'You set a cap of $8,000, split across two phases: cabinets first, then the island.' },
      ],
    }),
    mkMathom({
      id: 2, title: 'Team standup — Thursday', status: 'ready',
      duration_seconds: 372, created_at: '2026-07-16T09:05:00',
      original_filename: 'standup-thu.mp3',
      tags: [{ id: 3, name: 'work' }, { id: 4, name: 'standup' }],
      collections: [{ id: 1, name: 'Product' }],
      transcript:
        "Morning everyone. Priya, you're wrapping the search indexing work — anything blocking? No, just needs review. Marco, the onboarding redesign is behind because the copy isn't final; we'll pull that forward. Decision: we ship the FTS5 search behind a flag on Friday and turn it on Monday after we watch the logs over the weekend. Action items: Priya opens the PR by end of day, Marco chases the copy, and I'll update the release notes. Next standup Monday, same time.",
      summaries: [
        { id: 2, template_slug: 'meeting-minutes', template_name: 'Meeting Minutes', model: 'llama3.2',
          content: 'Attendees: Priya, Marco, host.\n\nDecisions:\n• Ship FTS5 search behind a flag Friday; enable Monday after weekend log review.\n\nAction items:\n• Priya — open the search PR by EOD.\n• Marco — finalize onboarding copy.\n• Host — update the release notes.\n\nNext: Monday standup, same time.' },
      ],
    }),
    mkMathom({
      id: 3, title: 'Podcast idea: local-first tools', status: 'ready',
      duration_seconds: 168, created_at: '2026-07-17T21:40:00',
      original_filename: 'idea-dump.wav',
      tags: [{ id: 2, name: 'ideas' }],
      transcript:
        "Idea for an episode: why local-first software is having a moment. Angle — people are tired of subscriptions and of their data walking out the door. Interview someone who self-hosts everything. Cover the trade-offs honestly: you own your data but you also own the backups. Working title, 'The house always wins.' Could tie it back to how a personal archive changes what you bother to keep.",
      summaries: [],
    }),
    mkMathom({
      id: 4, title: 'Call with the accountant', status: 'ready',
      duration_seconds: 641, created_at: '2026-07-18T14:12:00',
      original_filename: 'accountant-q3.m4a',
      tags: [{ id: 3, name: 'work' }, { id: 5, name: 'finance' }],
      collections: [],
      transcript:
        "Quick recap of the Q3 call. Estimated taxes are due the 15th — set that reminder. She suggested moving the home-office deduction to the simplified method this year, less paperwork. We should keep receipts for the new laptop and the desk. One open question: whether the conference travel counts if it was partly a holiday. She'll email a checklist by Friday.",
      summaries: [
        { id: 3, template_slug: 'action-items', template_name: 'Action Items', model: 'llama3.2',
          content: '☐ Pay estimated taxes by the 15th (set a reminder).\n☐ Switch home-office deduction to the simplified method.\n☐ Keep receipts for the laptop and desk.\n☐ Confirm whether partly-holiday conference travel is deductible.\n☐ Watch for the accountant’s checklist email (Friday).' },
      ],
      favorite: true,
    }),
    mkMathom({
      id: 5, title: 'Garden planning for spring', status: 'ready',
      duration_seconds: 132, created_at: '2026-06-28T11:30:00',
      original_filename: 'garden.m4a', archived: true,
      tags: [{ id: 1, name: 'home' }],
      transcript:
        "Spring garden notes. Tomatoes did badly in the shady bed last year, move them to the south fence. Try three types of basil this time. Build the raised bed before April. Order seeds in January so they don't sell out. Compost is nearly ready — turn it one more time.",
      summaries: [],
    }),
    mkMathom({
      id: 6, title: 'Book club: chapter thoughts', status: 'ready',
      duration_seconds: 205, created_at: '2026-06-20T20:15:00',
      original_filename: 'bookclub.mp3',
      tags: [{ id: 6, name: 'reading' }],
      transcript:
        "Thoughts before book club. The middle section drags but the ending earns it. I want to bring up how the house itself is almost a character — everything the family refuses to throw away ends up defining them. Question for the group: is keeping everything a kind of love or a kind of fear? Bring the sticky-noted copy.",
      summaries: [],
    }),
  ];

  // ----- fake "AI" generators (canned, deterministic) -----------------------
  function generateSummary(mathom, slug) {
    const t = mathom.transcript || '';
    const first = t.split('. ')[0] + '.';
    const byTemplate = {
      tldr: () =>
        `${first} The recording centers on “${mathom.title.toLowerCase()}”, with a clear next step to follow up on.`,
      'meeting-minutes': () =>
        `Topic: ${mathom.title}\n\nKey points:\n• ${first}\n• Follow-ups were captured for the group.\n\nDecision: proceed as discussed.\nNext: revisit at the following session.`,
      'action-items': () =>
        `☐ ${first.replace(/\.$/, '')}\n☐ Follow up on the open question raised.\n☐ Share a short recap with anyone affected.`,
      'email-draft': () =>
        `Subject: Recap — ${mathom.title}\n\nHi,\n\nQuick summary of the notes: ${first} I’ll follow up on the open items and circle back.\n\nBest,\nMe`,
      'github-issue': () =>
        `### Context\n${first}\n\n### Proposal\nCapture the idea from “${mathom.title}” as a tracked task.\n\n### Acceptance criteria\n- [ ] Decision recorded\n- [ ] Owner assigned\n- [ ] Follow-up scheduled`,
      'exec-brief': () =>
        `In one line: ${mathom.title}. ${first} No blockers; the next step is owner follow-through. Flagging only if timelines slip.`,
    };
    const fn = byTemplate[slug] || byTemplate.tldr;
    return fn();
  }

  function chatReply(mathom, question) {
    const q = question.toLowerCase();
    const t = mathom.transcript || '';
    if (/budget|cost|price|\$|money/.test(q) && /\$|budget|thousand|cap/.test(t)) {
      return 'Based on the recording, the budget is capped at $8,000, done in two phases — cabinets first, then the island.';
    }
    if (/who|attend|people/.test(q)) {
      return 'From the transcript, the people mentioned are the ones named in the recording — I’m grounded only in what was said, so I won’t invent others.';
    }
    if (/when|date|deadline|due/.test(q)) {
      return 'The recording mentions a follow-up timeframe; the clearest dated item is the deadline noted in the transcript. Check the highlighted line above for specifics.';
    }
    if (/next|action|todo|do/.test(q)) {
      return 'The main next step captured here is the follow-up mentioned at the end of the recording. Generate the “Action Items” summary for the full checklist.';
    }
    // generic grounded answer
    const sentence = t.split('. ').find((s) => q.split(/\W+/).some((w) => w.length > 3 && s.toLowerCase().includes(w)));
    return sentence
      ? `Here’s the relevant part: “${sentence.trim().replace(/\.$/, '')}.”`
      : 'I can only answer from this recording’s transcript, and I don’t see that covered. Try rephrasing, or ask about something mentioned above.';
  }

  // ----- view state ---------------------------------------------------------
  const state = { view: 'library', currentId: null, shelf: 'all', tag: null, query: '' };

  function setView(view) {
    state.view = view;
    $$('#nav a').forEach((a) => a.classList.toggle('active', a.dataset.view === view));
    render();
  }
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // ----- renderers ----------------------------------------------------------
  function badge(status) {
    return `<span class="badge ${status}">${esc(t('status.' + status))}</span>`;
  }

  function renderLibrary() {
    let list = mathoms.filter((m) => (state.shelf === 'archived' ? m.archived : !m.archived));
    if (state.shelf === 'favorites') list = list.filter((m) => m.favorite);
    if (state.tag) list = list.filter((m) => m.tags.some((t) => t.name === state.tag));

    const q = state.query.trim().toLowerCase();
    const searching = q.length > 0;
    let hits = [];
    if (searching) {
      hits = mathoms
        .filter((m) => !m.archived)
        .map((m) => {
          const hay = [m.title, m.transcript || '', m.tags.map((t) => t.name).join(' '), m.summaries.map((s) => s.content).join(' ')].join(' ');
          const idx = hay.toLowerCase().indexOf(q);
          if (idx === -1) return null;
          const start = Math.max(0, idx - 30);
          const raw = hay.slice(start, idx + q.length + 40);
          const snippet = (start > 0 ? '…' : '') +
            esc(raw).replace(new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig'), '<mark>$1</mark>') + '…';
          return { mathom: m, snippet };
        })
        .filter(Boolean);
    }

    const allTags = Array.from(new Set(mathoms.flatMap((m) => m.tags.map((t) => t.name))));

    const shelves = ['all', 'favorites', 'archived'];
    const shelfBtns = shelves
      .map((s) => `<button class="pill ${state.shelf === s ? 'active-shelf' : ''}" data-shelf="${s}">${esc(t('library.shelf.' + s))}</button>`)
      .join('');
    const tagBtns = allTags
      .map((name) => `<button class="pill tag ${state.tag === name ? 'active-tag' : ''}" data-tag="${esc(name)}">#${esc(name)}</button>`)
      .join('');

    const card = (m, snippet) => `
      <button class="card mathom-card" data-open="${m.id}">
        <div class="top">
          <h3>${m.favorite ? '★ ' : ''}${esc(m.title)}</h3>
          ${badge(m.status)}
        </div>
        <p class="meta">${fmtDate(m.created_at)}${m.duration_seconds ? ' · ' + fmtDuration(m.duration_seconds) : ''}${m.language ? ' · ' + m.language : ''}</p>
        ${m.tags.length ? `<div class="tags">${m.tags.map((t) => `<span class="chip">${esc(t.name)}</span>`).join('')}</div>` : ''}
      </button>
      ${snippet ? `<p class="snippet">${snippet}</p>` : ''}`;

    let body;
    if (searching) {
      body = `<p class="muted" style="margin-top:1rem">${esc(t('library.results', { count: hits.length, query: state.query }))}</p>
        <div style="display:flex;flex-direction:column;gap:0.75rem;margin-top:0.75rem">${hits.map((h) => `<div>${card(h.mathom, h.snippet)}</div>`).join('') || `<p class="muted">${esc(t('library.noMatches'))}</p>`}</div>`;
    } else if (list.length === 0) {
      body = `<div class="card" style="margin-top:2rem;text-align:center"><p class="font-display" style="font-size:1.1rem;margin:0">${esc(t('library.emptyTitle'))}</p><p class="muted" style="margin-top:0.25rem">${esc(t('library.emptyBody'))}</p></div>`;
    } else {
      body = `<div class="grid">${list.map((m) => card(m)).join('')}</div>`;
    }

    main.innerHTML = `
      <div class="page-head">
        <h2 class="font-display">${esc(t('library.title'))}</h2>
        <button class="btn-primary" id="new-mathom">${esc(t('library.newMathom'))}</button>
      </div>
      <input class="input" id="search" type="search" placeholder="${esc(t('library.searchPlaceholder'))}" value="${esc(state.query)}" style="margin-top:1rem" />
      ${!searching ? `<div class="filter-row">${shelfBtns}${tagBtns}</div>` : ''}
      ${body}`;

    const search = $('#search');
    search.addEventListener('input', (e) => {
      state.query = e.target.value;
      const pos = e.target.selectionStart;
      renderLibrary();
      const s2 = $('#search');
      s2.focus();
      try { s2.setSelectionRange(pos, pos); } catch (_) {}
    });
  }

  function renderDetail() {
    const m = mathoms.find((x) => x.id === state.currentId);
    if (!m) return setView('library');

    const exportLinks = ['md', 'txt', 'json']
      .map((f) => `<a data-export="${f}">${esc(t('detail.export', { format: f }))}</a>`)
      .join('');

    const collectionBtns = collections
      .map((c) => {
        const inC = m.collections.some((x) => x.id === c.id);
        return `<button class="pill ${inC ? 'active-shelf' : ''}" data-collection="${c.id}">🗂️ ${esc(c.name)}</button>`;
      })
      .join('');

    const templateOpts = templates.map((t) => `<option value="${t.slug}">${esc(t.name)}</option>`).join('');

    main.innerHTML = `
      <div class="detail">
        <div>
          <a class="back-link" id="back">${esc(t('detail.library'))}</a>
          <div class="detail-titlebar">
            <input class="detail-title" id="title" value="${esc(m.title)}" aria-label="Title" />
            <div class="detail-actions">
              ${badge(m.status)}
              <button class="btn-ghost" data-fav>${esc(m.favorite ? t('detail.favorited') : t('detail.favorite'))}</button>
              <button class="btn-ghost" data-archive>${esc(m.archived ? t('detail.unarchive') : t('detail.archive'))}</button>
              <button class="btn-ghost danger" data-delete>${esc(t('detail.delete'))}</button>
            </div>
          </div>
          <p class="detail-meta">${new Date(m.created_at).toLocaleString()}${m.duration_seconds ? ' · ' + fmtDuration(m.duration_seconds) : ''}${m.language ? ' · ' + m.language : ''}${m.original_filename ? ' · ' + esc(m.original_filename) : ''}</p>
        </div>

        <div class="audio-mock">
          <button data-play title="${esc(t('demo.audioPlay'))}">▶</button>
          <div class="audio-track"><span></span></div>
          <span class="audio-time">0:00 / ${clock(m.duration_seconds)}</span>
        </div>

        <section class="card">
          <div class="card-head">
            <h3 class="section-title">${esc(t('detail.tagsCollections'))}</h3>
            <div class="export-links">${exportLinks}</div>
          </div>
          <div style="margin-top:0.75rem;display:flex;flex-wrap:wrap;gap:0.5rem;align-items:center">
            ${m.tags.map((tag) => `<button class="chip" data-remove-tag="${tag.id}" title="${esc(t('detail.removeTag'))}" style="cursor:pointer">#${esc(tag.name)} ×</button>`).join('')}
            <input class="input" id="tag-input" placeholder="${esc(t('detail.addTag'))}" style="width:8rem;padding:0.3rem 0.6rem;font-size:0.8rem" />
          </div>
          <div style="margin-top:0.75rem;display:flex;flex-wrap:wrap;gap:0.5rem;align-items:center">
            ${collectionBtns || `<span class="muted">${esc(t('detail.noCollections'))}</span>`}
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <h3 class="section-title">${esc(t('detail.summaries'))}</h3>
            <div style="display:flex;gap:0.5rem;align-items:center">
              <select class="select" id="tmpl">${templateOpts}</select>
              <button class="btn-primary" id="gen"${m.transcript ? '' : ' disabled'}>${esc(t('detail.generate'))}</button>
            </div>
          </div>
          <div id="summaries">
            ${m.summaries.length === 0
              ? `<p class="muted" style="margin-top:0.75rem">${esc(t('detail.noSummaries'))}</p>`
              : m.summaries.map((s) => `
                <div class="summary-block">
                  <p class="kicker">${esc(s.template_name)} · ${esc(s.model)}</p>
                  <p class="body">${esc(s.content)}</p>
                </div>`).join('')}
          </div>
        </section>

        <section class="card">
          <h3 class="section-title">${esc(t('detail.transcript'))}</h3>
          ${m.transcript ? `<p class="transcript">${esc(m.transcript)}</p>` : `<p class="muted" style="margin-top:0.75rem">${esc(t('detail.transcriptPending'))}</p>`}
        </section>

        <section class="card">
          <div class="card-head">
            <h3 class="section-title">${esc(t('detail.askTitle'))}</h3>
            ${m.chat_messages.length ? `<button class="btn-ghost" id="clear-chat">${esc(t('detail.clearConversation'))}</button>` : ''}
          </div>
          <div class="chat-log" id="chat-log">
            ${m.chat_messages.map((c) => `<div class="bubble ${c.role}">${esc(c.content)}</div>`).join('')}
          </div>
          <form class="chat-form" id="chat-form">
            <input class="input" id="chat-input" placeholder="${esc(m.transcript ? t('detail.chatReady') : t('detail.chatWaiting'))}"${m.transcript ? '' : ' disabled'} />
            <button class="btn-primary" type="submit"${m.transcript ? '' : ' disabled'}>${esc(t('detail.ask'))}</button>
          </form>
        </section>
      </div>`;
  }

  function renderTimeline() {
    const buckets = {};
    mathoms.forEach((m) => {
      const key = m.created_at.slice(0, 7);
      buckets[key] = (buckets[key] || 0) + 1;
    });
    const rows = Object.entries(buckets).sort((a, b) => b[0].localeCompare(a[0]));
    const max = Math.max(1, ...rows.map((r) => r[1]));
    const label = (k) => {
      const [y, mo] = k.split('-').map(Number);
      return new Date(y, mo - 1, 1).toLocaleDateString(undefined, { year: 'numeric', month: 'long' });
    };
    main.innerHTML = `
      <h2 class="font-display" style="font-size:1.5rem;margin:0">${esc(t('timeline.title'))}</h2>
      <p class="muted" style="margin-top:0.25rem">${esc(t('timeline.subtitle'))}</p>
      <div style="margin-top:1.5rem">
        ${rows.length === 0 ? `<p class="muted">${esc(t('timeline.empty'))}</p>` : ''}
        ${rows.map(([k, n]) => `
          <div class="timeline-row">
            <span class="label">${label(k)}</span>
            <div class="timeline-bar"><span style="width:${Math.max(8, (n / max) * 100)}%">${n}</span></div>
          </div>`).join('')}
      </div>`;
  }

  function renderTemplates() {
    main.innerHTML = `
      <h2 class="font-display" style="font-size:1.5rem;margin:0">${esc(t('templates.title'))}</h2>
      <p class="muted" style="margin-top:0.25rem">${esc(t('templates.subtitle'))}</p>
      <div class="list">
        ${templates.map((tmpl) => `
          <div class="card">
            <h3>${esc(tmpl.name)} <span class="slug">${esc(tmpl.slug)}</span></h3>
            <p>${esc(tmpl.description)}</p>
          </div>`).join('')}
      </div>`;
  }

  function renderCollections() {
    main.innerHTML = `
      <h2 class="font-display" style="font-size:1.5rem;margin:0">${esc(t('collections.title'))}</h2>
      <p class="muted" style="margin-top:0.25rem">${esc(t('collections.subtitle'))}</p>
      <div class="list">
        ${collections.map((c) => {
          const items = mathoms.filter((m) => m.collections.some((x) => x.id === c.id));
          return `<div class="card">
            <h3>🗂️ ${esc(c.name)}</h3>
            <p>${esc(c.description)}</p>
            <p class="muted" style="margin-top:0.5rem">${esc(t('collections.count', { count: items.length }))}: ${items.map((m) => esc(m.title)).join(', ') || '—'}</p>
          </div>`;
        }).join('')}
      </div>`;
  }

  function render() {
    switch (state.view) {
      case 'library': return renderLibrary();
      case 'timeline': return renderTimeline();
      case 'templates': return renderTemplates();
      case 'collections': return renderCollections();
      default: return renderLibrary();
    }
  }

  // ----- upload simulation --------------------------------------------------
  const SAMPLE_UPLOADS = [
    { title: 'Voice note — grocery plan', transcript: 'Quick note: we’re out of coffee and olive oil. Try that new bakery on the corner. Plan meals around what’s in the freezer this week so we waste less. Pick up a birthday card for Sam.' },
    { title: 'Idea while walking', transcript: 'Had a thought on the walk — what if the archive suggested “on this day” memories, gently, once a week? Not naggy. Just a small doorway back into something you’d forgotten you kept.' },
  ];

  function simulateUpload() {
    const sample = SAMPLE_UPLOADS[Math.floor(Math.random() * SAMPLE_UPLOADS.length)];
    const m = mkMathom({
      id: nextId(), title: sample.title, status: 'pending',
      duration_seconds: 60 + Math.floor(Math.random() * 120),
      created_at: new Date().toISOString(),
      original_filename: 'new-recording.m4a', transcript: null, language: 'en',
    });
    mathoms.unshift(m);
    state.view = 'library'; state.query = ''; state.shelf = 'all'; state.tag = null;
    render();
    toast(t('demo.toast.added'));

    const steps = [
      [900, () => { m.status = 'transcribing'; }],
      [1600, () => { m.status = 'summarizing'; m.transcript = sample.transcript; }],
      [1500, () => {
        m.status = 'ready';
        m.summaries = [{ id: nextId(), template_slug: 'tldr', template_name: 'TL;DR', model: 'llama3.2', content: generateSummary(m, 'tldr') }];
        toast(t('demo.toast.ready', { title: m.title }));
      }],
    ];
    let delay = 0;
    steps.forEach(([d, fn]) => {
      delay += d;
      setTimeout(() => {
        fn();
        if (state.view === 'library') renderLibrary();
        if (state.view === undefined) {}
      }, delay);
    });
  }

  // ----- global event delegation -------------------------------------------
  document.addEventListener('click', (e) => {
    const nav = e.target.closest('#nav a');
    if (nav) { e.preventDefault(); setView(nav.dataset.view); return; }

    const shelf = e.target.closest('[data-shelf]');
    if (shelf) { state.shelf = shelf.dataset.shelf; renderLibrary(); return; }

    const tag = e.target.closest('[data-tag]');
    if (tag) { state.tag = state.tag === tag.dataset.tag ? null : tag.dataset.tag; renderLibrary(); return; }

    const open = e.target.closest('[data-open]');
    if (open) { state.currentId = Number(open.dataset.open); state.view = 'detail'; $$('#nav a').forEach((a) => a.classList.remove('active')); renderDetail(); return; }

    if (e.target.closest('#new-mathom')) { simulateUpload(); return; }
    if (e.target.closest('#back')) { setView('library'); return; }

    const m = mathoms.find((x) => x.id === state.currentId);
    if (!m) return;

    if (e.target.closest('[data-fav]')) { m.favorite = !m.favorite; renderDetail(); toast(t(m.favorite ? 'demo.toast.favorited' : 'demo.toast.unfavorited')); return; }
    if (e.target.closest('[data-archive]')) { m.archived = !m.archived; renderDetail(); toast(t(m.archived ? 'demo.toast.archived' : 'demo.toast.unarchived')); return; }
    if (e.target.closest('[data-delete]')) {
      if (window.confirm(t('demo.confirmDelete'))) {
        const i = mathoms.indexOf(m); mathoms.splice(i, 1); setView('library'); toast(t('demo.toast.deleted'));
      }
      return;
    }
    if (e.target.closest('[data-play]')) { toast(t('demo.toast.playback')); return; }

    const exp = e.target.closest('[data-export]');
    if (exp) { toast(t('demo.toast.export', { format: exp.dataset.export.toUpperCase() })); return; }

    const rmTag = e.target.closest('[data-remove-tag]');
    if (rmTag) { m.tags = m.tags.filter((t) => t.id !== Number(rmTag.dataset.removeTag)); renderDetail(); return; }

    const col = e.target.closest('[data-collection]');
    if (col) {
      const id = Number(col.dataset.collection);
      const c = collections.find((x) => x.id === id);
      const inC = m.collections.some((x) => x.id === id);
      m.collections = inC ? m.collections.filter((x) => x.id !== id) : [...m.collections, { id: c.id, name: c.name }];
      renderDetail();
      return;
    }

    if (e.target.closest('#gen')) {
      const slug = $('#tmpl').value;
      const tmpl = templates.find((t) => t.slug === slug);
      const btn = $('#gen');
      btn.disabled = true; btn.innerHTML = `<span class="spinner"></span> ${esc(t('detail.thinking'))}`;
      setTimeout(() => {
        m.summaries = [
          { id: nextId(), template_slug: slug, template_name: tmpl.name, model: 'llama3.2', content: generateSummary(m, slug) },
          ...m.summaries.filter((s) => s.template_slug !== slug),
        ];
        renderDetail();
        toast(t('demo.toast.summaryGenerated', { name: tmpl.name }));
      }, 1100);
      return;
    }

    if (e.target.closest('#clear-chat')) { m.chat_messages = []; renderDetail(); return; }
  });

  // change (title edit) + submit (tag add, chat) via delegation
  document.addEventListener('change', (e) => {
    if (e.target.id === 'title') {
      const m = mathoms.find((x) => x.id === state.currentId);
      const v = e.target.value.trim();
      if (m && v) { m.title = v; toast(t('demo.toast.titleSaved')); }
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.target.id === 'tag-input' && e.key === 'Enter') {
      e.preventDefault();
      const m = mathoms.find((x) => x.id === state.currentId);
      const v = e.target.value.trim();
      if (m && v) { m.tags = [...m.tags, { id: nextId(), name: v.replace(/^#/, '') }]; renderDetail(); }
    }
  });

  document.addEventListener('submit', (e) => {
    if (e.target.id === 'chat-form') {
      e.preventDefault();
      const input = $('#chat-input');
      const q = input.value.trim();
      const m = mathoms.find((x) => x.id === state.currentId);
      if (!q || !m) return;
      m.chat_messages = [...m.chat_messages, { id: nextId(), role: 'user', content: q }];
      renderDetail();
      const log = $('#chat-log'); if (log) log.scrollTop = log.scrollHeight;
      setTimeout(() => {
        m.chat_messages = [...m.chat_messages, { id: nextId(), role: 'assistant', content: chatReply(m, q) }];
        renderDetail();
        const log2 = $('#chat-log'); if (log2) log2.scrollTop = log2.scrollHeight;
      }, 750);
    }
  });

  // ----- language picker ----------------------------------------------------
  const langSelect = $('#lang-select');
  if (langSelect) {
    langSelect.innerHTML = LANGUAGES.map(
      (l) => `<option value="${l.code}">${esc(l.label)}</option>`,
    ).join('');
    langSelect.value = lang;
    langSelect.addEventListener('change', (e) => setLang(e.target.value));
  }

  // ----- boot ---------------------------------------------------------------
  applyStaticI18n();
  render();
})();
