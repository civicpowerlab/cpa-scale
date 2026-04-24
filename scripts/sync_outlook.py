#!/usr/bin/env python3
"""
Pull Liz's Outlook ICS and rewrite four marked regions in index.html:
  AUTO_SCHEDULE       - the JS SCHEDULE object used by the weekly grid
  AUTO_TODAY_ROCKS    - today's deep-work items (inside the Deep Work card)
  AUTO_MEETINGS       - today's meetings (has LOCATION or zoom URL)
  AUTO_ADMIN          - today's admin items (no location/zoom, not deep-work)

Classification rules (in order):
  1. Title matches a deep-work project keyword      -> deep work
  2. Title matches "family time"                     -> skip entirely
  3. Has LOCATION or a zoom/meet/teams link         -> meeting
  4. Everything else                                 -> admin
"""
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
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

LOOKAHEAD_DAYS = 21
EASTERN = ZoneInfo("America/New_York")

PROJECT_RULES = [
    (r"\bpurple\s*line\b|\bpl\b",        "tag-pl",      "purple line"),
    (r"\bfmto\b",                         "tag-fmto",    "fmto"),
    (r"\btrwbo\b",                        "tag-trwbo",   "trwbo"),
    (r"\bmamdani\b|\bzm\b",               "tag-mamdani", "mamdani"),
    (r"\bars\b",                          "tag-ars",     "ars"),
    (r"\bdia\b",                          "tag-dia",     "dia"),
    (r"\bagency\s*book\b|\bagency\b",    "tag-agency",  "agency"),
    (r"\bgroundwork\b",                   "tag-gw",      "groundwork"),
    (r"\bcpl\b|\bcivic\s*power\b|\bconvoca\b|\bcivic\s*tech\b",
                                          "tag-cpl",     "civic power lab"),
]
SELF_KEYWORDS = re.compile(r"\bhaircut\b|\byoga\b|\btherapy\b", re.IGNORECASE)
FAMILY_TIME_SKIP = re.compile(r"\bfamily\s*time\b", re.IGNORECASE)
FAMILY_EVENT = re.compile(
    r"\bdentist\b|\bcolonoscopy\b|\bfasting\b|\bdoctor\b|\bappointment\b|\bleo\b|\blana\b|\balexandre\b",
    re.IGNORECASE,
)
TRAVEL_KW = re.compile(
    r"\btravel\b|\bflight\b|\btrip\b|\brio\b|\bssa\b|\btahoe\b|\bmaine\b|\bholiday\b|\bmemorial\b|\bjuneteenth\b|\blabor\s*day\b",
    re.IGNORECASE,
)
REMOTE_MEETING_URL = re.compile(
    r"zoom\.us|meet\.google\.com|teams\.microsoft\.com|webex\.com",
    re.IGNORECASE,
)


def project_match(summary):
    for pattern, cls, label in PROJECT_RULES:
        if re.search(pattern, summary, re.IGNORECASE):
            return cls, label
    return None


def has_location_or_zoom(component, summary):
    loc = str(component.get("LOCATION", "")).strip()
    desc = str(component.get("DESCRIPTION", "")).strip()
    if loc:
        return True
    if REMOTE_MEETING_URL.search(summary + " " + desc):
        return True
    return False


def classify(summary, is_remote_or_located):
    pm = project_match(summary)
    if pm:
        return pm
    if SELF_KEYWORDS.search(summary):
        return "tag-rt", "self"
    if FAMILY_EVENT.search(summary):
        return "tag-im", "family"
    if TRAVEL_KW.search(summary):
        return "tag-im", "travel"
    if is_remote_or_located:
        return "tag-mtg", "mtg"
    return "tag-plan", "admin"


def summarize_block(summary, start_dt, end_dt, is_all_day):
    s = summary.strip()
    if is_all_day:
        return s
    if end_dt:
        return f"{s} {start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"
    return f"{s} {start_dt.strftime('%H:%M')}"


def fetch_and_parse(url):
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
        if FAMILY_TIME_SKIP.search(summary):
            continue

        events.append({
            "date": d,
            "start": start_dt,
            "end": dtend if (dtend and hasattr(dtend, "hour")) else None,
            "summary": summary,
            "all_day": is_all_day,
            "is_remote_or_located": has_location_or_zoom(c, summary),
        })
    events.sort(key=lambda e: (e["date"], e["start"] or datetime.min.replace(tzinfo=EASTERN)))
    return events, today


def build_schedule(events):
    schedule = {}
    for e in events:
        key = e["date"].isoformat()
        cls, label = classify(e["summary"], e["is_remote_or_located"])
        text = summarize_block(e["summary"], e["start"], e["end"], e["all_day"])
        schedule.setdefault(key, []).append({"tag": cls, "label": label, "text": text})
    return schedule


