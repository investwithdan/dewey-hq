#!/usr/bin/env python3
"""Regenerate Dewey HQ status.json + index.html from local agent stores.

Honest statuses only — never invents activity. Privacy-filtered.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
AGENTS_ROOT = Path("/home/box/sand-data/agents")
ET = ZoneInfo("America/New_York")

# Privacy: strip emails, phones, street-ish addresses, obvious dollar amounts, credentials-ish tokens
PRIVACY_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?"),
    re.compile(r"\b\d{1,5}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Lane|Ln|Dr|Drive|Ct|Court)\b", re.I),
    re.compile(r"\b(?:password|token|api[_-]?key|secret)\s*[:=]\s*\S+", re.I),
]

SENSITIVE_NAME_HINTS = re.compile(
    r"\b(?:seller|buyer|realtor|customer|client)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"
)


def now_et() -> datetime:
    return datetime.now(tz=ET)


def fmt_et(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.astimezone(ET).strftime("%b %-d, %-I:%M %p ET")


def ms_to_dt(ms: int | float | None) -> datetime | None:
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(ET)


def scrub(text: str) -> str:
    out = text
    for pat in PRIVACY_PATTERNS:
        out = pat.sub("[redacted]", out)
    out = SENSITIVE_NAME_HINTS.sub("[redacted]", out)
    return out


def activity_dot(last_dt: datetime | None, now: datetime) -> str:
    if not last_dt:
        return "gray"
    age = now - last_dt
    if age.total_seconds() <= 3600:
        return "green"
    if last_dt.date() == now.date():
        return "yellow"
    return "gray"


def summarize_entry(entry: dict) -> str | None:
    """One-line general status from a transcript entry. Returns None if unusable."""
    kind = entry.get("kind")
    if kind == "event":
        ev = entry.get("event") or {}
        etype = ev.get("type") or "event"
        if etype == "name-changed":
            return f"Renamed to {ev.get('to') or 'new name'}"
        return f"System event: {etype.replace('-', ' ')}"
    if kind == "message":
        role = entry.get("role") or (entry.get("message") or {}).get("role")
        # Never quote message contents — keep general
        if role == "user":
            return "Received a new user message"
        if role == "assistant":
            return "Sent an assistant reply"
        return "Had a conversation update"
    if kind == "tool" or entry.get("type") == "tool_call":
        return "Ran a tool action"
    return None


def read_agent_activity(agent_id: str, bot_name: str) -> tuple[str, datetime | None]:
    """Return (status, last_active_dt). Never fabricates."""
    d = AGENTS_ROOT / agent_id
    if not d.exists():
        return "No recent activity visible", None

    last_dt: datetime | None = None
    status: str | None = None

    store = d / "store.db"
    if store.exists():
        try:
            con = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
            cur = con.cursor()
            cur.execute(
                "SELECT entry FROM transcript_entries ORDER BY seq DESC LIMIT 20"
            )
            rows = cur.fetchall()
            con.close()
            for (raw,) in rows:
                try:
                    entry = json.loads(raw)
                except Exception:
                    continue
                ts = ms_to_dt(entry.get("timestampMs"))
                if ts and (last_dt is None or ts > last_dt):
                    last_dt = ts
                if status is None:
                    s = summarize_entry(entry)
                    if s:
                        status = scrub(s)
        except Exception:
            pass

    # Active agent on this box = currently in use (gateway / active-agent.json)
    try:
        active = json.loads((AGENTS_ROOT / "active-agent.json").read_text())
        if active.get("activeAgentId") == agent_id:
            # This box is running as this agent right now
            status = "Active on the shared box right now"
            last_dt = now_et()
    except Exception:
        pass

    # Special-case: King Dewey currently building this dashboard (running regenerate)
    # Only set if we are regenerating as part of the live Dewey HQ task AND this is Dewey.
    # Detect via a marker file written by the live build, or if status still empty and
    # Dewey is active — already handled above.

    if not status:
        status = "No recent activity visible"
    return status, last_dt


def load_bots() -> list[dict]:
    return json.loads((ROOT / "bots.json").read_text())


def build_status() -> dict:
    try:
        OVERRIDES = json.loads((ROOT / "overrides.json").read_text())
    except Exception:
        OVERRIDES = {}
    now = now_et()
    bots = load_bots()
    out_bots = []
    for b in bots:
        status, last_dt = read_agent_activity(b["id"], b["name"])
        # If this is King Dewey and we're regenerating the dashboard, prefer that status
        # when active — already set. Optionally refine:
        if b["id"] == "53f3e608-ff80-4a27-a2e5-6ca4c5d76cbf" and (
            status.startswith("Active on the shared box")
            or (ROOT / ".building").exists()
        ):
            status = "Building / updating Dewey HQ status page"
            last_dt = now
        ov = OVERRIDES.get(b["id"])
        if ov:
            status = ov.get("status", status)
            iso = ov.get("lastActiveIso")
            if iso == "NOW":
                last_dt = now
            elif iso:
                last_dt = datetime.fromisoformat(iso).astimezone(ET)
        out_bots.append(
            {
                **b,
                "status": status,
                "lastActive": fmt_et(last_dt) or "Not available",
                "lastActiveIso": last_dt.isoformat() if last_dt else None,
                "dot": activity_dot(last_dt, now),
            }
        )
    return {
        "updatedAt": fmt_et(now),
        "updatedAtIso": now.isoformat(),
        "bots": out_bots,
    }


def card_html(bot: dict) -> str:
    theme = bot.get("theme") or bot.get("group")
    crown = " 👑" if theme == "crown" else ""
    last = bot.get("lastActive") or "Not available"
    return f"""
    <article class="card group-{bot['group']}">
      <div class="card-top">
        <span class="dot {bot['dot']}" title="{bot['dot']}"></span>
        <h3>{bot['name']}{crown}</h3>
      </div>
      <p class="biz">{bot.get('business','')}</p>
      <p class="status">{bot['status']}</p>
      <p class="last">Last active: {last}</p>
    </article>"""


def render_html(data: dict) -> str:
    groups = [
        ("chief", "👑 King Dewey", "section-crown"),
        ("re", "🏡 Real Estate — D F Land Management", "section-re"),
        ("cards", "🃏 FOMO Rips — Cards", "section-cards"),
        ("other", "✨ Other", "section-other"),
    ]
    sections = []
    for key, title, cls in groups:
        cards = [card_html(b) for b in data["bots"] if b["group"] == key]
        if not cards:
            continue
        sections.append(
            f'<section class="section {cls}"><h2>{title}</h2><div class="grid">{"".join(cards)}</div></section>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta http-equiv="refresh" content="300"/>
<title>Dewey HQ — Bot Status</title>
<style>
  :root {{
    --bg: #0b0b0f;
    --text: #f4f4f5;
    --muted: #a1a1aa;
    --card: #16161d;
    --gold: #f5c542;
    --gold-dim: #8a6a12;
    --neon: #39ff14;
    --orange: #ff6b00;
    --yellow: #ffe600;
    --green: #22c55e;
    --amber: #eab308;
    --gray: #6b7280;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: radial-gradient(ellipse at top, #1a1520 0%, var(--bg) 55%);
    color: var(--text);
    min-height: 100vh;
    padding: 20px 16px 48px;
  }}
  header {{
    text-align: center;
    padding: 28px 12px 18px;
  }}
  header h1 {{
    margin: 0;
    font-size: clamp(2rem, 6vw, 3.2rem);
    letter-spacing: 0.04em;
    background: linear-gradient(90deg, #fff 0%, var(--gold) 50%, #fff 100%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }}
  header .sub {{
    margin-top: 8px;
    color: var(--muted);
    font-size: 1.05rem;
  }}
  header .updated {{
    margin-top: 14px;
    display: inline-block;
    padding: 8px 14px;
    border-radius: 999px;
    background: #221f2a;
    border: 1px solid #3f3a4d;
    font-size: 1rem;
  }}
  .legend {{
    display: flex; gap: 16px; justify-content: center; flex-wrap: wrap;
    margin: 18px 0 8px; color: var(--muted); font-size: 0.95rem;
  }}
  .legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
  .section {{
    max-width: 980px;
    margin: 28px auto;
  }}
  .section h2 {{
    font-size: 1.45rem;
    margin: 0 0 14px;
    padding: 10px 14px;
    border-radius: 12px;
  }}
  .section-crown h2 {{
    background: linear-gradient(90deg, #3a2e0a, #1a1508);
    border: 1px solid var(--gold-dim);
    color: var(--gold);
  }}
  .section-re h2 {{
    background: #14110a;
    border: 1px solid #5c4a12;
    color: var(--gold);
  }}
  .section-cards h2 {{
    background: linear-gradient(90deg, #0d1a0a, #1a0f00);
    border: 1px solid #3d5a12;
    color: var(--neon);
    text-shadow: 0 0 8px rgba(57,255,20,0.35);
  }}
  .section-other h2 {{
    background: #14141c;
    border: 1px solid #333;
    color: #c4b5fd;
  }}
  .grid {{
    display: grid;
    grid-template-columns: 1fr;
    gap: 14px;
  }}
  @media (min-width: 720px) {{
    .grid {{ grid-template-columns: 1fr 1fr; }}
  }}
  .card {{
    background: var(--card);
    border-radius: 18px;
    padding: 18px 18px 16px;
    border: 1px solid #2a2a35;
    box-shadow: 0 8px 24px rgba(0,0,0,0.35);
  }}
  .group-chief {{
    border-color: var(--gold-dim);
    background: linear-gradient(160deg, #221c0c 0%, #16161d 60%);
  }}
  .group-re {{
    border-color: #4a3b10;
  }}
  .group-cards {{
    border-color: #2f4a14;
    background: linear-gradient(160deg, #10180e 0%, #1a1208 55%, #16161d 100%);
  }}
  .group-cards .status {{ color: #d9ffc7; }}
  .card-top {{
    display: flex; align-items: center; gap: 12px;
  }}
  .card h3 {{
    margin: 0;
    font-size: 1.35rem;
    line-height: 1.25;
  }}
  .biz {{
    margin: 6px 0 0;
    color: var(--muted);
    font-size: 0.95rem;
  }}
  .status {{
    margin: 14px 0 8px;
    font-size: 1.2rem;
    line-height: 1.35;
    font-weight: 560;
  }}
  .last {{
    margin: 0;
    color: var(--muted);
    font-size: 1rem;
  }}
  .dot {{
    width: 16px; height: 16px; border-radius: 50%;
    flex-shrink: 0;
    box-shadow: 0 0 10px currentColor;
  }}
  .dot.green {{ background: var(--green); color: var(--green); }}
  .dot.yellow {{ background: var(--amber); color: var(--amber); }}
  .dot.gray {{ background: var(--gray); color: var(--gray); box-shadow: none; }}
  .gym-btn {{
    display: inline-block; margin-top: 14px; padding: 12px 22px; border-radius: 999px;
    font-size: 1.1rem; font-weight: 800; text-decoration: none; color: #111;
    background: linear-gradient(180deg, #ffe08a, var(--gold)); border: 2px solid var(--gold-dim);
    box-shadow: 0 4px 0 var(--gold-dim);
  }}
  .gym-btn:active {{ transform: translateY(3px); box-shadow: 0 1px 0 var(--gold-dim); }}
  footer {{
    text-align: center;
    color: var(--muted);
    margin-top: 36px;
    font-size: 0.9rem;
  }}
</style>
</head>
<body>
  <header>
    <h1>👑 Dewey HQ</h1>
    <p class="sub">All Grok Bot assistants — tap once, read the cards</p>
    <div class="updated">Last updated: {data['updatedAt']} · auto-refreshes every 5 min</div>
    <div><a class="gym-btn" href="gym.html">Go to the Gym 🏋️</a></div>
    <div class="legend">
      <span><span class="dot green"></span> Active (last hour)</span>
      <span><span class="dot yellow"></span> Active today</span>
      <span><span class="dot gray"></span> Idle / unknown</span>
    </div>
  </header>
  {''.join(sections)}
  <footer>Statuses are privacy-filtered and only shown when activity can be read. Nothing is invented.</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Dewey HQ Gym — playful animated view built from the same status data
# ---------------------------------------------------------------------------
import html as _html

GYM_PALETTES = {
    # (body, head, limbs/trim)
    "chief": [("#7c3aed", "#f3e8ff", "#5b21b6")],
    "re": [("#1c1c1c", "#f5c542", "#d4a72c"), ("#232323", "#ffd666", "#c9a227"), ("#161616", "#eab84a", "#e0b24a")],
    "cards": [("#39ff14", "#e3ffd6", "#1d8f0a"), ("#ff6b00", "#ffe0c7", "#b84d00"), ("#ffe600", "#fffbd1", "#a69500")],
    "other": [("#a78bfa", "#ede9fe", "#6d28d9"), ("#22d3ee", "#cffafe", "#0e7490")],
}

GYM_ACTIVITIES = {
    "green": [("bench", "LIFTING", "🏋️"), ("treadmill", "CARDIO", "🏃"), ("boxing", "BOXING", "🥊"), ("ropes", "BATTLE ROPES", "🔥")],
    "yellow": [("bike", "EASY SPIN", "🚴"), ("jumprope", "JUMP ROPE", "🪢"), ("curls", "CURLS", "💪")],
    "gray": [("sip", "ON BREAK", "💧"), ("stretch", "ON BREAK", "🧘"), ("nap", "ON BREAK", "💤")],
}


def _e(s) -> str:
    return _html.escape(str(s if s is not None else ""), quote=True)


def _head(x, y, r=19, mood="happy", crown=False, band=False) -> str:
    p = []
    if not crown:
        p.append(f'<line x1="{x}" y1="{y-r+2}" x2="{x}" y2="{y-r-9}" class="ant"/><circle cx="{x}" cy="{y-r-11}" r="4" class="antball"/>')
    p.append(f'<circle cx="{x}" cy="{y}" r="{r}" class="hd"/>')
    vw, vh = r * 1.5, r * 0.9
    p.append(f'<rect x="{x-vw/2:.1f}" y="{y-vh/2-2:.1f}" width="{vw:.1f}" height="{vh:.1f}" rx="{r*0.42:.1f}" class="visor"/>')
    ex, ey = r * 0.33, y - 2
    if mood == "strain":
        p.append(f'<path d="M{x-ex-4:.1f} {ey-4} l6 4 l-6 4 M{x+ex+4:.1f} {ey-4} l-6 4 l6 4" class="eyel"/>')
        p.append(f'<ellipse cx="{x}" cy="{y+r*0.66:.1f}" rx="2.6" ry="3" class="mouthfill"/>')
    elif mood == "sleep":
        p.append(f'<path d="M{x-ex-4:.1f} {ey} q4 4 8 0 M{x+ex-4:.1f} {ey} q4 4 8 0" class="eyel"/>')
        p.append(f'<path d="M{x-3} {y+r*0.66:.1f} q3 2 6 0" class="mouth"/>')
    elif mood == "content":
        p.append(f'<path d="M{x-ex-4:.1f} {ey+2} q4 -6 8 0 M{x+ex-4:.1f} {ey+2} q4 -6 8 0" class="eyel"/>')
        p.append(f'<path d="M{x-4} {y+r*0.6:.1f} q4 4 8 0" class="mouth"/>')
    else:  # happy
        p.append(f'<ellipse cx="{x-ex:.1f}" cy="{ey}" rx="3" ry="4.2" class="eye"/><ellipse cx="{x+ex:.1f}" cy="{ey}" rx="3" ry="4.2" class="eye"/>')
        p.append(f'<path d="M{x-4} {y+r*0.6:.1f} q4 4 8 0" class="mouth"/>')
    p.append(f'<circle cx="{x-r*0.66:.1f}" cy="{y+r*0.5:.1f}" r="3.2" class="blush"/><circle cx="{x+r*0.66:.1f}" cy="{y+r*0.5:.1f}" r="3.2" class="blush"/>')
    if band:
        p.append(f'<line x1="{x-r*0.8:.1f}" y1="{y-r*0.6:.1f}" x2="{x+r*0.8:.1f}" y2="{y-r*0.6:.1f}" class="band"/>'
                 f'<path d="M{x+r*0.8:.1f} {y-r*0.6:.1f} l7 -3 M{x+r*0.8:.1f} {y-r*0.6:.1f} l8 3" class="bandtail"/>')
    if crown:
        w = r * 1.3
        base = y - r + 5
        top = y - r - 13
        pts = f"{x-w/2:.1f},{base:.1f} {x-w/2:.1f},{top+3:.1f} {x-w/4:.1f},{top+9:.1f} {x},{top:.1f} {x+w/4:.1f},{top+9:.1f} {x+w/2:.1f},{top+3:.1f} {x+w/2:.1f},{base:.1f}"
        p.append(f'<g class="crowngrp"><polygon points="{pts}" class="crown"/>'
                 f'<rect x="{x-w/2:.1f}" y="{base-5:.1f}" width="{w:.1f}" height="5" class="crownband"/>'
                 f'<circle cx="{x}" cy="{top+1:.1f}" r="2.6" class="gem-r"/>'
                 f'<circle cx="{x-w/2:.1f}" cy="{top+3:.1f}" r="2.1" class="gem-b"/>'
                 f'<circle cx="{x+w/2:.1f}" cy="{top+3:.1f}" r="2.1" class="gem-b"/>'
                 f'<circle cx="{x}" cy="{base-2.5:.1f}" r="1.8" class="gem-g"/></g>')
    return f'<g class="head">{"".join(p)}</g>'


def _sweat(x, y) -> str:
    out = []
    for i, (dx, dy) in enumerate([(0, 0), (9, 7), (-4, 12)]):
        out.append(f'<path class="anim drop" style="animation-delay:-{i*0.37:.2f}s" d="M{x+dx} {y+dy} c-3 5 -4 8 0 10 c4 -2 3 -5 0 -10z"/>')
    return "".join(out)


_SHADOW = '<ellipse cx="120" cy="158" rx="92" ry="6" class="shadow"/>'


def _scene(kind: str, crown: bool) -> str:
    """Inner SVG for a gym station (viewBox 0 0 240 170)."""
    if kind == "bench":
        return f"""{_SHADOW}
