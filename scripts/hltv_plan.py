#!/usr/bin/env python3
"""Plan one team's HLTV demo downloads from pages you saved in your browser.

HLTV allows demo downloads by people only (its robots.txt disallows automated demo
downloads and its terms reportedly forbid scraping), so this tool never contacts hltv.org:

    # 1. In Safari open https://www.hltv.org/results?team=<id> (ids: config/hltv.toml [teams])
    #    and save it with File > Save As ("Web Archive" or "Page Source" both work). For
    #    older matches also save the next results page ("Next" at the bottom).
    # 2. Optional: save match pages as well; they add the demo link, exact start time and maps.
    python scripts/hltv_plan.py aurora --results-html ~/Downloads/Results.webarchive \
        [--match-html-dir ~/Downloads/aurora-matches]

Writes ``_sync/<team>_plan.json`` (matches with start times, events and demo ids when known),
``_sync/<team>_queue.txt`` (most wanted first) and ``_sync/<team>_queue.html``: open the page in
Safari and click its links one by one. A match whose page you saved links to its demo; the
others link to their match page, where you click "GOTV Demo". When the downloads have
finished, run ``bash scripts/refresh.sh`` (import, exact dates via scripts/register_hltv_dates.py,
archive the .rar/.zip files, parse, export; it also updates the page). scripts/hltv_queue.py
rewrites the page on its own.

Scope (config/hltv.toml): matches since ``[download] since``, tier-1 events only, ordered by
HLTV's popularity stars (they reflect both teams' rankings), then newest first. Matches we
already have are skipped: HLTV ids registered in config/hltv_archives.json or present as
dataset folders (data/raw/<source>/<event>/<id>-...), and archives with the same
event/teams/format (data/raw/hltv folders + the archive directory in config/storage.toml).
When a rematch at the same event makes that comparison ambiguous, those matches are not
queued but listed for you to decide (printed, and under "待确认 / To check" on the page).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playbook import hltv  # noqa: E402

SAVED_PAGES = (".html", ".htm", ".webarchive")


def existing_stems() -> list[str]:
    """Archive stems we have that are not registered to a match id (registered ones are
    covered by known_match_ids, and must not stand in for another match)."""
    return sorted(hltv.local_stems(ROOT) - hltv.archive_registry(ROOT).keys())


def known_match_ids() -> set[int]:
    """HLTV match ids we already have: registered archives and dataset folders named <id>-..."""
    return set(hltv.archive_registry(ROOT).values()) | hltv.dataset_match_ids(ROOT)


def saved_match_pages(folder: Path | None) -> dict[int, hltv.MatchPage]:
    """Saved match pages by HLTV match id, taken from the file name (<id>.html), the URL a
    .webarchive records, or the page's own canonical link."""
    pages: dict[int, hltv.MatchPage] = {}
    for path in sorted(folder.iterdir()) if folder else []:
        if path.suffix.lower() not in SAVED_PAGES:
            continue
        html, url = hltv.read_saved_page(path)
        page = hltv.parse_match(html)
        m = hltv.MATCH_HREF.search(url)
        mid = int(path.stem) if path.stem.isdigit() else int(m[1]) if m else page.match_id
        if mid is None:
            print(f"  cannot tell which match {path.name} is; rename it to <match id>{path.suffix}")
            continue
        pages[mid] = page
    return pages


def plan_entry(row: hltv.ResultRow, page: hltv.MatchPage | None) -> dict:
    """One planned match; ``demo_id`` stays None unless its match page was saved."""
    return {"hltv_match_id": row.match_id, "demo_id": page.demo_id if page else None,
            "unix_ms": (page.unix_ms if page else None) or row.unix_ms,
            "event": (page.event if page else "") or row.event,
            "hltv_event_id": page.event_id if page else None,
            "teams": (page.teams if page else []) or row.teams,
            "maps_played": page.maps_played if page else [],
            "stars": row.stars, "slug": row.slug, "fmt": row.fmt}


def day(unix_ms: int | None) -> str:
    return datetime.fromtimestamp(unix_ms / 1000, tz=timezone.utc).date().isoformat() if unix_ms else "?"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("team", help="team slug from config/hltv.toml [teams]")
    ap.add_argument("--results-html", type=Path, nargs="+", required=True,
                    help="the team's HLTV results page(s) saved from your browser (.html or .webarchive)")
    ap.add_argument("--match-html-dir", type=Path, help="folder with saved HLTV match pages (optional)")
    ap.add_argument("--since")
    ap.add_argument("--limit", type=int, default=0, help="keep only the first N planned matches")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "_sync")
    args = ap.parse_args(argv)

    cfg = hltv.load_config()
    team_id = (cfg.get("teams") or {}).get(args.team)
    if team_id is None:
        ap.error(f"unknown team {args.team!r}; add it to config/hltv.toml [teams]")
    if args.match_html_dir and not args.match_html_dir.is_dir():
        ap.error(f"no folder {args.match_html_dir}")
    since = args.since or (cfg.get("download") or {}).get("since", "2026-01-01")
    results_url = f"{hltv.HLTV}/results?team={team_id}"

    rows: list[hltv.ResultRow] = []
    for path in args.results_html:
        rows += hltv.parse_results(hltv.read_saved_page(path)[0])
    if not rows:
        print(f"No HLTV results in {', '.join(map(str, args.results_html))}. Open {results_url} in Safari, "
              "save it (File > Save As) and pass that file.")
        return 1
    oldest = min((r.unix_ms for r in rows if r.unix_ms), default=None)
    if oldest and day(oldest) > since:
        print(f"Note: the saved results go back to {day(oldest)} only; to plan everything since {since}, also "
              f"save the next page of {results_url} ('Next' at the bottom) and pass it too.")
    plan = hltv.plan_matches(rows, existing_stems(), since=since, cfg=cfg, known_ids=known_match_ids())
    want = plan.want[: args.limit] if args.limit else plan.want
    pages = saved_match_pages(args.match_html_dir)
    entries = [plan_entry(row, pages.get(row.match_id)) for row in want]
    ambiguous = [plan_entry(row, pages.get(row.match_id)) for row in plan.ambiguous]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = args.out_dir / f"{args.team}_plan.json"
    hltv.write_plan(plan_path, {"slug": args.team, "hltv_team_id": team_id, "since": since}, entries, ambiguous)
    queue = args.out_dir / f"{args.team}_queue.txt"
    queue.write_text(hltv.queue_text(entries), encoding="utf-8")
    page, _, _ = hltv.write_queue_page(args.team, args.out_dir, ROOT)
    via_page = sum(1 for e in entries if e["demo_id"] is None)
    print(f"{len(entries)} to download ({via_page} via their match page), {len(plan.have)} already have, "
          f"{len(plan.ambiguous)} ambiguous, {len(plan.skipped)} not tier-1 -> {plan_path.name}, {queue.name}, "
          f"{page.name}")
    if plan.ambiguous:
        print("Not queued, decide by hand (also listed on the page): these share event, teams and format with "
              "archives we have, but there are more such matches than archives (a rematch?):")
        for row in plan.ambiguous:
            print(f"  {row.match_id} {day(row.unix_ms)} {' vs '.join(row.teams)} ({row.event}, {row.fmt}) "
                  f"{hltv.match_url(row.match_id, row.slug)}")
    print(f"Next: open {page} in Safari and click the links one by one; when the downloads have finished, "
          "run bash scripts/refresh.sh (or ask Claude to).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
