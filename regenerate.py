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


def main() -> None:
    data = build_status()
    (ROOT / "status.json").write_text(json.dumps(data, indent=2) + "\n")
    (ROOT / "index.html").write_text(render_html(data))
    print(f"Updated {ROOT/'status.json'} and {ROOT/'index.html'} at {data['updatedAt']}")
    for b in data["bots"]:
        print(f"  [{b['dot']:6}] {b['name']}: {b['status']} | {b.get('lastActive')}")


if __name__ == "__main__":
    main()