def build_today_buckets(events, today):
    rocks, meetings, admin = [], [], []
    for e in events:
        if e["date"] != today or e["all_day"]:
            continue
        cls, label = classify(e["summary"], e["is_remote_or_located"])
        text = summarize_block(e["summary"], e["start"], e["end"], False)
        item = {"tag": cls, "label": label, "text": text}
        if project_match(e["summary"]):
            rocks.append(item)
        elif cls == "tag-mtg":
            meetings.append(item)
        elif cls in ("tag-im", "tag-rt"):
            if e["is_remote_or_located"]:
                meetings.append(item)
            else:
                admin.append(item)
        else:
            admin.append(item)
    return rocks, meetings, admin


def render_schedule_js(schedule):
    lines = ["  const SCHEDULE = {"]
    for key in sorted(schedule.keys()):
        items = schedule[key]
        if not items:
            lines.append(f"    '{key}':[],")
            continue
        parts = []
        for it in items:
            text = it["text"].replace("\\", "\\\\").replace("'", "\\'")
            label = it["label"].replace("\\", "\\\\").replace("'", "\\'")
            parts.append(f"{{tag:'{it['tag']}',label:'{label}',text:'{text}'}}")
        lines.append(f"    '{key}':[{','.join(parts)}],")
    lines.append("  };")
    return "\n".join(lines)


def html_esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def render_today_rocks(items):
    if not items:
        return (
            '      <li><label><em style="color:var(--sumi-dim);font-family:\'Fraunces\',serif">'
            "No deep work today - open day.</em></label></li>"
        )
    out = []
    for i, it in enumerate(items, start=1):
        mid = f"t-r{i}"
        out.append(
            f'      <li><input type="checkbox" id="{mid}" data-group="rocks"><label for="{mid}">'
            f'<span class="tag {it["tag"]}">{html_esc(it["label"])}</span>{html_esc(it["text"])}</label></li>'
        )
    return "\n".join(out)


def render_today_meetings(items):
    if not items:
        return (
            '        <li><label><em style="color:var(--sumi-dim);font-family:\'Fraunces\',serif">'
            "No meetings today.</em></label></li>"
        )
    out = []
    for i, it in enumerate(items, start=1):
        mid = f"t-mtg-{i}"
        out.append(
            f'        <li><input type="checkbox" id="{mid}" data-group="meetings"><label for="{mid}">'
            f'<span class="tag {it["tag"]}">{html_esc(it["label"])}</span>{html_esc(it["text"])}</label></li>'
        )
    return "\n".join(out)


def render_today_admin(items):
    if not items:
        return (
            '        <li><label><em class="admin-placeholder">'
            "Nothing scheduled. Ad-hoc admin lands here.</em></label></li>"
        )
    out = []
    for i, it in enumerate(items, start=1):
        mid = f"t-a{i}"
        out.append(
            f'        <li><input type="checkbox" id="{mid}" data-group="admin"><label for="{mid}">'
            f'<span class="tag {it["tag"]}">{html_esc(it["label"])}</span>{html_esc(it["text"])}</label></li>'
        )
    return "\n".join(out)


def replace_between(text, start_marker, end_marker, new_block):
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.DOTALL)
    indent = "  " if end_marker.startswith("  //") else ("      " if end_marker.startswith("<!--") else "")
    replacement = start_marker + "\n" + new_block + "\n" + indent + end_marker
    return pattern.sub(lambda _m: replacement, text, count=1)


def patch_file(path):
    original = path.read_text()
    events, today = fetch_and_parse(ICS_URL)
    schedule = build_schedule(events)
    rocks, meetings, admin = build_today_buckets(events, today)

    patched = original
    patched = replace_between(patched, "// AUTO_SCHEDULE_START", "// AUTO_SCHEDULE_END",
                              render_schedule_js(schedule))
    patched = replace_between(patched, "<!-- AUTO_TODAY_ROCKS_START -->", "<!-- AUTO_TODAY_ROCKS_END -->",
                              render_today_rocks(rocks))
    patched = replace_between(patched, "<!-- AUTO_MEETINGS_START -->", "<!-- AUTO_MEETINGS_END -->",
                              render_today_meetings(meetings))
    patched = replace_between(patched, "<!-- AUTO_ADMIN_START -->", "<!-- AUTO_ADMIN_END -->",
                              render_today_admin(admin))

    if patched == original:
        print("No changes.")
        return False
    path.write_text(patched)
    print(
        f"Patched {path.name}: {len(schedule)} scheduled days, "
        f"{len(rocks)} rocks, {len(meetings)} meetings, {len(admin)} admin (today)."
    )
    return True


if __name__ == "__main__":
    patch_file(INDEX)
    sys.exit(0)
