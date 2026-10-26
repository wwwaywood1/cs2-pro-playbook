#!/usr/bin/env python3
"""Give demos their exact match dates from known HLTV match start times.

    # after a planned download (scripts/refresh.sh runs this automatically):
    python scripts/register_hltv_dates.py --plan _sync/aurora_plan.json --log _sync/aurora_download.log
    # backfill archives that were imported earlier, from an archive -> HLTV match mapping:
    python scripts/register_hltv_dates.py --archives _sync/archive_matches.json
    # start times for demos whose folder names carry the HLTV match id (dataset trees):
    python scripts/register_hltv_dates.py --matches _sync/match_starts.json
    # re-derive dates for everything in the registry (e.g. after more imports):
    python scripts/register_hltv_dates.py
    ... --apply      # write config/hltv_archives.json, config/match_dates.csv, config/events.json

HLTV archive names carry no match id, so the pipeline normally dates those demos by
event (start date or an interpolated day). Once we know which HLTV match an archive
came from, or when a match is (its start time), the date is exact. The registry
``config/hltv_archives.json`` keeps that knowledge:

  "matches":  {"<hltv match id>": {"start_unix_ms", "event", "hltv_event_id", "maps", "teams", "source", ...}}
  "archives": {"<archive stem>": <hltv match id>}

Inputs (all optional, merged into the registry):

  --plan + --log   plan JSON {"matches": [{"demo_id": <HLTV demo id>, "hltv_match_id", "unix_ms", ...}]}
                   and download-log lines ``OK <hltv demo id> <hltv match id> <size|already-present> <file>``
  --archives       {"<archive stem>": {"hltv_match_id", "unix_ms", "event", "maps", ...}}
  --matches        {"<hltv match id>": {"unix_ms", "event", "maps", ...}}

Every game of a registered archive that has been imported (``data/raw/hltv/<stem>/``)
and every other raw demo whose identity carries a registered HLTV match id gets one
``demo_id,date`` row in config/match_dates.csv.

- The maps inside an archive must all be maps played in its HLTV match (when the match
  lists maps); otherwise the archive is skipped as a wrong mapping.
- The date is the UTC calendar day of the match start. When the event is in
  config/events.json and that day falls exactly one day outside the event's (local)
  range, it is clamped into the range (an evening match in the Americas starts after
  midnight UTC).
- Existing rows are never overwritten (conflicts are reported); registry entries are
  never replaced by different values.
- Events missing from config/events.json are added with the range of their matches,
  flagged ``"source": "hltv-plan"`` so a human can refine them.

Default is a dry run.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playbook.dedupe import demo_event_slug  # noqa: E402
from playbook.parse import demo_identity  # noqa: E402

ARCHIVE_SUFFIXES = (".rar", ".zip", ".gz", ".bz2", ".7z")
MAP_RE = re.compile(r"(?:^|-)(dust2|mirage|inferno|nuke|ancient|anubis|cache|overpass|train|vertigo)(?:-p\d+)?$")
REGISTRY_NOTE = ("HLTV matches we know the start time of, and which HLTV match each imported archive came "
                 "from. Written by scripts/register_hltv_dates.py; drives exact dates in config/match_dates.csv.")


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
    name = Path(name).name
    for suffix in ARCHIVE_SUFFIXES:
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return name


def game_map(path: Path) -> str | None:
    m = MAP_RE.search(path.stem.lower())
    return m[1] if m else None


def match_entry(match: dict, source: str) -> dict:
    """Normalise a plan/archives/matches record into a registry match entry."""
    maps = match.get("maps_played", match.get("maps")) or []
    if isinstance(maps, str):
        maps = [m for m in maps.split(",") if m]
    out = {"start_unix_ms": int(match.get("start_unix_ms") or match["unix_ms"]),
           "event": match.get("event") or "",
           "hltv_event_id": match.get("hltv_event_id"),
           "maps": list(maps),
           "source": match.get("source") or source}
    teams = match.get("teams")
    if teams:
        out["teams"] = teams.split("|") if isinstance(teams, str) else list(teams)
    for key in ("bo3_match_id", "stars"):
        if match.get(key) is not None:
            out[key] = match[key]
    return out


def load_registry(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.setdefault("_note", REGISTRY_NOTE)
    data.setdefault("matches", {})
    data.setdefault("archives", {})
    return data


def merge_registry(registry: dict, matches: dict[str, dict], archives: dict[str, str]) -> tuple[int, int, list[str]]:
    """Add new matches/archives in place; never replace an entry with different values."""
    notes, new_m, new_a = [], 0, 0
    for mid, entry in sorted(matches.items()):
        old = registry["matches"].get(mid)
        if old is None:
            registry["matches"][mid] = entry
            new_m += 1
        elif utc_day(old["start_unix_ms"]) != utc_day(entry["start_unix_ms"]):
            notes.append(f"match {mid}: registry keeps start {utc_day(old['start_unix_ms'])} "
                         f"(input says {utc_day(entry['start_unix_ms'])})")
    for stem, mid in sorted(archives.items()):
        old = registry["archives"].get(stem)
        if old is None:
            registry["archives"][stem] = mid
            new_a += 1
        elif str(old) != str(mid):
            notes.append(f"{stem}: registry keeps match {old} (input says {mid})")
    return new_m, new_a, notes


def clamp_to_event(day: str, slug: str | None, events: dict) -> str:
    info = events.get(slug or "")
    if not info:
        return day
    d, start, end = date.fromisoformat(day), date.fromisoformat(info["start"]), date.fromisoformat(info["end"])
    if d == end + timedelta(days=1):
        return end.isoformat()
    if d == start - timedelta(days=1):
        return start.isoformat()
    return day


def _maps_ok(games: list[Path], entry: dict) -> bool:
    played = {m.lower() for m in entry.get("maps") or []}
    return not played or {game_map(p) for p in games} <= played


def collect(registry: dict, raw: Path, events: dict) -> tuple[dict[str, str], dict[str, dict], list[str]]:
    """(demo_id -> date, new event slug -> {name, days}, notes)."""
    dates: dict[str, str] = {}
    new_events: dict[str, dict] = {}
    notes: list[str] = []
    matches = registry["matches"]

    def add(games: list[Path], entry: dict, label: str) -> None:
        slug = demo_event_slug(games[0], raw)
        day = clamp_to_event(utc_day(entry["start_unix_ms"]), slug, events)
        for path in games:
            demo_id = demo_identity(path)["demo_id"]
            if dates.get(demo_id, day) != day:
                notes.append(f"{demo_id}: two dates {dates[demo_id]} / {day} ({label})")
                continue
            dates[demo_id] = day
        if slug and slug not in events:
            ev = new_events.setdefault(slug, {"name": entry.get("event") or slug, "days": set()})
            ev["days"].add(day)

    for stem, mid in sorted(registry["archives"].items()):
        entry = matches.get(str(mid))
        if entry is None:
            notes.append(f"{stem}: match {mid} has no start time")
            continue
        folder = raw / "hltv" / stem
        if not folder.is_dir():
            notes.append(f"{stem}: not imported yet")
            continue
        games = sorted(p for p in folder.rglob("*.dem") if not p.name.startswith("._"))
        if not games:
            notes.append(f"{stem}: no .dem files (all maps skipped?)")
        elif not _maps_ok(games, entry):
            notes.append(f"{stem}: maps {sorted(m or '?' for m in {game_map(p) for p in games})} not all in "
                         f"match {mid} ({sorted(entry.get('maps') or [])}); skipped")
        else:
            add(games, entry, stem)

    # dataset trees whose folder names carry the HLTV match id (e.g. data/raw/<source>/<event>/<id>-<slug>/)
    by_match: dict[str, list[Path]] = {}
    if raw.is_dir():
        for path in sorted(raw.rglob("*.dem")):
            if path.name.startswith("._") or path.relative_to(raw).parts[0] == "hltv":
                continue
            mid = demo_identity(path)["hltv_match_id"]
            if mid is not None and str(mid) in matches:
                by_match.setdefault(str(mid), []).append(path)
    for mid, games in sorted(by_match.items()):
        if _maps_ok(games, matches[mid]):
            add(games, matches[mid], f"match {mid}")
        else:
            notes.append(f"match {mid}: demo maps not all in the registered maps; skipped")
    return dates, new_events, notes


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
                conflicts.append(f"{demo_id}: keeps {existing[demo_id]} (registry says {day})")
            continue
        added.append((demo_id, day))
    return added, conflicts


def from_plan(plan: dict, log: dict[int, str]) -> tuple[dict[str, dict], dict[str, str], list[str]]:
    by_demo = {int(m["demo_id"]): m for m in plan.get("matches", [])}
    matches, archives, notes = {}, {}, []
    for hltv_demo, name in sorted(log.items()):
        match = by_demo.get(hltv_demo)
        if match is None:
            notes.append(f"demo {hltv_demo}: not in plan")
            continue
        mid = str(int(match["hltv_match_id"]))
        matches[mid] = match_entry(match, "plan")
        archives[archive_stem(name)] = mid
    return matches, archives, notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--log", type=Path, nargs="+", default=[])
    ap.add_argument("--archives", type=Path, nargs="+", default=[],
                    help="JSON {archive stem: {hltv_match_id, unix_ms, event, maps, ...}}")
    ap.add_argument("--matches", type=Path, nargs="+", default=[],
                    help="JSON {hltv match id: {unix_ms, event, maps, ...}}")
    ap.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--registry", type=Path, default=ROOT / "config" / "hltv_archives.json")
    ap.add_argument("--dates", type=Path, default=ROOT / "config" / "match_dates.csv")
    ap.add_argument("--events", type=Path, default=ROOT / "config" / "events.json")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    if args.plan and not args.log:
        ap.error("--plan needs --log")

    in_matches: dict[str, dict] = {}
    in_archives: dict[str, str] = {}
    notes: list[str] = []
    if args.plan:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        log: dict[int, str] = {}
        for p in args.log:
            if p.exists():
                log.update(read_log(p))
        found_m, found_a, plan_notes = from_plan(plan, log)
        in_matches.update(found_m)
        in_archives.update(found_a)
        notes += plan_notes
    for path in args.archives:
        for stem, match in json.loads(path.read_text(encoding="utf-8")).items():
            mid = str(int(match["hltv_match_id"]))
            in_matches[mid] = match_entry(match, "archives")
            in_archives[archive_stem(stem)] = mid
    for path in args.matches:
        for mid, match in json.loads(path.read_text(encoding="utf-8")).items():
            in_matches[str(int(mid))] = match_entry(match, "matches")

    registry = load_registry(args.registry)
    new_m, new_a, reg_notes = merge_registry(registry, in_matches, in_archives)
    events_doc = json.loads(args.events.read_text(encoding="utf-8"))
    dates, events, collect_notes = collect(registry, args.raw, events_doc["events"])
    added, conflicts = merge_dates(args.dates, dates)
    new_events = {}
    for slug, info in sorted(events.items()):
        days = sorted(info["days"])
        new_events[slug] = {"name": info["name"], "start": days[0], "end": days[-1], "source": "hltv-plan"}

    print(f"registry: {len(registry['matches'])} matches ({new_m} new), {len(registry['archives'])} archives "
          f"({new_a} new); games dated: {len(dates)}; new date rows: {len(added)}; "
          f"conflicts kept: {len(conflicts)}; new events: {len(new_events)}")
    for line in reg_notes + conflicts + notes + collect_notes:
        print("  " + line)
    for slug, ev in new_events.items():
        print(f"  + event {slug}: {ev['name']} {ev['start']}..{ev['end']}")
    if not args.apply:
        print("(dry run; pass --apply to write)")
        return 0
    if new_m or new_a:
        registry["matches"] = dict(sorted(registry["matches"].items()))
        registry["archives"] = dict(sorted(registry["archives"].items()))
        args.registry.write_text(json.dumps(registry, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if added:
        write_header = not args.dates.exists() or args.dates.stat().st_size == 0
        with args.dates.open("a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if write_header:
                w.writerow(["demo_id", "date"])
            w.writerows(added)
    if new_events:
        events_doc["events"].update(new_events)
        args.events.write_text(json.dumps(events_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