<rect x="40" y="40" width="6" height="118" rx="2" class="metal"/><rect x="194" y="40" width="6" height="118" rx="2" class="metal"/>
<rect x="64" y="122" width="7" height="36" class="metal-d"/><rect x="150" y="122" width="7" height="36" class="metal-d"/>
<rect x="52" y="112" width="116" height="11" rx="5" class="pad"/>
<polyline points="146,104 172,100 178,156" class="lm"/><polyline points="142,110 160,114 160,156" class="lm"/>
<rect x="76" y="92" width="72" height="22" rx="10" class="bd"/>
<g class="anim bp-arms" style="transform-origin:100px 100px"><line x1="96" y1="100" x2="96" y2="58" class="lm"/><line x1="108" y1="100" x2="108" y2="58" class="lm"/></g>
<g class="anim bp-bar">
  <ellipse cx="114" cy="50" rx="9" ry="21" class="plate back"/>
  <line x1="90" y1="58" x2="114" y2="50" class="bar"/>
  <ellipse cx="90" cy="58" rx="10" ry="23" class="plate"/><ellipse cx="90" cy="58" rx="3" ry="6" class="hub"/>
</g>
{_head(60, 102, 17, "strain", crown, band=not crown)}
{_sweat(80, 80)}"""
    if kind == "treadmill":
        return f"""{_SHADOW}
