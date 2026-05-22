from __future__ import annotations

import hashlib
import os
from datetime import datetime

try:
    from icalendar import Calendar, Event
except ImportError:
    raise SystemExit("请先安装依赖: pip install icalendar")


def build_ics(
    events: list[dict],
    calendar_name: str = "Calendar",
    uid_prefix: str = "",
) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//calpipe//calpipe//ZH")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", calendar_name)

    now_utc = datetime.utcnow()
    for ev in events:
        raw = f"{ev['title']}|{ev['start'].isoformat()}"
        h = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
        prefix = uid_prefix + "-" if uid_prefix else ""
        uid = f"{prefix}{ev['start'].strftime('%Y%m%d')}-{h}"

        event = Event()
        event.add("uid", uid)
        event.add("dtstamp", now_utc)
        event.add("dtstart", ev["start"])
        event.add("dtend", ev["end"])
        event.add("summary", ev["title"])
        if ev.get("description"):
            event.add("description", ev["description"])
        if ev.get("url"):
            event.add("url", ev["url"])
        cal.add_component(event)

    return cal.to_ical()


def events_by_year(events: list[dict]) -> dict[int, list[dict]]:
    by_year: dict[int, list[dict]] = {}
    for ev in events:
        start_y = ev["start"].year
        end_y = ev["end"].year
        for y in range(start_y, end_y + 1):
            by_year.setdefault(y, []).append(ev)
    return by_year


def generate_ics_by_year(
    events: list[dict],
    source_id: str,
    calendar_name: str,
    uid_prefix: str,
    output_dir: str,
    only_current_year: bool = False,
) -> dict[int, int]:
    by_year = events_by_year(events)
    written: dict[int, int] = {}
    current_year = datetime.now().year
    years_to_write = [current_year] if only_current_year else sorted(by_year.keys())

    for year in years_to_write:
        if year not in by_year:
            continue
        year_events = by_year[year]
        name = f"{calendar_name} {year}"
        ics_bytes = build_ics(year_events, calendar_name=name, uid_prefix=uid_prefix)
        path = os.path.join(output_dir, f"{source_id}_{year}.ics")
        with open(path, "wb") as f:
            f.write(ics_bytes)
        written[year] = len(year_events)

        if year == current_year:
            path_latest = os.path.join(output_dir, f"{source_id}_latest.ics")
            with open(path_latest, "wb") as f:
                f.write(ics_bytes)
    return written


def generate_ics_full(
    events: list[dict],
    source_id: str,
    calendar_name: str,
    uid_prefix: str,
    output_dir: str,
) -> None:
    name = f"{calendar_name} 全量"
    ics_bytes = build_ics(events, calendar_name=name, uid_prefix=uid_prefix)
    path = os.path.join(output_dir, f"{source_id}_all.ics")
    with open(path, "wb") as f:
        f.write(ics_bytes)
