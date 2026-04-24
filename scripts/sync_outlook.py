#!/usr/bin/env python3
"""
Pull Liz's Outlook ICS and rewrite the AUTO_SCHEDULE block + today's
AUTO_MEETINGS block in index.html.

Run locally for testing:
    ICS_URL="https://..." python3 scripts/sync_outlook.py
In CI: receives ICS_URL from the workflow env (backed by repo secret).
"""
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from icalendar import Calendar
except ImportError:
    print("ERROR: icalendar not installed. Run: pip install icalendar", file=sys.stderr)
    sys.exit(1)

ICS_URL = os.environ.get("ICS_URL")
if not ICS_URL:
    print("ERROR: ICS_URL env var is required", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX = REPO_ROOT / "index.html"

LOOKAHEAD_DAYS = 21    # how far forward to populate SCHEDULE
EASTERN = ZoneInfo("America/New_York")

# --- classify an event into a tag class based on its summary / categories ---
TAG_RULES = [
    # (regex, tag class, label-fallback)
    (r"\bpurple\s*line\b|\bpl\b",        "tag-pl",       "purple line"),
    (r"\bfmto\b",                         "tag-fmto",     "fmto"),
    (r"\btrwbo\b",                        "tag-trwbo",    "trwbo"),
    (r"\bmamdani\b|\bzm\b",               "tag-mamdani",  "mamdani"),
    (r"\bars\b",                          "tag-ars",      "ars"),
    (r"\bdia\b",                          "tag-dia",      "dia"),
    (r"\bagency\b",                       "tag-agency",   "agency"),
    (r"\bgroundwork\b",                   "tag-gw",       "groundwork"),
    (r"\bcpl\b|\bcivic\s*power\b|\bconvoca\b|\bcivic\s*tech\b", "tag-cpl", "cpl"),
    (r"\bhaircut\b|\byoga\b|\bmed\b|\bpersonal\b", "tag-rt", "self"),
    (r"\btravel\b|\bflight\b|\btrip\b|\brio\b|\bssa\b|\btahoe\b|\bmaine\b", "tag-im", "travel"),
    (r"\bdentist\b|\bdoctor\b|\bappointment\b|\bcolonoscopy\b|\bfasting\b", "tag-im", "family"),
    (r"\bholiday\b|\bmemorial\b|\bjuneteenth\b|\blabor\s*day\b", "tag-im", "holiday"),
    # Meetings are the default when no match.
]
DEEP_WORK_KEYWORDS = re.compile(
    r"\b(purple\s*line|pl|fmto|trwbo|mamdani|zm|ars|dia|agency|groundwork|cpl|civic\s*power|civic\s*tech)\b",
    re.IGNORECASE,
)
FAMILY_KEYWORDS = re.compile(r"\bfamily\s*time\b|\bkids?\b|\bleo\b|\blana\b", re.IGNORECASE)


def classify(summary: str) -> tuple[str, str]:
    """Return (tag_class, label) for a summary."""
    s = summary.lower()
    for pattern, cls, label in TAG_RULES:
        if re.search(pattern, s, re.IGNORECASE):
            return cls, label
    return "tag-plan", "mtg"  # default: admin/meeting grey


def is_meeting(summary: str) -> bool:
    """True if this is a meeting/event (not a deep-work block or family time)."""
    if FAMILY_KEYWORDS.search(summary):
        return False
    # Everything that isn't a recognized deep-work block is treated as a meeting.
    return not DEEP_WORK_KEYWORDS.search(summary)


def format_time(dt, is_all_day: bool) -> str:
    if is_all_day:
        return ""
    return dt.strftime("%H:%M")


def summarize_block(summary: str, start_dt, end_dt, is_all_day: bool) -> str:
    """Human-readable text for a block in the weekly grid."""
    s = summary.strip()
    if is_all_day:
        return s
    if end_dt:
        return f"{s} {start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')}"
    return f"{s} {start_dt.strftime('%H:%M')}"


def fetch_and_parse(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "liz-planner-sync/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    cal = Calendar.from_ical(data)
    today = datetime.now(EASTERN).date()
    end = today + timedelta(days=LOOKAHEAD_DAYS)

    events = []
    for c in cal.walk("VEVENT"):
        dtstart = c.get("DTSTART").dt
        dtend = c.get("DTEND").dt if c.get("DTEND") else None

        is_all_day = not hasattr(dtstart, "hour")
        if is_all_day:
            d = dtstart
            start_dt = None
        else:
            # Convert to Eastern
            if dtstart.tzinfo is None:
                dtstart = dtstart.replace(tzinfo=timezone.utc)
            start_dt = dtstart.astimezone(EASTERN)
            d = start_dt.date()
            if dtend is not None and hasattr(dtend, "hour"):
                if dtend.tzinfo is None:
                    dtend = dtend.replace(tzinfo=timezone.utc)
                dtend = dtend.astimezone(EASTERN)

        if not (today <= d <= end):
            continue

        summary = str(c.get("SUMMARY", "")).strip()
        if not summary:
            continue
        # Skip family-time auto-blocks (Liz said no need)
        if FAMILY_KEYWORDS.search(summary):
            continue

        events.append({
            "date": d,
            "start": start_dt,
            "end": dtend if (dtend and hasattr(dtend, "hour")) else None,
            "summary": summary,
            "all_day": is_all_day,
        })
    events.sort(key=lambda e: (e["date"], e["start"] or datetime.min.replace(tzinfo=EASTERN)))
    return events, today


def build_schedule(events):
    """Group into { 'YYYY-MM-DD': [ {tag, label, text}, ... ] }"""
    schedule = {}
    for e in events:
        key = e["date"].isoformat()
        cls, label = classify(e["summary"])
        text = summarize_block(e["summary"], e["start"], e["end"], e["all_day"])
        schedule.setdefault(key, []).append({"tag": cls, "label": label, "text": text})
    return schedule


def build_today_meetings(events, today):
    """List of dicts for today's meetings (not deep-work blocks) for Today card."""
    out = []
    for e in events:
        if e["date"] != today:
            continue
        if not is_meeting(e["summary"]):
            continue
        if e["all_day"]:
            continue  # all-day 'blocks' are not meetings
        cls, _label = classify(e["summary"])
        # For meetings tag-plan is fine; keep original summary + time
        text = f"{e['summary']}"
        if e["start"]:
            text += f" · {e['start'].strftime('%H:%M')}"
            if e["end"]:
                text += f"–{e['end'].strftime('%H:%M')}"
        out.append({"tag": cls if cls != "tag-plan" else "tag-plan", "text": text})
    return out


def render_schedule_js(schedule: dict) -> str:
    lines = ["  const SCHEDULE = {"]
    for key in sorted(schedule.keys()):
        items = schedule[key]
        if not items:
            lines.append(f"    '{key}':[],")
            continue
        parts = []
        for it in items:
            # escape single-quotes in text
            text = it["text"].replace("\\", "\\\\").replace("'", "\\'")
            label = it["label"].replace("\\", "\\\\").replace("'", "\\'")
            parts.append(f"{{tag:'{it['tag']}',label:'{label}',text:'{text}'}}")
        lines.append(f"    '{key}':[{','.join(parts)}],")
    lines.append("  };")
    return "\n".join(lines)


def render_today_meetings_html(meetings: list) -> str:
    if not meetings:
        return '        <li><label><em style="color:var(--sumi-dim);font-family:\'Fraunces\',serif">No meetings today.</em></label></li>'
    out = []
    for i, m in enumerate(meetings, start=1):
        mid = f"t-mtg-{i}"
        # simple HTML escape
        text = m["text"].replace("&", "&amp;").replace("<", "&lt;")
        out.append(
            f'        <li><input type="checkbox" id="{mid}" data-group="meetings"><label for="{mid}"><span class="tag {m["tag"]}">mtg</span>{text}</label></li>'
        )
    return "\n".join(out)


def replace_between(text: str, start_marker: str, end_marker: str, new_block: str) -> str:
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL,
    )
    replacement = start_marker + "\n" + new_block + "\n  " + end_marker.lstrip("/ ")
    # For HTML-style markers we need a different approach: keep exact markers.
    return pattern.sub(lambda _m: start_marker + "\n" + new_block + "\n" + _end_indent(end_marker) + end_marker, text, count=1)


def _end_indent(end_marker: str) -> str:
    # Put the end marker at the same indent as it appears in the source (best-effort).
    if end_marker.startswith("  //"):
        return "  "
    if end_marker.startswith("<!--"):
        return "        "
    return ""


def patch_file(path: Path):
    original = path.read_text()
    events, today = fetch_and_parse(ICS_URL)
    schedule = build_schedule(events)
    today_meetings = build_today_meetings(events, today)

    # 1) Replace SCHEDULE block (JS markers)
    schedule_js = render_schedule_js(schedule)
    patched = replace_between(
        original,
        "// AUTO_SCHEDULE_START",
        "// AUTO_SCHEDULE_END",
        schedule_js,
    )

    # 2) Replace Meetings list (HTML markers)
    meetings_html = render_today_meetings_html(today_meetings)
    patched = replace_between(
        patched,
        "<!-- AUTO_MEETINGS_START -->",
        "<!-- AUTO_MEETINGS_END -->",
        meetings_html,
    )

    if patched == original:
        print("No changes.")
        return False
    path.write_text(patched)
    print(f"Patched {path.name}: {len(schedule)} scheduled days, {len(today_meetings)} meetings today.")
    return True


if __name__ == "__main__":
    changed = patch_file(INDEX)
    sys.exit(0 if changed or not os.environ.get("CI") else 0)