<path d="M34 145 H198 L206 156 H28 Z" class="metal-d"/>
<line x1="36" y1="145" x2="196" y2="145" class="beltbase"/>
<line x1="36" y1="145" x2="196" y2="145" class="anim belt"/>
<line x1="192" y1="145" x2="180" y2="80" class="post"/><line x1="146" y1="100" x2="184" y2="93" class="post thin"/>
<rect x="164" y="64" width="38" height="20" rx="4" class="console"/><text x="183" y="79" class="lcd">8.5</text>
<g class="anim run-bob">
  <g class="anim swing" style="transform-origin:112px 118px;animation-delay:-.28s"><line x1="112" y1="118" x2="112" y2="142" class="lm dim"/></g>
  <g class="anim swing" style="transform-origin:112px 94px"><line x1="112" y1="94" x2="112" y2="116" class="lm dim"/></g>
  <rect x="98" y="82" width="30" height="40" rx="12" class="bd"/>
  <g class="anim swing" style="transform-origin:116px 118px"><line x1="116" y1="118" x2="116" y2="142" class="lm"/></g>
  <g class="anim swing" style="transform-origin:116px 94px;animation-delay:-.28s"><line x1="116" y1="94" x2="116" y2="116" class="lm"/></g>
  {_head(114, 60, 19, "strain", crown, band=not crown)}
  {_sweat(138, 52)}
