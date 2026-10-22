"""Schedule-based match dates. Day precision is an estimate, never a timestamp.

Unique HLTV series IDs are ranked within each event and spaced evenly (nearest
calendar day) over its inclusive schedule. All raw series participate, so merely
parsing another map does not shift existing estimates. Sparse events and series
without IDs use the event start. Unknown sources stay undated.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from playbook.config import CONFIG_DIR, RAW_DIR
from playbook.dedupe import _pretty_event, demo_event_slug

DATE_FIELDS = ("date", "date_precision", "event")


def match_date_key(match: dict) -> tuple:
    """Newest dates first when sorted in reverse; undated rows last."""
    return (match.get("date") or "", match.get("hltv_match_id") or 0, match["demo_id"])


def load_overrides(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out = {}
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not {"demo_id", "date"} <= set(reader.fieldnames or []):
            raise ValueError(f"{path}: expected demo_id,date columns")
        for row in reader:
            demo, value = row["demo_id"].strip(), row["date"].strip()
            if not demo and not value:
                continue
            if not demo or date.fromisoformat(value).isoformat() != value:
                raise ValueError(f"{path}: invalid override {row}")
            if demo in out and out[demo] != value:
                raise ValueError(f"{path}: conflicting dates for {demo}")
            out[demo] = value
    return out


def demo_dates(matches: pl.DataFrame, raw_dir: Path = RAW_DIR,
               events_path: Path = CONFIG_DIR / "events.json",
               overrides_path: Path = CONFIG_DIR / "match_dates.csv") -> dict[str, dict]:
    """Resolve each input demo; manual series overrides win, including unknown events.

    A manual date on any map applies to the entire series. Conflicting overrides
    in the same series are rejected rather than silently producing different dates.
    Event aliases share their configured name and range, not separate rankings.
    """
    from playbook.parse import demo_identity

    registry = json.loads(events_path.read_text(encoding="utf-8"))["events"]
    overrides = load_overrides(overrides_path)
    sources = {}
    # Include raw but not yet parsed matches in the event's ordered population.
    records = {}
    for path in sorted(raw_dir.rglob("*.dem")):
        ident = demo_identity(path)
        slug = demo_event_slug(path, raw_dir)
        record = {**ident, "slug": slug, "archive": str(path.parent)}
        sources.setdefault(ident["demo_id"], record)
        records.setdefault(ident["demo_id"], record)
    for row in matches.iter_rows(named=True):
        record = dict(sources.get(row["demo_id"], {}))
        record.update(demo_id=row["demo_id"], hltv_match_id=row.get("hltv_match_id") or record.get("hltv_match_id"))
        records[row["demo_id"]] = record

    # Union by archive and HLTV id: id-bearing maps date their archive siblings.
    parent = {demo: demo for demo in records}
    def find(demo):
        while parent[demo] != demo:
            parent[demo] = parent[parent[demo]]
            demo = parent[demo]
        return demo
    seen = {}
    for demo, row in records.items():
        info = registry.get(row.get("slug"), {})
        event_key = (info.get("name"), info.get("start"), info.get("end")) if info else row.get("slug")
        row["event_key"] = event_key
        keys = []
        if row.get("archive") and row.get("slug"):
            keys.append(("archive", row["archive"]))
        if row.get("hltv_match_id"):
            keys.append(("id", event_key, row["hltv_match_id"]))
        for key in keys:
            if key in seen:
                parent[find(demo)] = find(seen[key])
            else:
                seen[key] = demo
    groups = defaultdict(list)
    for demo, row in records.items():
        groups[find(demo)].append(row)
    event_ids = defaultdict(set)
    for row in records.values():
        if row.get("hltv_match_id"):
            event_ids[row["event_key"]].add(row["hltv_match_id"])
    estimates = {}
    for key, ids in event_ids.items():
        ordered = sorted(ids)
        if len(ordered) >= 3:
            estimates[key] = {mid: i / (len(ordered) - 1) for i, mid in enumerate(ordered)}

    out = {}
    for rows in groups.values():
        known = next((r for r in rows if r.get("slug") in registry), rows[0])
        info = registry.get(known.get("slug"))
        result = {"date": None, "date_precision": None,
                  "event": info["name"] if info else _pretty_event(known["slug"]) if known.get("slug") else None}
        if info:
            start, end = date.fromisoformat(info["start"]), date.fromisoformat(info["end"])
            if end < start:
                raise ValueError(f"Invalid event date range: {known['slug']}")
            result.update(date=start.isoformat(), date_precision="event")
            mid = next((r["hltv_match_id"] for r in rows if r.get("hltv_match_id")), None)
            fraction = estimates.get(known["event_key"], {}).get(mid)
            if fraction is not None:
                estimate = start + timedelta(days=int((end - start).days * fraction + .5))
                if start <= estimate <= end:
                    result.update(date=estimate.isoformat(), date_precision="day")
        exact = {overrides[r["demo_id"]] for r in rows if r["demo_id"] in overrides}
        if len(exact) > 1:
            raise ValueError(f"Conflicting manual dates in series: {[r['demo_id'] for r in rows]}")
        if exact:
            result.update(date=exact.pop(), date_precision="exact")
        for row in rows:
            out[row["demo_id"]] = dict(result)
    return {demo: out[demo] for demo in matches["demo_id"].to_list()}


def attach_dates(matches: pl.DataFrame, **kwargs) -> pl.DataFrame:
    metadata = demo_dates(matches, **kwargs)
    return matches.with_columns(
        pl.Series(field, [metadata[demo][field] for demo in matches["demo_id"]], dtype=pl.String)
        for field in DATE_FIELDS)


def attach_example_dates(recipes: list[dict], matches: pl.DataFrame) -> None:
    metadata = {row["demo_id"]: row for row in matches.iter_rows(named=True)}
    for recipe in recipes:
        for example in recipe.get("examples", []):
            row = metadata.get(example["demo_id"], {})
            example.update({field: row.get(field) for field in DATE_FIELDS})
        recipe["examples"] = sorted(recipe.get("examples", []),
                                    key=lambda e: match_date_key(metadata.get(e["demo_id"], e)), reverse=True)
