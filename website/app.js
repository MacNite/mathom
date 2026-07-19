const mathoms = [
  {
    id: 1,
    title: "Product strategy session",
    date: "Today, 10:42",
    duration: 2538,
    durationLabel: "42:18",
    status: "ready",
    favorite: true,
    summary: "The team aligned on onboarding, local semantic search, and a design-partner beta as the next three priorities.",
    tags: ["strategy", "product"]
  },
  {
    id: 2,
    title: "Customer discovery — Northwind",
    date: "Yesterday, 15:20",
    duration: 1924,
    durationLabel: "32:04",
    status: "ready",
    favorite: true,
    summary: "Northwind needs simpler permission controls, repeatable exports, and a clearer migration path for existing notes.",
    tags: ["customer", "research"]
  },
  {
    id: 3,
    title: "Weekly engineering sync",
    date: "Jul 16, 09:00",
    duration: 2849,
    durationLabel: "47:29",
    status: "ready",
    favorite: false,
    summary: "Migration rehearsal is scheduled for Thursday. Two API edge cases remain before the release candidate can be cut.",
    tags: ["engineering", "weekly"]
  },
  {
    id: 4,
    title: "Conference hallway notes",
    date: "Jul 14, 18:35",
    duration: 967,
    durationLabel: "16:07",
    status: "ready",
    favorite: false,
    summary: "A quick collection of ideas around private AI, durable context, and user-owned knowledge infrastructure.",
    tags: ["ideas", "conference"]
  },
  {
    id: 5,
    title: "Q3 planning retrospective",
    date: "Jul 11, 14:15",
    duration: 3612,
    durationLabel: "1:00:12",
    status: "ready",
    favorite: true,
    summary: "The strongest outcomes came from smaller releases and earlier customer feedback. Ownership gaps slowed two initiatives.",
    tags: ["planning", "retro"]
  },
  {
    id: 6,
    title: "Voice note — search concepts",
    date: "Processing now",
    duration: 1180,
    durationLabel: "19:40",
    status: "processing",
    favorite: false,
    summary: "Transcribing locally with faster-whisper…",
    tags: ["voice-note"]
  }
];

let activeFilter = "all";
let activeView = "library";

const grid = document.querySelector("#mathom-grid");
const searchInput = document.querySelector("#demo-search");
const sortSelect = document.querySelector("#sort-select");
const title = document.querySelector("#dashboard-title");
const total = document.querySelector("#stat-total");

function getVisibleMathoms() {
  const query = searchInput.value.trim().toLowerCase();
  let visible = mathoms.filter((item) => {
    const matchesSearch = [item.title, item.summary, ...item.tags]
      .join(" ")
      .toLowerCase()
      .includes(query);

    let matchesFilter = true;
    if (activeFilter === "ready") matchesFilter = item.status === "ready";
    if (activeFilter === "processing") matchesFilter = item.status === "processing";
    if (activeFilter === "favorite") matchesFilter = item.favorite;
    if (activeView === "favorites") matchesFilter = matchesFilter && item.favorite;

    return matchesSearch && matchesFilter;
  });

  if (sortSelect.value === "title") {
    visible.sort((a, b) => a.title.localeCompare(b.title));
  } else if (sortSelect.value === "duration") {
    visible.sort((a, b) => b.duration - a.duration);
  } else {
    visible.sort((a, b) => b.id - a.id);
  }

  return visible;
}

function render() {
  const visible = getVisibleMathoms();
  total.textContent = activeView === "favorites" ? mathoms.filter((item) => item.favorite).length : mathoms.length;

  if (!visible.length) {
    grid.innerHTML = `<div class="empty-state"><strong>No Mathoms found.</strong><br>Try another search or filter.</div>`;
    return;
  }

  grid.innerHTML = visible.map((item) => `
    <article class="mathom-card ${item.status === "processing" ? "processing-card" : ""}">
      <div class="mathom-card-top">
        <span class="mathom-type"><i style="background:${item.status === "processing" ? "#d6a84e" : "#69a775"}"></i>${item.status === "processing" ? "TRANSCRIBING" : "READY"}</span>
        <span>${item.durationLabel}</span>
      </div>
      <h4>${item.title}</h4>
      <p>${item.summary}</p>
      <div class="tags">${item.tags.map((tag) => `<span>#${tag}</span>`).join("")}</div>
      ${item.status === "processing" ? `<div class="processing-bar"><span></span></div>` : ""}
      ${item.favorite ? `<span class="favorite" title="Favorite">★</span>` : ""}
    </article>
  `).join("");
}

document.querySelectorAll("[data-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-filter]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    activeFilter = button.dataset.filter;
    render();
  });
});

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-view]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    activeView = button.dataset.view;
    title.textContent = button.textContent.replace(/[0-9]/g, "").trim();
    render();
  });
});

searchInput.addEventListener("input", render);
sortSelect.addEventListener("change", render);

const menuButton = document.querySelector(".menu-button");
const nav = document.querySelector(".nav");
menuButton.addEventListener("click", () => {
  const open = nav.classList.toggle("open");
  menuButton.setAttribute("aria-expanded", String(open));
});

nav.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => {
  nav.classList.remove("open");
  menuButton.setAttribute("aria-expanded", "false");
}));

document.querySelectorAll(".copy-button").forEach((button) => {
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      const previous = button.textContent;
      button.textContent = "Copied";
      window.setTimeout(() => { button.textContent = previous; }, 1400);
    } catch {
      button.textContent = "Select commands";
    }
  });
});

render();