</g>"""
    if kind == "boxing":
        return f"""{_SHADOW}
<rect x="150" y="2" width="62" height="6" rx="2" class="metal"/>
<g class="anim bag" style="transform-origin:180px 8px">
  <line x1="180" y1="8" x2="180" y2="30" class="chain"/>
  <rect x="164" y="30" width="32" height="84" rx="13" class="bagbody"/>
  <rect x="164" y="42" width="32" height="6" class="bagband"/><rect x="164" y="98" width="32" height="6" class="bagband"/>
</g>
<line x1="94" y1="120" x2="82" y2="156" class="lm"/><line x1="108" y1="120" x2="120" y2="156" class="lm"/>
<rect x="86" y="82" width="30" height="42" rx="12" class="bd"/>
<g class="anim punch" style="animation-delay:-.4s"><line x1="112" y1="104" x2="130" y2="106" class="lm"/><circle cx="136" cy="106" r="8.5" class="glove"/></g>
<g class="anim punch"><line x1="112" y1="94" x2="130" y2="94" class="lm"/><circle cx="137" cy="94" r="8.5" class="glove"/></g>
{_head(101, 60, 19, "strain", crown, band=not crown)}
{_sweat(78, 54)}"""
    if kind == "ropes":
        w1a, w1b = "M120 108 Q134 88 149 110 T178 118 T204 136", "M120 108 Q134 128 149 106 T178 130 T204 136"
        w2a, w2b = "M120 118 Q134 98 149 120 T178 128 T204 140", "M120 118 Q134 138 149 116 T178 138 T204 140"
        return f"""{_SHADOW}
<rect x="200" y="126" width="16" height="32" rx="4" class="metal"/><circle cx="208" cy="134" r="4" class="metal-d"/>
<path d="{w1a}" class="rope"><animate attributeName="d" dur="0.6s" repeatCount="indefinite" values="{w1a};{w1b};{w1a}"/></path>
<path d="{w2a}" class="rope"><animate attributeName="d" dur="0.6s" begin="-0.3s" repeatCount="indefinite" values="{w2a};{w2b};{w2a}"/></path>
<g class="anim squat-bob">
  <polyline points="82,124 70,140 76,156" class="lm"/><polyline points="98,124 110,140 104,156" class="lm"/>
  <rect x="74" y="90" width="32" height="38" rx="12" class="bd"/>
  <line x1="100" y1="98" x2="120" y2="108" class="lm"/><line x1="100" y1="106" x2="120" y2="118" class="lm"/>
  {_head(90, 68, 19, "strain", crown, band=not crown)}
  {_sweat(66, 62)}
</g>"""
    if kind == "bike":
        return f"""{_SHADOW}
<rect x="66" y="150" width="120" height="7" rx="3" class="metal-d"/>
<path d="M92 150 L112 112 L150 112 L168 150" class="frame"/>
<line x1="112" y1="112" x2="106" y2="94" class="frame"/><rect x="92" y="88" width="28" height="7" rx="3" class="pad"/>
<line x1="150" y1="112" x2="160" y2="82" class="frame"/><line x1="152" y1="80" x2="174" y2="80" class="frame"/>
<g class="anim spin" style="transform-origin:170px 134px"><circle cx="170" cy="134" r="16" class="wheel"/>
  <line x1="170" y1="118" x2="170" y2="150" class="spoke"/><line x1="154" y1="134" x2="186" y2="134" class="spoke"/></g>
<line x1="108" y1="86" x2="130" y2="104" class="lm dim"/>
<g class="anim pedal" style="transform-origin:130px 104px;animation-delay:-.9s"><line x1="130" y1="104" x2="128" y2="132" class="lm dim"/></g>
<rect x="94" y="52" width="28" height="38" rx="12" class="bd"/>
<line x1="112" y1="86" x2="134" y2="102" class="lm"/>
<g class="anim pedal" style="transform-origin:134px 102px"><line x1="134" y1="102" x2="132" y2="130" class="lm"/></g>
<line x1="116" y1="62" x2="156" y2="80" class="lm"/>
{_head(110, 34, 17, "happy", crown)}"""
    if kind == "jumprope":
        return f"""{_SHADOW}
<g class="anim hop">
  <path d="M88 112 C82 172, 150 172, 144 112" class="anim jrope" style="transform-origin:116px 112px"/>
  <line x1="110" y1="118" x2="108" y2="146" class="lm"/><line x1="122" y1="118" x2="124" y2="146" class="lm"/>
  <rect x="100" y="80" width="32" height="42" rx="12" class="bd"/>
  <line x1="102" y1="90" x2="88" y2="110" class="lm"/><line x1="130" y1="90" x2="144" y2="110" class="lm"/>
  <rect x="84" y="106" width="8" height="12" rx="2" class="handle"/><rect x="140" y="106" width="8" height="12" rx="2" class="handle"/>
  {_head(116, 58, 19, "happy", crown)}
</g>"""
    if kind == "curls":
        db = lambda x, y: (f'<line x1="{x-9}" y1="{y}" x2="{x+9}" y2="{y}" class="bar"/>'
                           f'<rect x="{x-13}" y="{y-6}" width="6" height="12" rx="1.5" class="dbw"/><rect x="{x+7}" y="{y-6}" width="6" height="12" rx="1.5" class="dbw"/>')
        return f"""{_SHADOW}
<line x1="108" y1="120" x2="102" y2="156" class="lm"/><line x1="124" y1="120" x2="130" y2="156" class="lm"/>
<rect x="98" y="80" width="36" height="42" rx="12" class="bd"/>
<line x1="100" y1="90" x2="88" y2="112" class="lm"/><line x1="132" y1="90" x2="144" y2="112" class="lm"/>
<g class="anim curl-l" style="transform-origin:88px 112px"><line x1="88" y1="112" x2="88" y2="134" class="lm"/>{db(88, 138)}</g>
<g class="anim curl-r" style="transform-origin:144px 112px"><line x1="144" y1="112" x2="144" y2="134" class="lm"/>{db(144, 138)}</g>
{_head(116, 58, 19, "happy", crown)}"""
    if kind == "sip":
        return f"""{_SHADOW}
