#!/usr/bin/env python3
"""Give imported HLTV downloads their exact match dates (and register missing events).

    python scripts/register_hltv_dates.py --plan _sync/aurora_plan.json --log _sync/aurora_download.log
    python scripts/register_hltv_dates.py ... --apply      # write config/match_dates.csv / events.json

HLTV archive names carry no match id, so the pipeline normally dates those demos by
event (start date or an interpolated day). When we planned the downloads ourselves we
know each archive's HLTV match and its start time (``unix_ms`` from the match page).
This script joins:

  plan JSON   {"matches": [{"demo_id": <HLTV demo id>, "hltv_match_id", "unix_ms", "event", ...}]}
  download log lines ``OK <hltv demo id> <hltv match id> <size|already-present> <archive file>``
  extracted demos under data/raw/hltv/<archive stem>/

and writes one ``demo_id,date`` row per game into config/match_dates.csv (dates are the
UTC calendar day of the match start; existing rows are never overwritten and conflicts are
reported). Events that are missing from config/events.json are added with the range of the
planned matches of that event, flagged ``"source": "hltv-plan"`` so a human can refine them.
Default is a dry run.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playbook.dedupe import demo_event_slug  # noqa: E402
from playbook.parse import demo_identity  # noqa: E402

ARCHIVE_SUFFIXES = (".rar", ".zip", ".gz", ".bz2", ".7z")


def read_log(path: Path) -> dict[int, str]:
    """HLTV demo id -> archive file name, from OK lines of a download log."""
    out: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split(" ", 4)
        if len(parts) == 5 and parts[0] == "OK" and parts[1].isdigit():
            out[int(parts[1])] = parts[4].strip()
    return out


def utc_day(unix_ms: int) -> str:
    return datetime.fromtimestamp(unix_ms / 1000, tz=timezone.utc).date().isoformat()


def archive_stem(name: str) -> str:
    for suffix in ARCHIVE_SUFFIXES:
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return name


def collect(plan: dict, log: dict[int, str], raw: Path) -> tuple[dict[str, str], dict[str, dict], list[str]]:
    """(demo_id -> date, event slug -> {name, dates}, notes)."""
    by_demo = {int(m["demo_id"]): m for m in plan["matches"]}
    dates: dict[str, str] = {}
    events: dict[str, dict] = {}
    notes: list[str] = []
    hltv = raw / "hltv"
    for hltv_demo, name in sorted(log.items()):
        match = by_demo.get(hltv_demo)
        if match is None:
            notes.append(f"demo {hltv_demo}: not in plan")
            continue
        folder = hltv / archive_stem(name)
        if not folder.is_dir():
            notes.append(f"demo {hltv_demo}: not imported yet ({folder.name})")
            continue
        day = utc_day(int(match["unix_ms"]))
        games = sorted(p for p in folder.rglob("*.dem") if not p.name.startswith("._"))
        if not games:
            notes.append(f"demo {hltv_demo}: no .dem files in {folder.name} (all maps skipped?)")
        for path in games:
            demo_id = demo_identity(path)["demo_id"]
            if dates.get(demo_id, day) != day:
                notes.append(f"{demo_id}: two plan dates {dates[demo_id]} / {day}")
                continue
            dates[demo_id] = day
            slug = demo_event_slug(path, raw)
            if slug:
                ev = events.setdefault(slug, {"name": match.get("event") or slug, "days": set()})
                ev["days"].add(day)
    return dates, events, notes


def merge_dates(path: Path, new: dict[str, str]) -> tuple[list[tuple[str, str]], list[str]]:
    existing: dict[str, str] = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                if row.get("demo_id"):
                    existing[row["demo_id"].strip()] = row["date"].strip()
    added, conflicts = [], []
    for demo_id, day in sorted(new.items()):
        if demo_id in existing:
            if existing[demo_id] != day:
                conflicts.append(f"{demo_id}: keeps {existing[demo_id]} (plan says {day})")
            continue
        added.append((demo_id, day))
    return added, conflicts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--log", type=Path, required=True, nargs="+")
    ap.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--dates", type=Path, default=ROOT / "config" / "match_dates.csv")
    ap.add_argument("--events", type=Path, default=ROOT / "config" / "events.json")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    log: dict[int, str] = {}
    for p in args.log:
        if p.exists():
            log.update(read_log(p))
    dates, events, notes = collect(plan, log, args.raw)
    added, conflicts = merge_dates(args.dates, dates)

    registry = json.loads(args.events.read_text(encoding="utf-8"))
    new_events = {}
    for slug, info in sorted(events.items()):
        if slug in registry["events"]:
            continue
        days = sorted(info["days"])
        new_events[slug] = {"name": info["name"], "start": days[0], "end": days[-1], "source": "hltv-plan"}

    print(f"games dated: {len(dates)}; new date rows: {len(added)}; conflicts kept: {len(conflicts)}; "
          f"new events: {len(new_events)}")
    for line in conflicts + notes:
        print("  " + line)
    for slug, ev in new_events.items():
        print(f"  + event {slug}: {ev['name']} {ev['start']}..{ev['end']}")
    if not args.apply:
        print("(dry run; pass --apply to write)")
        return 0
    if added:
        write_header = not args.dates.exists() or args.dates.stat().st_size == 0
        with args.dates.open("a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if write_header:
                w.writerow(["demo_id", "date"])
            w.writerows(added)
    if new_events:
        registry["events"].update(new_events)
        args.events.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
