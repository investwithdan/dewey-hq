#!/usr/bin/env python3
"""Dragon Ball–inspired interactive Bot Gym renderer (private preview ready).

render_gym_dbz_html(data) returns a full HTML page that:
- bootstraps from embedded status JSON
- refreshes from status.json every 60s when served over HTTP
- shows Active/Today/Idle visual reactions, filters, detail modal, demo pulse
Does NOT write published gym.html — call from build_interactive_preview.py.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DOT_CLASS = {"green": "active", "yellow": "today", "gray": "idle"}
DOT_LABEL = {"green": "Active", "yellow": "Today", "gray": "Idle"}
SECTION_META = [
    ("command", "Command"),
    ("re", "Real Estate"),
    ("cards", "CardStreet"),
    ("other", "Other"),
]

DEFAULT_META = {
    "53f3e608-ff80-4a27-a2e5-6ca4c5d76cbf": {
        "role": "Chief of Staff · HQ command & coordination",
        "image": "gym-dbz-assets/king-dewey-ss4.jpg",
        "section": "command",
        "king": True,
    },
    "55f1b729-da04-47da-b27f-1c8cc08b3a46": {
        "role": "RE Coach · strategy & deal coaching",
        "image": "gym-dbz-assets/re-ace.jpg",
        "section": "re",
    },
    "b6beb697-de17-4ba0-b353-2ed82b45c43a": {
        "role": "Lead Scout · code enforcement & list pulls",
        "image": "gym-dbz-assets/re-lead-source.jpg",
        "section": "re",
    },
    "a1d4100a-852a-4f24-ad57-070bfe7a7a93": {
        "role": "Inbox Keeper · email triage & cleanup",
        "image": "gym-dbz-assets/re-inbox-keeper.jpg",
        "section": "re",
    },
    "bf460238-110f-4b15-9d78-129e13e45697": {
        "role": "Contracts · novation playbooks & paperwork",
        "image": "gym-dbz-assets/re-novations-nick.jpg",
        "section": "re",
    },
    "2f7735f3-fd5e-4b03-b43c-8f637125a72d": {
        "role": "RE Marketing · brand & outreach creative",
        "image": "gym-dbz-assets/re-marketing.jpg",
        "section": "re",
    },
    "02b5177a-0569-45b3-b698-caa30965aeb5": {
        "role": "Card Ops · operations & workflow",
        "image": "gym-dbz-assets/cs-ops.jpg",
        "section": "cards",
    },
    "bf5ee880-1cb7-4221-ab93-647206ff84c5": {
        "role": "Whatnot Seller · live shows & playbooks",
        "image": "gym-dbz-assets/cs-whatnot-seller.jpg",
        "section": "cards",
    },
    "d38fbbd9-f01d-4208-b0f9-17509cd52309": {
        "role": "Inventory · stock tracking & pulls",
        "image": "gym-dbz-assets/cs-inventory.jpg",
        "section": "cards",
    },
    "eb5d43c1-39cc-4920-8fd1-4f37ccd38478": {
        "role": "Market Scout · comps & price intel",
        "image": "gym-dbz-assets/cs-market-scout.jpg",
        "section": "cards",
    },
    "77ce1314-1724-4cf5-939c-51acdaefd207": {
        "role": "Card Branding · logos & creative",
        "image": "gym-dbz-assets/cs-marketing.jpg",
        "section": "cards",
    },
    "1c983104-eff1-4875-997e-3e053bb6059a": {
        "role": "Crypto Research · charts & alerts",
        "image": "gym-dbz-assets/memecoin-king.jpg",
        "section": "other",
    },
    "5330e1eb-ac0c-42e5-9fdf-b30e5554d441": {
        "role": "Resale Scout · price comps & deals",
        "image": "gym-dbz-assets/resale-scout.jpg",
        "section": "other",
    },
}


def load_meta() -> dict:
    path = ROOT / "bots-meta.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return DEFAULT_META


def _e(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def readiness_for(dot: str) -> str:
    if dot == "green":
        return "On a job now"
    if dot == "yellow":
        return "Worked earlier today — standing by for the next job"
    return "Standing by — ready for the next job"


def enrich_bots(data: dict, meta: dict) -> list[dict]:
    out = []
    for bot in data.get("bots", []):
        m = meta.get(bot.get("id"), {})
        dot = bot.get("dot") if bot.get("dot") in DOT_CLASS else "gray"
        out.append(
            {
                **bot,
                "dot": dot,
                "state": DOT_CLASS[dot],
                "stateLabel": DOT_LABEL[dot],
                "role": m.get("role") or bot.get("business") or "",
                "image": m.get("image") or "",
                "section": m.get("section")
                or {"chief": "command", "re": "re", "cards": "cards"}.get(
                    bot.get("group"), "other"
                ),
                "king": bool(m.get("king") or bot.get("theme") == "crown"),
                "readiness": readiness_for(dot),
            }
        )
    return out


CSS = r"""
:root {
  color-scheme: dark;
  --bg: #0b0d12;
  --bg-elev: #12151d;
  --bg-card: #161a24;
  --bg-card-hover: #1b2030;
  --border: rgba(255,255,255,.08);
  --border-strong: rgba(255,255,255,.14);
  --text: #e8ecf5;
  --muted: #9aa3b5;
  --faint: #6b7385;
  --gold: #e0b84e;
  --green: #3dd68c;
  --yellow: #f0c14a;
  --gray: #8b93a7;
  --re: #5b8def;
  --cards: #f0a35e;
  --other: #a78bfa;
  --command: #e0b84e;
  --radius: 18px;
  --shadow: 0 18px 40px rgba(0,0,0,.45);
  --font: "Segoe UI", "Inter", system-ui, -apple-system, sans-serif;
}
* { box-sizing: border-box; }
html { background: var(--bg); }
body {
  margin: 0;
  font-family: var(--font);
  color: var(--text);
  background:
    radial-gradient(1200px 600px at 10% -10%, rgba(224,184,78,.08), transparent 60%),
    radial-gradient(900px 500px at 90% 0%, rgba(91,141,239,.07), transparent 55%),
    var(--bg);
  min-block-size: 100dvb;
  line-height: 1.45;
}
button { font: inherit; color: inherit; cursor: pointer; }
.preview-banner {
  position: sticky; top: 0; z-index: 50;
  display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: .75rem;
  padding: .7rem 1rem;
  background: linear-gradient(90deg, #3a2a0a, #5a4010 40%, #3a2a0a);
  border-bottom: 1px solid rgba(224,184,78,.35);
  color: #ffe9a8;
  font-size: .85rem; font-weight: 600; letter-spacing: .04em;
  text-transform: uppercase;
}
.preview-banner span {
  display: inline-flex; align-items: center; gap: .4rem;
  background: rgba(0,0,0,.35); padding: .2rem .55rem; border-radius: 999px;
  font-size: .72rem; text-transform: none; letter-spacing: .02em; font-weight: 600;
}
.wrap {
  width: min(1180px, 100% - 2rem);
  margin-inline: auto;
  padding-block: 1.75rem 3.5rem;
}
.hero {
  display: grid; gap: 1rem;
  margin-bottom: 1.25rem;
  padding: 1.5rem 1.6rem;
  background: linear-gradient(160deg, #1a1f2c, #12151d 70%);
  border: 1px solid var(--border-strong);
  border-radius: 22px;
  box-shadow: var(--shadow);
}
.hero-top {
  display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 1rem;
}
.eyebrow {
  color: var(--gold); font-size: .75rem; font-weight: 700;
  letter-spacing: .14em; text-transform: uppercase; margin: 0 0 .35rem;
}
h1 {
  margin: 0; font-size: clamp(1.7rem, 3vw, 2.35rem); font-weight: 750;
  letter-spacing: -.02em;
}
.subtitle { margin: .45rem 0 0; color: var(--muted); max-inline-size: 42rem; }
.meta { display: flex; flex-wrap: wrap; gap: .6rem; }
.pill {
  display: inline-flex; align-items: center; gap: .45rem;
  padding: .4rem .75rem; border-radius: 999px;
  background: rgba(255,255,255,.04); border: 1px solid var(--border);
  color: var(--muted); font-size: .8rem;
}
.pill strong { color: var(--text); font-weight: 650; }
.scoreboard {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: .75rem;
}
@media (max-width: 640px) {
  .scoreboard { grid-template-columns: 1fr; }
}
.sb-cell {
  padding: .85rem 1rem;
  border-radius: 14px;
  background: rgba(0,0,0,.28);
  border: 1px solid var(--border);
}
.sb-num { font-size: 1.55rem; font-weight: 800; letter-spacing: .04em; }
.sb-num.working { color: var(--green); }
.sb-num.break { color: var(--yellow); }
.sb-num.updated { color: var(--gold); font-size: 1.05rem; }
.sb-lbl {
  margin-top: .2rem; color: var(--faint); font-size: .72rem;
  letter-spacing: .08em; text-transform: uppercase; font-weight: 700;
}
.sb-sub { margin-top: .15rem; color: var(--muted); font-size: .78rem; }
.toolbar {
  display: flex; flex-wrap: wrap; align-items: center; gap: .65rem;
  margin: 0 0 1.5rem;
}
.filters { display: flex; flex-wrap: wrap; gap: .5rem; flex: 1; }
.chip {
  border: 1px solid var(--border);
  background: rgba(255,255,255,.04);
  border-radius: 999px;
  padding: .45rem .85rem;
  font-size: .82rem; font-weight: 650;
  color: var(--muted);
}
.chip[aria-pressed="true"] {
  color: var(--text);
  border-color: rgba(224,184,78,.45);
  background: rgba(224,184,78,.14);
  box-shadow: 0 0 0 1px rgba(224,184,78,.15);
}
.demo-btn {
  border: 1px dashed rgba(61,214,140,.45);
  background: rgba(61,214,140,.08);
  color: #b8f5d4;
  border-radius: 999px;
  padding: .45rem .9rem;
  font-size: .8rem; font-weight: 700;
}
.demo-btn:disabled { opacity: .55; cursor: default; }
.demo-note { color: var(--faint); font-size: .75rem; width: 100%; }
.legend { display: flex; flex-wrap: wrap; gap: .75rem; margin-top: .15rem; }
.legend span { display: inline-flex; align-items: center; gap: .4rem; color: var(--muted); font-size: .8rem; }
.dot {
  width: .55rem; height: .55rem; border-radius: 50%; display: inline-block;
  box-shadow: 0 0 0 3px rgba(255,255,255,.06);
}
.dot.active, .badge.active .dot { background: var(--green); box-shadow: 0 0 10px rgba(61,214,140,.55); }
.dot.today, .badge.today .dot { background: var(--yellow); box-shadow: 0 0 10px rgba(240,193,74,.55); }
.dot.idle, .badge.idle .dot { background: var(--gray); }
.section { margin-block: 2rem; }
.section[hidden] { display: none !important; }
.section-head {
  display: flex; align-items: baseline; gap: .75rem;
  margin-bottom: 1rem; padding-inline: .15rem;
}
.section-head h2 {
  margin: 0; font-size: 1.05rem; font-weight: 700;
  letter-spacing: .08em; text-transform: uppercase;
}
.section.command .section-head h2 { color: var(--command); }
.section.re .section-head h2 { color: var(--re); }
.section.cards .section-head h2 { color: var(--cards); }
.section.other .section-head h2 { color: var(--other); }
.count {
  color: var(--faint); font-size: .8rem; font-weight: 600;
  padding: .15rem .5rem; border-radius: 999px; border: 1px solid var(--border);
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
  gap: 1.1rem;
}
.section.command .grid { grid-template-columns: minmax(0, 1fr); }
@media (min-width: 900px) {
  .section.command .grid { grid-template-columns: minmax(320px, 420px) 1fr; }
  .section.command .card {
    display: grid; grid-template-columns: 200px 1fr; align-items: stretch;
  }
  .section.command .portrait { min-block-size: 100%; aspect-ratio: auto; }
}
.card {
  display: flex; flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: clip;
  box-shadow: 0 10px 28px rgba(0,0,0,.28);
  transition: border-color .2s ease, transform .2s ease, background .2s ease, filter .25s ease, box-shadow .25s ease;
  text-align: left;
  padding: 0;
  width: 100%;
}
.card:hover, .card:focus-visible {
  border-color: var(--border-strong);
  background: var(--bg-card-hover);
  transform: translateY(-2px);
  outline: none;
}
.card.king {
  border-color: rgba(224,184,78,.35);
  box-shadow: 0 14px 36px rgba(224,184,78,.12), 0 10px 28px rgba(0,0,0,.35);
}
.card.today {
  outline: 1px solid rgba(240,193,74,.35);
  box-shadow: 0 0 0 1px rgba(240,193,74,.18), 0 10px 28px rgba(0,0,0,.28);
}
.card.active {
  outline: 1px solid rgba(61,214,140,.4);
  box-shadow: 0 0 24px rgba(61,214,140,.22), 0 10px 28px rgba(0,0,0,.28);
}
.card.idle .portrait img {
  filter: saturate(.45) brightness(.85);
}
.card.today .portrait img { filter: saturate(.9) brightness(1); }
.card.active .portrait img { filter: none; }
.card.active .portrait::before {
  content: "";
  position: absolute; inset: -8%;
  background: radial-gradient(circle at 50% 60%, rgba(61,214,140,.35), transparent 55%);
  animation: aura-pulse 1.6s ease-in-out infinite;
  pointer-events: none; z-index: 1;
}
.card.today .portrait::before {
  content: "";
  position: absolute; inset: -6%;
  background: radial-gradient(circle at 50% 55%, rgba(240,193,74,.22), transparent 55%);
  pointer-events: none; z-index: 1;
}
@keyframes aura-pulse {
  0%, 100% { opacity: .55; transform: scale(.98); }
  50% { opacity: 1; transform: scale(1.03); }
}
@media (prefers-reduced-motion: reduce) {
  .card.active .portrait::before { animation: none; opacity: .75; }
  .card { transition: none; }
}
.portrait {
  position: relative;
  aspect-ratio: 3 / 4;
  background: #0a0c11;
  overflow: hidden;
}
.portrait::after {
  content: "";
  position: absolute; inset: auto 0 0 0; height: 35%;
  background: linear-gradient(to top, var(--bg-card), transparent);
  pointer-events: none; z-index: 2;
}
.portrait img {
  display: block; width: 100%; height: 100%;
  object-fit: cover; object-position: center 18%;
  transition: filter .25s ease;
}
.badge {
  position: absolute; top: .75rem; left: .75rem; z-index: 3;
  display: inline-flex; align-items: center; gap: .4rem;
  padding: .35rem .65rem; border-radius: 999px;
  background: rgba(10,12,17,.78); backdrop-filter: blur(8px);
  border: 1px solid var(--border-strong);
  font-size: .72rem; font-weight: 700; letter-spacing: .06em;
  text-transform: uppercase; color: var(--text);
}
.body {
  display: grid; gap: .55rem;
  padding: 1rem 1.05rem 1.15rem;
  flex: 1;
}
.body header h3 {
  margin: 0; font-size: 1.05rem; font-weight: 750; letter-spacing: -.01em;
}
.role { margin: .25rem 0 0; color: var(--text); font-size: .82rem; font-weight: 600; }
.biz { margin: .15rem 0 0; color: var(--faint); font-size: .75rem; }
.status { margin: 0; color: var(--muted); font-size: .9rem; min-block-size: 2.8em; }
.readiness {
  margin: 0; font-size: .78rem; font-weight: 700; letter-spacing: .02em;
}
.card.active .readiness { color: var(--green); }
.card.today .readiness { color: var(--yellow); }
.card.idle .readiness { color: #9eb0d0; }
.card-foot {
  margin-top: auto; padding-top: .35rem;
  border-top: 1px solid var(--border);
  color: var(--faint); font-size: .72rem; letter-spacing: .02em;
  display: flex; justify-content: space-between; gap: .5rem;
}
.tap-hint { color: var(--gold); font-weight: 650; opacity: .85; }
.footnote {
  margin-top: 2.5rem; text-align: center; color: var(--faint); font-size: .78rem;
}
.modal-backdrop {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(4,6,10,.72);
  display: grid; place-items: end center;
  padding: 1rem;
}
@media (min-width: 720px) {
  .modal-backdrop { place-items: center; }
}
.modal-backdrop[hidden] { display: none !important; }
.modal {
  width: min(520px, 100%);
  max-height: min(90dvb, 720px);
  overflow: auto;
  background: #141821;
  border: 1px solid var(--border-strong);
  border-radius: 20px;
  box-shadow: 0 24px 60px rgba(0,0,0,.55);
  padding: 0;
}
.modal-hero {
  position: relative;
  aspect-ratio: 16 / 10;
  background: #0a0c11;
  overflow: hidden;
}
.modal-hero img {
  width: 100%; height: 100%; object-fit: cover; object-position: center 20%;
}
.modal.active .modal-hero img { filter: none; }
.modal.idle .modal-hero img { filter: saturate(.45) brightness(.85); }
.modal.today .modal-hero img { filter: saturate(.9); }
.modal-body { padding: 1.1rem 1.2rem 1.35rem; display: grid; gap: .7rem; }
.modal-top {
  display: flex; justify-content: space-between; gap: .75rem; align-items: flex-start;
}
.modal h2 { margin: 0; font-size: 1.35rem; }
.close-btn {
  border: 1px solid var(--border);
  background: rgba(255,255,255,.05);
  border-radius: 999px;
  width: 2.2rem; height: 2.2rem;
  display: grid; place-items: center;
  font-size: 1.1rem;
}
.modal .status { min-block-size: 0; }
.modal-meta {
  display: grid; gap: .35rem;
  padding: .8rem .9rem;
  border-radius: 12px;
  background: rgba(255,255,255,.03);
  border: 1px solid var(--border);
  font-size: .85rem; color: var(--muted);
}
.modal-meta strong { color: var(--text); }
.refresh-toast {
  position: fixed; bottom: 1rem; left: 50%; transform: translateX(-50%);
  z-index: 80; padding: .45rem .85rem; border-radius: 999px;
  background: rgba(20,24,33,.92); border: 1px solid var(--border-strong);
  color: var(--muted); font-size: .75rem; opacity: 0; pointer-events: none;
  transition: opacity .2s ease;
}
.refresh-toast.show { opacity: 1; }
"""

JS = r"""
(function () {
  const BOOT = window.__GYM_BOOT__ || { bots: [], updatedAt: "" };
  const META = window.__GYM_META__ || {};
  const DOT_CLASS = { green: "active", yellow: "today", gray: "idle" };
  const DOT_LABEL = { green: "Active", yellow: "Today", gray: "Idle" };
  const SECTIONS = [
    ["command", "Command"],
    ["re", "Real Estate"],
    ["cards", "CardStreet"],
    ["other", "Other"],
  ];
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let state = {
    data: BOOT,
    filter: "all",
    demoUntil: 0,
    demoIds: new Set(),
    openId: null,
  };

  const el = {
    boards: document.getElementById("boards"),
    working: document.getElementById("sb-working"),
    break: document.getElementById("sb-break"),
    updated: document.getElementById("sb-updated"),
    updatedSub: document.getElementById("sb-updated-sub"),
    crew: document.getElementById("pill-crew"),
    pillUpdated: document.getElementById("pill-updated"),
    demoBtn: document.getElementById("demo-pulse"),
    demoNote: document.getElementById("demo-note"),
    modal: document.getElementById("modal"),
    backdrop: document.getElementById("modal-backdrop"),
    toast: document.getElementById("refresh-toast"),
  };

  function readiness(dot) {
    if (dot === "green") return "On a job now";
    if (dot === "yellow") return "Worked earlier today — standing by for the next job";
    return "Standing by — ready for the next job";
  }

  function effectiveDot(bot) {
    if (state.demoUntil > Date.now() && state.demoIds.has(bot.id)) return "green";
    return bot.dot && DOT_CLASS[bot.dot] ? bot.dot : "gray";
  }

  function enrich(bot) {
    const m = META[bot.id] || {};
    const dot = effectiveDot(bot);
    const section =
      m.section ||
      ({ chief: "command", re: "re", cards: "cards" }[bot.group] || "other");
    return {
      ...bot,
      dot,
      state: DOT_CLASS[dot],
      stateLabel: DOT_LABEL[dot],
      role: m.role || bot.business || "",
      image: m.image || "",
      section,
      king: !!(m.king || bot.theme === "crown"),
      readiness: readiness(dot),
    };
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function passesFilter(bot) {
    if (state.filter === "all") return true;
    if (state.filter === "working") return bot.dot === "green" || bot.dot === "yellow";
    if (state.filter === "idle") return bot.dot === "gray";
    return true;
  }

  function updateScoreboard(bots) {
    let green = 0, yellow = 0, gray = 0;
    for (const b of bots) {
      if (b.dot === "green") green++;
      else if (b.dot === "yellow") yellow++;
      else gray++;
    }
    el.working.textContent = String(green + yellow).padStart(2, "0");
    el.break.textContent = String(gray).padStart(2, "0");
    el.updated.textContent = state.data.updatedAt || "—";
    el.updatedSub.textContent =
      green + " active · " + yellow + " today · live from status.json";
    el.crew.textContent = String(bots.length);
    el.pillUpdated.innerHTML = "Updated <strong>" + esc(state.data.updatedAt || "—") + "</strong>";
  }

  function cardHtml(bot) {
    const king = bot.king ? " king" : "";
    return (
      '<button type="button" class="card ' +
      bot.state +
      king +
      '" data-id="' +
      esc(bot.id) +
      '" data-state="' +
      bot.state +
      '" aria-label="' +
      esc(bot.name) +
      " — " +
      esc(bot.stateLabel) +
      '">' +
      '<div class="portrait">' +
      '<img src="' +
      esc(bot.image) +
      '" alt="' +
      esc(bot.name) +
      '" width="480" height="640" loading="lazy" />' +
      '<span class="badge ' +
      bot.state +
      '"><i class="dot"></i>' +
      esc(bot.stateLabel) +
      "</span>" +
      "</div>" +
      '<div class="body">' +
      "<header><h3>" +
      esc(bot.name) +
      '</h3><p class="role">' +
      esc(bot.role) +
      '</p><p class="biz">' +
      esc(bot.business || "") +
      "</p></header>" +
      '<p class="status">' +
      esc(bot.status || "") +
      "</p>" +
      '<p class="readiness">' +
      esc(bot.readiness) +
      "</p>" +
      '<div class="card-foot"><span>Last active · ' +
      esc(bot.lastActive || "—") +
      '</span><span class="tap-hint">Tap</span></div>' +
      "</div></button>"
    );
  }

  function render() {
    const bots = (state.data.bots || []).map(enrich);
    updateScoreboard(bots);
    const bySection = {};
    for (const [key] of SECTIONS) bySection[key] = [];
    for (const b of bots) {
      if (!passesFilter(b)) continue;
      (bySection[b.section] || bySection.other).push(b);
    }
    let html = "";
    for (const [key, title] of SECTIONS) {
      const list = bySection[key] || [];
      if (!list.length) {
        html +=
          '<section class="section ' +
          key +
          '" data-section="' +
          key +
          '" hidden><div class="section-head"><h2>' +
          title +
          '</h2><span class="count">0</span></div><div class="grid"></div></section>';
        continue;
      }
      html +=
        '<section class="section ' +
        key +
        '" data-section="' +
        key +
        '"><div class="section-head"><h2>' +
        title +
        '</h2><span class="count">' +
        list.length +
        '</span></div><div class="grid">' +
        list.map(cardHtml).join("") +
        "</div></section>";
    }
    el.boards.innerHTML = html;
    if (state.openId) {
      const still = bots.find((b) => b.id === state.openId);
      if (still) fillModal(still);
      else closeModal();
    }
  }

  function fillModal(bot) {
    el.modal.className = "modal " + bot.state;
    el.modal.innerHTML =
      '<div class="modal-hero"><img src="' +
      esc(bot.image) +
      '" alt="' +
      esc(bot.name) +
      '" /></div>' +
      '<div class="modal-body">' +
      '<div class="modal-top"><div><span class="badge ' +
      bot.state +
      '"><i class="dot"></i>' +
      esc(bot.stateLabel) +
      '</span><h2 id="modal-title" style="margin-top:.55rem">' +
      esc(bot.name) +
      '</h2><p class="role">' +
      esc(bot.role) +
      '</p><p class="biz">' +
      esc(bot.business || "") +
      "</p></div>" +
      '<button type="button" class="close-btn" id="modal-close" aria-label="Close">×</button></div>' +
      '<p class="status">' +
      esc(bot.status || "") +
      "</p>" +
      '<p class="readiness">' +
      esc(bot.readiness) +
      "</p>" +
      '<div class="modal-meta">' +
      "<div>Last active · <strong>" +
      esc(bot.lastActive || "—") +
      "</strong></div>" +
      "<div>Readiness · <strong>" +
      esc(bot.readiness) +
      "</strong></div>" +
      "<div>Source · <strong>status.json</strong> (privacy-filtered)</div>" +
      "</div></div>";
    el.backdrop.hidden = false;
    el.backdrop.setAttribute("aria-hidden", "false");
    document.getElementById("modal-close").focus();
  }

  function openModal(id) {
    const bot = (state.data.bots || []).map(enrich).find((b) => b.id === id);
    if (!bot) return;
    state.openId = id;
    fillModal(bot);
  }

  function closeModal() {
    state.openId = null;
    el.backdrop.hidden = true;
    el.backdrop.setAttribute("aria-hidden", "true");
  }

  function setFilter(next) {
    state.filter = next;
    document.querySelectorAll(".chip").forEach((chip) => {
      chip.setAttribute("aria-pressed", chip.dataset.filter === next ? "true" : "false");
    });
    render();
  }

  function runDemoPulse() {
    const idle = (state.data.bots || []).filter((b) => (b.dot || "gray") === "gray");
    const picks = idle.slice(0, 3).map((b) => b.id);
    if (!picks.length) {
      el.demoNote.textContent = "No idle fighters to demo — everyone already looks busy.";
      return;
    }
    state.demoIds = new Set(picks);
    state.demoUntil = Date.now() + 15000;
    if (el.demoBtn) el.demoBtn.disabled = true;
    el.demoNote.textContent =
      "Demo only — temporarily pulsing " +
      picks.length +
      " idle fighters as Active for 15s. Does not write status.json.";
    render();
    setTimeout(() => {
      state.demoUntil = 0;
      state.demoIds = new Set();
      if (el.demoBtn) el.demoBtn.disabled = false;
      el.demoNote.textContent =
        "Demo pulse finished. Cards are back to real status.json dots.";
      render();
    }, 15000);
  }

  async function refreshFromStatus() {
    try {
      const res = await fetch("status.json?t=" + Date.now(), { cache: "no-store" });
      if (!res.ok) throw new Error("status " + res.status);
      const data = await res.json();
      if (!data || !Array.isArray(data.bots)) throw new Error("bad payload");
      state.data = data;
      render();
      el.toast.textContent = "Refreshed from status.json · " + (data.updatedAt || "");
      el.toast.classList.add("show");
      setTimeout(() => el.toast.classList.remove("show"), 1600);
    } catch (err) {
      // file:// or offline — keep bootstrap; quiet fail
    }
  }

  el.boards.addEventListener("click", (ev) => {
    const card = ev.target.closest(".card");
    if (card) openModal(card.dataset.id);
  });
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => setFilter(chip.dataset.filter));
  });
  if (el.demoBtn) el.demoBtn.addEventListener("click", runDemoPulse);
  el.backdrop.addEventListener("click", (ev) => {
    if (ev.target === el.backdrop) closeModal();
  });
  el.backdrop.addEventListener("click", (ev) => {
    if (ev.target.id === "modal-close" || ev.target.closest("#modal-close")) closeModal();
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") closeModal();
  });

  render();
  refreshFromStatus();
  setInterval(refreshFromStatus, 60000);
  // reduced motion: still refresh text; CSS already disables aura pulse
  void reduceMotion;
})();
"""


def render_gym_dbz_html(data: dict, *, private_preview: bool = True) -> str:
    """Return interactive Dragon Ball–inspired gym HTML for the given status payload."""
    meta = load_meta()
    bots = enrich_bots(data, meta)
    green = sum(1 for b in bots if b["dot"] == "green")
    yellow = sum(1 for b in bots if b["dot"] == "yellow")
    gray = sum(1 for b in bots if b["dot"] == "gray")
    updated = data.get("updatedAt") or "—"

    boot_json = json.dumps(data, ensure_ascii=False)
    meta_json = json.dumps(meta, ensure_ascii=False)

    banner = ""
    demo_block = ""
    robots_meta = '<meta name="robots" content="noindex,nofollow" />\n' if private_preview else ""
    page_title = "Dewey HQ · Bot Gym — PRIVATE INTERACTIVE PREVIEW" if private_preview else "Dewey HQ · Bot Gym"
    footnote = (
        "Private interactive preview · refreshes from status.json every 60s when served · live Dewey HQ unchanged · images in gym-dbz-assets/"
        if private_preview
        else "Statuses refresh with Dewey HQ · privacy-filtered · original characters inspired by Dragon Ball fighter archetypes — not official clones."
    )
    if private_preview:
        banner = """  <div class="preview-banner">
    Private preview — not published
    <span>Interactive · reactive to status.json</span>
    <span>Dragon Ball–inspired</span>
  </div>
"""
        demo_block = """      <button type="button" class="demo-btn" id="demo-pulse">Demo pulse (15s)</button>
      <p class="demo-note" id="demo-note">Private only — flips 2–3 idle cards to Active briefly so you can see the reaction. Does not change status.json.</p>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
{robots_meta}<title>{page_title}</title>
<style>
{CSS}
</style>
</head>
<body>
{banner}  <div class="wrap">
    <header class="hero">
      <div class="hero-top">
        <div>
          <p class="eyebrow">Dewey HQ</p>
          <h1>Bot Gym</h1>
          <p class="subtitle">Dragon Ball–inspired fighter crew · live status · tap a fighter for details. Original characters — not official clones. Status text comes from status.json only.</p>
        </div>
        <div class="meta">
          <div class="pill" id="pill-updated">Updated <strong>{_e(updated)}</strong></div>
          <div class="pill">Crew <strong id="pill-crew">{len(bots)}</strong></div>
        </div>
      </div>
      <div class="scoreboard" aria-label="Gym scoreboard">
        <div class="sb-cell">
          <div class="sb-num working" id="sb-working">{green + yellow:02d}</div>
          <div class="sb-lbl">Working</div>
          <div class="sb-sub">Active + Today</div>
        </div>
        <div class="sb-cell">
          <div class="sb-num break" id="sb-break">{gray:02d}</div>
          <div class="sb-lbl">On break</div>
          <div class="sb-sub">Idle / standing by</div>
        </div>
        <div class="sb-cell">
          <div class="sb-num updated" id="sb-updated">{_e(updated)}</div>
          <div class="sb-lbl">Last updated</div>
          <div class="sb-sub" id="sb-updated-sub">{green} active · {yellow} today · live from status.json</div>
        </div>
      </div>
      <div class="legend">
        <span><i class="dot active"></i> Active — on a job now</span>
        <span><i class="dot today"></i> Today — worked earlier</span>
        <span><i class="dot idle"></i> Idle — ready for the next job</span>
      </div>
    </header>

    <div class="toolbar">
      <div class="filters" role="group" aria-label="Filter fighters">
        <button type="button" class="chip" data-filter="all" aria-pressed="true">All</button>
        <button type="button" class="chip" data-filter="working" aria-pressed="false">Active + Today</button>
        <button type="button" class="chip" data-filter="idle" aria-pressed="false">Idle</button>
      </div>
{demo_block}    </div>

    <div id="boards"></div>
    <p class="footnote">{footnote}</p>
  </div>

  <div class="modal-backdrop" id="modal-backdrop" hidden aria-hidden="true">
    <div class="modal" id="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"></div>
  </div>
  <div class="refresh-toast" id="refresh-toast" role="status"></div>

<script>
window.__GYM_BOOT__ = {boot_json};
window.__GYM_META__ = {meta_json};
{JS}
</script>
</body>
</html>
"""


def write_interactive_preview(data: dict | None = None, path: Path | None = None) -> Path:
    """Write gym-interactive-preview.html without touching published pages."""
    if data is None:
        data = json.loads((ROOT / "status.json").read_text())
    out = path or (ROOT / "gym-interactive-preview.html")
    out.write_text(render_gym_dbz_html(data, private_preview=True))
    return out


if __name__ == "__main__":
    p = write_interactive_preview()
    print(f"Wrote {p}")