<rect x="52" y="120" width="136" height="10" rx="4" class="pad"/>
<rect x="62" y="130" width="7" height="28" class="metal-d"/><rect x="172" y="130" width="7" height="28" class="metal-d"/>
<line x1="108" y1="122" x2="104" y2="154" class="lm"/><line x1="126" y1="122" x2="130" y2="154" class="lm"/>
<rect x="100" y="80" width="34" height="44" rx="12" class="bd"/>
<line x1="102" y1="92" x2="96" y2="118" class="lm"/>
<path d="M98 86 Q104 74 116 80 L111 114 Q104 116 98 112 Z" class="towel"/><path d="M99 104 L111 106 M98.5 108 L110.5 110" class="towelstripe"/>
<line x1="132" y1="92" x2="146" y2="108" class="lm"/>
{_head(117, 58, 19, "content", crown)}
<g class="anim sip" style="transform-origin:146px 108px">
  <line x1="146" y1="108" x2="148" y2="92" class="lm"/>
  <rect x="143" y="66" width="11" height="26" rx="3" class="bottle"/><rect x="145" y="61" width="7" height="6" rx="1.5" class="cap"/>
  <circle cx="148" cy="92" r="5" class="hand"/>
</g>"""
    if kind == "stretch":
        return f"""{_SHADOW}
<g class="anim lean" style="transform-origin:116px 156px">
  <line x1="110" y1="120" x2="102" y2="156" class="lm"/><line x1="122" y1="120" x2="130" y2="156" class="lm"/>
  <rect x="100" y="80" width="32" height="42" rx="12" class="bd"/>
  <line x1="102" y1="88" x2="80" y2="44" class="lm"/><line x1="130" y1="88" x2="152" y2="44" class="lm"/>
  <circle cx="79" cy="42" r="5.5" class="hand"/><circle cx="153" cy="42" r="5.5" class="hand"/>
  {_head(116, 62, 19, "content", crown)}
</g>
<rect x="166" y="144" width="40" height="12" rx="3" class="towel"/><line x1="166" y1="150" x2="206" y2="150" class="towelstripe"/>
<rect x="40" y="128" width="12" height="28" rx="3" class="bottle"/><rect x="42" y="123" width="8" height="6" rx="1.5" class="cap"/>"""
    if kind == "nap":
        return f"""{_SHADOW}
<rect x="26" y="146" width="188" height="10" rx="5" class="yogamat"/>
<rect x="198" y="120" width="11" height="26" rx="3" class="bottle"/><rect x="200" y="115" width="7" height="6" rx="1.5" class="cap"/>
<line x1="142" y1="134" x2="184" y2="138" class="lm"/><line x1="142" y1="140" x2="182" y2="146" class="lm"/>
<g class="anim breathe" style="transform-origin:110px 146px"><rect x="78" y="122" width="66" height="24" rx="11" class="bd"/>
<path d="M96 120 L124 120 L126 148 L94 148 Z" class="towel"/></g>
<line x1="96" y1="132" x2="118" y2="142" class="lm"/>
<g transform="rotate(-14 62 128)">{_head(62, 128, 17, "sleep", crown)}</g>
<text x="80" y="98" class="anim zzz" style="font-size:14px">Z</text>
<text x="80" y="98" class="anim zzz" style="font-size:18px;animation-delay:-1s">Z</text>
<text x="80" y="98" class="anim zzz" style="font-size:22px;animation-delay:-2s">Z</text>"""
    return ""


def gym_station(bot: dict, kind: str, label: str, emoji: str, palette: tuple) -> str:
    body, head, limbs = palette
    crown = (bot.get("theme") == "crown") or bot.get("group") == "chief"
    dot = bot.get("dot") or "gray"
    name = _e(bot["name"])
    king = " king" if bot.get("group") == "chief" else ""
    tag_text = label if dot != "gray" else f"ON BREAK"
    sub = {"bench": "bench press", "treadmill": "treadmill sprint", "boxing": "heavy bag", "ropes": "rope slams",
           "bike": "stationary bike", "jumprope": "jump rope", "curls": "dumbbell curls",
           "sip": "hydrating", "stretch": "stretching", "nap": "power nap"}[kind]
    return f"""
    <article class="station dot-{dot} zone-{_e(bot['group'])}{king}" style="--c:{body};--h:{head};--l:{limbs}">
      <div class="scene-wrap">
        <span class="tag tag-{dot}">{emoji} {tag_text}</span>
        <svg class="scene" viewBox="0 0 240 170" role="img" aria-label="{name}: {sub}">{_scene(kind, crown)}</svg>
      </div>
      <div class="info">
        <h3><span class="ldot {dot}"></span>{name}{' 👑' if crown else ''}</h3>
        <p class="biz">{_e(bot.get('business', ''))} · <span class="doing">{sub}</span></p>
        <p class="status">{_e(bot.get('status', ''))}</p>
        <p class="last">⏱ Last active: {_e(bot.get('lastActive') or 'Not available')}</p>
      </div>
    </article>"""


GYM_CSS = r"""
:root { --gold:#f5c542; --neon:#39ff14; --orange:#ff6b00; --yellow:#ffe600; --text:#f4f4f5; --muted:#b4b4bd; }
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; color: var(--text); min-height: 100vh; padding: 18px 16px 48px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background-color: #141518;
  background-image:
    radial-gradient(rgba(255,255,255,.045) 1px, transparent 1.4px),
    radial-gradient(rgba(0,0,0,.45) 1px, transparent 1.4px),
    linear-gradient(90deg, rgba(0,0,0,.55) 3px, transparent 3px),
    linear-gradient(rgba(0,0,0,.55) 3px, transparent 3px),
    radial-gradient(ellipse at 50% 0%, rgba(255,255,255,.06), transparent 60%);
  background-size: 7px 7px, 11px 11px, 180px 180px, 180px 180px, 100% 100%;
  background-position: 0 0, 4px 6px, -2px 0, 0 -2px, 0 0;
}
.wrap { max-width: 1000px; margin: 0 auto; }
/* ---------- scoreboard ---------- */
.scoreboard {
  position: relative; margin: 4px auto 18px; padding: 18px 18px 16px; border-radius: 20px;
  background: linear-gradient(180deg, #2b2e35, #1a1c21); border: 3px solid #3d414b;
  box-shadow: 0 14px 40px rgba(0,0,0,.6), inset 0 1px 0 rgba(255,255,255,.08);
}
.scoreboard::before, .scoreboard::after {
  content: ""; position: absolute; top: 10px; width: 10px; height: 10px; border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #9aa0aa, #444 70%);
}
.scoreboard::before { left: 10px; } .scoreboard::after { right: 10px; }
.sb-title {
  text-align: center; font-weight: 900; letter-spacing: .08em; text-transform: uppercase;
  font-size: clamp(2rem, 7vw, 3.4rem); line-height: 1.05; margin: 2px 0 14px;
  color: #fff; text-shadow: 0 3px 0 #000, 0 0 18px rgba(245,197,66,.45);
}
.sb-title .gold { color: var(--gold); }
.sb-panel { display: grid; grid-template-columns: 1fr 1fr 1.5fr; gap: 12px; }
.sb-cell {
  background: #07080a; border-radius: 14px; padding: 12px 10px 10px; text-align: center; border: 2px solid #23262d;
  background-image: radial-gradient(rgba(255,255,255,.05) 1px, transparent 1.3px); background-size: 5px 5px;
}
.sb-num { font-family: "Courier New", ui-monospace, Menlo, monospace; font-weight: 900; font-size: clamp(2.8rem, 9vw, 4.4rem); line-height: 1; }
.sb-time { font-family: "Courier New", ui-monospace, Menlo, monospace; font-weight: 900; font-size: clamp(1.8rem, 5.6vw, 2.8rem); line-height: 1.15; color: #ff5a3c; text-shadow: 0 0 12px rgba(255,90,60,.7); padding-top: 8px; }
.led-green { color: #4dff6a; text-shadow: 0 0 14px rgba(77,255,106,.75); }
.led-amber { color: #ffb02e; text-shadow: 0 0 14px rgba(255,176,46,.7); }
.sb-lbl { margin-top: 8px; font-weight: 800; letter-spacing: .12em; font-size: .95rem; color: #e5e7eb; }
.sb-sub { margin-top: 4px; font-size: .9rem; color: var(--muted); }
.nav { display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; margin-top: 14px; }
.btn {
  display: inline-flex; align-items: center; gap: 8px; padding: 12px 20px; border-radius: 999px; font-size: 1.1rem; font-weight: 800;
  color: #111; background: linear-gradient(180deg, #ffe08a, #f5c542); text-decoration: none; border: 2px solid #8a6a12;
  box-shadow: 0 4px 0 #8a6a12;
}
.btn:active { transform: translateY(3px); box-shadow: 0 1px 0 #8a6a12; }
.legend { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px 18px; margin: 4px 0 6px; color: var(--muted); font-size: 1rem; }
.legend b { color: #fff; }
/* ---------- zones ---------- */
.zone { margin: 26px 0; padding: 16px; border-radius: 22px; position: relative; }
.zone h2 { margin: 0 0 14px; font-size: clamp(1.5rem, 4.4vw, 2rem); line-height: 1.15; }
.zone-grid { display: grid; grid-template-columns: 1fr; gap: 16px; }
@media (min-width: 700px) { .zone-grid { grid-template-columns: 1fr 1fr; } }
.zone-chief-wrap { background: linear-gradient(135deg, rgba(124,58,237,.28), rgba(245,197,66,.14)); border: 2px solid #8a6a12; }
.zone-chief-wrap h2 { color: var(--gold); text-shadow: 0 2px 0 #000; }
.zone-re-wrap { background: rgba(10,10,10,.75); border: 2px solid #5c4a12; padding-top: 26px; overflow: hidden; }
.zone-re-wrap::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 12px; background: repeating-linear-gradient(45deg, var(--gold) 0 14px, #0b0b0b 14px 28px); }
.zone-re-wrap h2 { color: var(--gold); text-transform: uppercase; letter-spacing: .06em; font-weight: 900; }
.zone-cards-wrap {
  border: 2px solid #2f4a14; overflow: hidden;
  background:
    radial-gradient(circle at 8% 12%, rgba(57,255,20,.20), transparent 22%),
    radial-gradient(circle at 92% 8%, rgba(255,107,0,.22), transparent 24%),
    radial-gradient(circle at 70% 95%, rgba(255,230,0,.14), transparent 26%),
    radial-gradient(circle at 20% 90%, rgba(255,107,0,.12), transparent 20%),
    #0e120c;
}
.zone-cards-wrap h2 {
  display: inline-block; transform: rotate(-2deg); font-weight: 900; text-transform: uppercase; letter-spacing: .03em;
  font-family: "Marker Felt", "Chalkboard SE", "Comic Sans MS", "Segoe Print", Impact, sans-serif;
  color: var(--neon); text-shadow: 3px 3px 0 var(--orange), 6px 6px 0 rgba(0,0,0,.6), 0 0 18px rgba(57,255,20,.6);
}
.zone-cards-wrap h2 .y { color: var(--yellow); } .zone-cards-wrap h2 .o { color: var(--orange); text-shadow: 3px 3px 0 var(--neon), 6px 6px 0 rgba(0,0,0,.6); }
.zone-other-wrap { background: rgba(30,27,46,.6); border: 2px solid #3b3557; }
.zone-other-wrap h2 { color: #c4b5fd; }
/* ---------- stations ---------- */
.station {
  background: linear-gradient(180deg, #1d2027, #16181d); border-radius: 20px; overflow: hidden;
  border: 2px solid #30343d; box-shadow: 0 10px 26px rgba(0,0,0,.45);
}
.zone-re .station, .station.zone-re { border-color: #6b5615; }
.station.zone-cards { border-color: #2f5a14; }
.station.zone-cards:nth-child(3n+2) { border-color: #7a3a0a; }
.station.zone-cards:nth-child(3n) { border-color: #6f6510; }
.station.king { border-color: #c9a227; }
@media (min-width: 700px) { .station.king { grid-column: 1 / -1; display: grid; grid-template-columns: 1.05fr 1fr; align-items: center; } }
.scene-wrap { position: relative; background: linear-gradient(180deg, #23262e 0 74%, #2b2f37 74% 100%); }
.scene { display: block; width: 100%; height: auto; }
.tag {
  position: absolute; top: 10px; left: 10px; z-index: 2; padding: 6px 12px; border-radius: 10px;
  font-weight: 900; letter-spacing: .08em; font-size: .95rem; color: #0b0b0b; box-shadow: 0 3px 0 rgba(0,0,0,.45);
}
.tag-green { background: #4ade80; } .tag-yellow { background: #facc15; } .tag-gray { background: #cbd5e1; }
.info { padding: 12px 16px 16px; }
.info h3 { margin: 0; font-size: 1.4rem; line-height: 1.2; display: flex; align-items: center; gap: 10px; }
.ldot { width: 16px; height: 16px; border-radius: 50%; flex-shrink: 0; }
.ldot.green { background: #22c55e; box-shadow: 0 0 10px #22c55e; } .ldot.yellow { background: #eab308; box-shadow: 0 0 10px #eab308; } .ldot.gray { background: #6b7280; }
.biz { margin: 6px 0 0; color: var(--muted); font-size: 1rem; }
.doing { color: #e5e7eb; font-weight: 700; }
.status { margin: 10px 0 8px; font-size: 1.15rem; line-height: 1.38; font-weight: 560; }
.zone-cards .status { color: #e2ffd6; }
.last { margin: 0; color: var(--muted); font-size: 1rem; }
footer { text-align: center; color: var(--muted); margin-top: 30px; font-size: .95rem; }
@keyframes cheer { 0%,100% { transform: scale(1); } 40% { transform: scale(1.03) rotate(-.6deg); } 70% { transform: scale(.99); } }
.station { cursor: pointer; -webkit-tap-highlight-color: transparent; }
.station.cheer { animation: cheer .45s ease-out; }
@media (prefers-reduced-motion: reduce) { .station.cheer { animation: none; } }
/* ---------- svg parts ---------- */
.scene .bd { fill: var(--c); stroke: var(--l); stroke-width: 2.5; }
.scene .hd { fill: var(--h); stroke: rgba(0,0,0,.35); stroke-width: 2; }
.scene .lm { stroke: var(--l); stroke-width: 9; stroke-linecap: round; stroke-linejoin: round; fill: none; }
.scene .lm.dim { opacity: .65; }
.scene .visor { fill: #15161d; }
.scene .eye { fill: #7df9ff; }
.scene .eyel { stroke: #7df9ff; stroke-width: 2.4; fill: none; stroke-linecap: round; stroke-linejoin: round; }
.scene .mouth { stroke: #3b2a1a; stroke-width: 2; fill: none; stroke-linecap: round; }
.scene .mouthfill { fill: #3b2a1a; }
.scene .blush { fill: #fb7185; opacity: .55; }
.scene .ant { stroke: #9ca3af; stroke-width: 3; }
.scene .antball { fill: var(--l); stroke: #000; stroke-opacity: .3; }
.scene .band { stroke: #ef4444; stroke-width: 5; stroke-linecap: round; }
.scene .bandtail { stroke: #ef4444; stroke-width: 3; stroke-linecap: round; fill: none; }
.scene .crown { fill: #f5c542; stroke: #8a6a12; stroke-width: 1.5; stroke-linejoin: round; }
.scene .crownband { fill: #d4a017; }
.scene .gem-r { fill: #ef4444; } .scene .gem-b { fill: #60a5fa; } .scene .gem-g { fill: #34d399; }
.scene .shadow { fill: rgba(0,0,0,.45); }
.scene .metal { fill: #6b7280; } .scene .metal-d { fill: #343842; }
.scene .pad { fill: #3f4350; stroke: #5b6170; stroke-width: 1.5; }
.scene .plate { fill: #1b1c21; stroke: #ef4444; stroke-width: 4; } .scene .plate.back { stroke: #991b1b; }
.scene .hub { fill: #9ca3af; }
.scene .bar { stroke: #d1d5db; stroke-width: 4; stroke-linecap: round; }
.scene .drop { fill: #7dd3fc; }
.scene .beltbase { stroke: #0c0d10; stroke-width: 6; }
.scene .belt { stroke: #4b5060; stroke-width: 2; stroke-dasharray: 8 10; }
.scene .post { stroke: #4b5563; stroke-width: 6; stroke-linecap: round; } .scene .post.thin { stroke-width: 4; }
.scene .console { fill: #0f1115; stroke: #4b5563; stroke-width: 2; }
.scene .lcd { fill: #4dff6a; font: 700 12px "Courier New", monospace; text-anchor: middle; }
.scene .chain { stroke: #9ca3af; stroke-width: 2.5; stroke-dasharray: 3 2; }
.scene .bagbody { fill: #b91c1c; stroke: #7f1d1d; stroke-width: 2; } .scene .bagband { fill: #7f1d1d; }
.scene .glove { fill: #ef4444; stroke: #7f1d1d; stroke-width: 2; }
.scene .rope { stroke: #d6b36b; stroke-width: 5; fill: none; stroke-linecap: round; }
.scene .frame { stroke: #6b7280; stroke-width: 6; fill: none; stroke-linecap: round; stroke-linejoin: round; }
.scene .wheel { fill: #1f2937; stroke: #9ca3af; stroke-width: 3; } .scene .spoke { stroke: #9ca3af; stroke-width: 2; }
.scene .jrope { stroke: #f472b6; stroke-width: 3; fill: none; }
.scene .handle { fill: #f472b6; }
.scene .dbw { fill: #374151; stroke: #9ca3af; stroke-width: 1; }
.scene .towel { fill: #f8fafc; stroke: #94a3b8; stroke-width: 1.5; }
.scene .towelstripe { stroke: #3b82f6; stroke-width: 2.5; fill: none; }
.scene .hand { fill: var(--l); }
.scene .bottle { fill: rgba(56,189,248,.75); stroke: #0ea5e9; stroke-width: 1.5; } .scene .cap { fill: #0ea5e9; }
.scene .yogamat { fill: #1e3a8a; stroke: #3b82f6; stroke-width: 1.5; }
.scene .zzz { fill: #c4b5fd; font-weight: 900; font-family: "Comic Sans MS", "Chalkboard SE", sans-serif; }
/* ---------- animations ---------- */
.anim { transform-box: view-box; }
@keyframes bp-bar { 0%,100% { transform: translateY(0); } 50% { transform: translateY(18px); } }
@keyframes bp-arms { 0%,100% { transform: scaleY(1); } 50% { transform: scaleY(.57); } }
.bp-bar { animation: bp-bar 1.5s ease-in-out infinite; }
.bp-arms { animation: bp-arms 1.5s ease-in-out infinite; }
@keyframes swing { 0%,100% { transform: rotate(-32deg); } 50% { transform: rotate(32deg); } }
.swing { animation: swing .56s ease-in-out infinite; }
@keyframes run-bob { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }
.run-bob { animation: run-bob .28s ease-in-out infinite; }
@keyframes belt { to { stroke-dashoffset: 18; } }
.belt { animation: belt .25s linear infinite; }
@keyframes punch { 0%,50%,100% { transform: translateX(0); } 22% { transform: translateX(17px); } }
.punch { animation: punch .8s ease-out infinite; }
@keyframes bag { 0%,100% { transform: rotate(0); } 30% { transform: rotate(5deg); } 65% { transform: rotate(-2deg); } }
.bag { animation: bag .4s ease-in-out infinite; }
@keyframes squat-bob { 0%,100% { transform: translateY(0); } 50% { transform: translateY(3px); } }
.squat-bob { animation: squat-bob .3s ease-in-out infinite; }
@keyframes drip { 0% { transform: translateY(0); opacity: 0; } 15% { opacity: 1; } 100% { transform: translateY(16px); opacity: 0; } }
.drop { animation: drip 1.1s ease-in infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.spin { animation: spin 1.8s linear infinite; }
@keyframes pedal { 0%,100% { transform: rotate(-24deg); } 50% { transform: rotate(20deg); } }
.pedal { animation: pedal 1.8s ease-in-out infinite; }
@keyframes hop { 0%,100% { transform: translateY(-12px); } 50% { transform: translateY(0); } }
.hop { animation: hop 1.1s ease-in-out infinite; }
@keyframes jrope { 0%,100% { transform: scaleY(1); } 50% { transform: scaleY(-1.9); } }
.jrope { animation: jrope 1.1s linear infinite; }
@keyframes curl-l { 0%,100% { transform: rotate(0); } 50% { transform: rotate(-135deg); } }
@keyframes curl-r { 0%,100% { transform: rotate(0); } 50% { transform: rotate(135deg); } }
.curl-l { animation: curl-l 2.6s ease-in-out infinite; }
.curl-r { animation: curl-r 2.6s ease-in-out infinite; animation-delay: -1.3s; }
@keyframes sip { 0%,50%,100% { transform: rotate(0); } 62%,86% { transform: rotate(-36deg); } }
.sip { animation: sip 5s ease-in-out infinite; }
@keyframes lean { 0%,100% { transform: rotate(-9deg); } 50% { transform: rotate(9deg); } }
.lean { animation: lean 5s ease-in-out infinite; }
@keyframes breathe { 0%,100% { transform: scaleY(1); } 50% { transform: scaleY(1.07); } }
.breathe { animation: breathe 3.6s ease-in-out infinite; }
@keyframes zzz { 0% { transform: translate(0,0); opacity: 0; } 15% { opacity: 1; } 100% { transform: translate(26px,-70px); opacity: 0; } }
.zzz { animation: zzz 3s ease-out infinite; }
@media (prefers-reduced-motion: reduce) {
  .scene, .scene * { animation: none !important; }
  .zzz:nth-of-type(2) { transform: translate(12px,-30px); } .zzz:nth-of-type(3) { transform: translate(24px,-60px); }
}
@media (max-width: 560px) { .sb-panel { grid-template-columns: 1fr 1fr; } .sb-cell.wide { grid-column: 1 / -1; } }
"""

GYM_JS = r"""
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce) { document.querySelectorAll('svg.scene').forEach(function (s) { if (s.pauseAnimations) s.pauseAnimations(); }); }
  var left = 300, el = document.getElementById('cd');
  if (el) setInterval(function () { left = Math.max(0, left - 1); el.textContent = Math.floor(left / 60) + ':' + ('0' + (left % 60)).slice(-2); }, 1000);
  document.querySelectorAll('.station').forEach(function (st) {
    st.addEventListener('click', function () { st.classList.remove('cheer'); void st.offsetWidth; st.classList.add('cheer'); });
  });
})();
"""


def render_gym_html(data: dict) -> str:
    bots = data["bots"]
    counters = {"green": 0, "yellow": 0, "gray": 0}
    pal_idx = {k: 0 for k in GYM_PALETTES}
    stations: dict[str, list[str]] = {}
    for b in bots:
        dot = b.get("dot") if b.get("dot") in counters else "gray"
        opts = GYM_ACTIVITIES[dot]
        kind, label, emoji = opts[counters[dot] % len(opts)]
        counters[dot] += 1
        grp = b.get("group") if b.get("group") in GYM_PALETTES else "other"
        pals = GYM_PALETTES[grp]
        pal = pals[pal_idx[grp] % len(pals)]
        pal_idx[grp] += 1
        stations.setdefault(grp, []).append(gym_station(b, kind, label, emoji, pal))

    zones = [
        ("chief", "👑 King's Corner", ""),
        ("re", "🏛️ Real Estate Iron Zone", ""),
        ("cards", 'FOMO <span class="y">Rips</span> <span class="o">Cardio Deck</span> ⚡', ""),
        ("other", "✨ Other", ""),
    ]
    zone_html = []
    for key, title, _ in zones:
        if not stations.get(key):
            continue
        zone_html.append(f'<section class="zone zone-{key}-wrap zone-{key}"><h2>{title}</h2><div class="zone-grid">{"".join(stations[key])}</div></section>')

    working_hard = counters["green"]
    working_light = counters["yellow"]
    on_break = counters["gray"]
    try:
        upd = datetime.fromisoformat(data["updatedAtIso"]).astimezone(ET)
        upd_time = upd.strftime("%-I:%M %p")
        upd_date = upd.strftime("%a %b %-d") + " · ET"
    except Exception:
        upd_time, upd_date = _e(data.get("updatedAt", "")), ""

    page = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta http-equiv="refresh" content="300"/>
<meta name="apple-mobile-web-app-capable" content="yes"/>
<title>Dewey HQ Gym — Bot Status</title>
<style>__CSS__</style>
</head>
<body>
<div class="wrap">
  <header class="scoreboard">
    <div class="sb-title">🏋️ Dewey HQ <span class="gold">Gym</span></div>
    <div class="sb-panel">
      <div class="sb-cell"><div class="sb-num led-green">__WORK__</div><div class="sb-lbl">WORKING OUT</div><div class="sb-sub">__HARD__ going hard · __LIGHT__ light</div></div>
      <div class="sb-cell"><div class="sb-num led-amber">__BREAK__</div><div class="sb-lbl">ON BREAK</div><div class="sb-sub">idle / waiting</div></div>
      <div class="sb-cell wide"><div class="sb-time">__TIME__</div><div class="sb-lbl">LAST UPDATED</div><div class="sb-sub">__DATE__ · refresh in <span id="cd">5:00</span></div></div>
    </div>
    <nav class="nav"><a class="btn" href="index.html">📋 Classic view</a></nav>
  </header>
  <div class="legend">
    <span>🔥 <b>Going hard</b> = active in the last hour</span>
    <span>🚴 <b>Light work</b> = active earlier today</span>
    <span>💤 <b>On break</b> = idle / waiting</span>
  </div>
  __ZONES__
  <footer>Same data as the classic view, refreshed together. Statuses are privacy-filtered; nothing is invented.</footer>
</div>
<script>__JS__</script>
</body>
</html>
"""
    return (page.replace("__CSS__", GYM_CSS)
            .replace("__JS__", GYM_JS)
            .replace("__WORK__", f"{working_hard + working_light:02d}")
            .replace("__HARD__", str(working_hard))
            .replace("__LIGHT__", str(working_light))
            .replace("__BREAK__", f"{on_break:02d}")
            .replace("__TIME__", upd_time)
            .replace("__DATE__", upd_date)
            .replace("__ZONES__", "\n".join(zone_html)))



def main() -> None:
    data = build_status()
    (ROOT / "status.json").write_text(json.dumps(data, indent=2) + "\n")
    (ROOT / "index.html").write_text(render_html(data))
    (ROOT / "gym.html").write_text(render_gym_html(data))
    print(f"Updated {ROOT/'status.json'}, {ROOT/'index.html'} and {ROOT/'gym.html'} at {data['updatedAt']}")
    for b in data["bots"]:
        print(f"  [{b['dot']:6}] {b['name']}: {b['status']} | {b.get('lastActive')}")


if __name__ == "__main__":
    main()
