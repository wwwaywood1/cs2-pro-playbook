#!/usr/bin/env python3
"""Plan (and script) the HLTV demo downloads for one team.

    # on a machine that can reach hltv.org (your own Terminal):
    python scripts/hltv_plan.py aurora --fetch
    # from pages saved by a browser (results page + one HTML file per match page):
    python scripts/hltv_plan.py aurora --results-html results.html --match-html-dir matches/

Writes ``_sync/<team>_plan.json`` (matches with exact start times, events, demo ids) and
``_sync/<team>_queue.txt`` (most wanted first) for ``scripts/hltv_download.sh <team>``, which
downloads them into ~/Downloads and then runs ``scripts/refresh.sh`` (import, exact dates via
scripts/register_hltv_dates.py, archive the .rar/.zip files, parse, export).

HLTV is behind Cloudflare. This tool identifies itself honestly and stops when it is refused;
it never tries to get around a check. Save the pages from your browser instead (above).

Scope (config/hltv.toml): matches since ``[download] since``, tier-1 events only, ordered by
HLTV's popularity stars (they reflect both teams' rankings), then newest first. Matches we
already have are skipped: HLTV ids registered in config/hltv_archives.json or present as
dataset folders (data/raw/<source>/<event>/<id>-...), and archives with the same
event/teams/format (data/raw/hltv folders + the archive directory in config/storage.toml).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playbook import hltv  # noqa: E402

UA = "cs2-pro-playbook/0.1 (personal non-commercial CS2 demo analysis; one request at a time)"


class Blocked(RuntimeError):
    pass


def fetch(url: str, delay: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:  # Cloudflare answers 403/503 with a challenge page
        raise Blocked(f"{url}: HTTP {exc.code}") from exc
    if "Just a moment" in body[:2000] or "cf-chl" in body[:5000]:
        raise Blocked(f"{url}: Cloudflare challenge")
    time.sleep(delay)
    return body


def existing_stems() -> list[str]:
    stems = []
    raw = ROOT / "data" / "raw" / "hltv"
    if raw.is_dir():
        stems += [p.name for p in raw.iterdir() if p.is_dir()]
        stems += [p.stem for p in raw.iterdir() if p.is_file() and p.suffix.lower() in (".rar", ".zip")]
    storage = ROOT / "config" / "storage.toml"
    if storage.exists():
        adir = Path((tomllib.loads(storage.read_text()).get("archive") or {}).get("dir", "/nonexistent"))
        if adir.is_dir():
            stems += [p.stem for p in adir.iterdir() if p.suffix.lower() in (".rar", ".zip")
                      and not p.name.startswith("._")]
    return stems


def known_match_ids() -> set[int]:
    """HLTV match ids we already have: registered archives and dataset folders named <id>-..."""
    ids: set[int] = set()
    registry = ROOT / "config" / "hltv_archives.json"
    if registry.exists():
        ids |= {int(m) for m in json.loads(registry.read_text(encoding="utf-8")).get("archives", {}).values()}
    raw = ROOT / "data" / "raw"
    if raw.is_dir():
        for source in raw.iterdir():
            if source.is_dir() and source.name != "hltv":
                for folder in source.glob("*/*"):
                    head = folder.name.split("-", 1)[0]
                    if folder.is_dir() and head.isdigit():
                        ids.add(int(head))
    return ids


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("team", help="team slug from config/hltv.toml [teams]")
    ap.add_argument("--fetch", action="store_true", help="fetch hltv.org pages directly")
    ap.add_argument("--results-html", type=Path, nargs="*", default=[])
    ap.add_argument("--match-html-dir", type=Path)
    ap.add_argument("--since")
    ap.add_argument("--limit", type=int, default=0, help="keep only the first N planned matches")
    ap.add_argument("--delay", type=float, default=10.0, help="seconds between page fetches (HLTV starts challenging at ~3 s)")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "_sync")
    args = ap.parse_args(argv)

    cfg = hltv.load_config()
    team_id = (cfg.get("teams") or {}).get(args.team)
    if team_id is None:
        ap.error(f"unknown team {args.team!r}; add it to config/hltv.toml [teams]")
    since = args.since or (cfg.get("download") or {}).get("since", "2026-01-01")

    rows: list[hltv.ResultRow] = []
    try:
        if args.fetch:
            for offset in (0, 100):
                page = hltv.parse_results(fetch(f"{hltv.HLTV}/results?team={team_id}"
                                                + (f"&offset={offset}" if offset else ""), args.delay))
                rows += page
                if not page or min((r.unix_ms or 1 << 62) for r in page) < hltv.datetime.fromisoformat(
                        since).replace(tzinfo=hltv.timezone.utc).timestamp() * 1000:
                    break
        for path in args.results_html:
            rows += hltv.parse_results(path.read_text(encoding="utf-8"))
        want, have, skipped = hltv.plan_matches(rows, existing_stems(), since=since, cfg=cfg,
                                                known_ids=known_match_ids())
        if args.limit:
            want = want[: args.limit]
        entries = []
        for row in want:
            html = None
            if args.match_html_dir and (args.match_html_dir / f"{row.match_id}.html").exists():
                html = (args.match_html_dir / f"{row.match_id}.html").read_text(encoding="utf-8")
            elif args.fetch:
                html = fetch(f"{hltv.HLTV}/matches/{row.match_id}/{row.slug}", args.delay)
            page = hltv.parse_match(html) if html else None
            if page is None or page.demo_id is None:
                print(f"  no demo link yet: {row.match_id} {row.slug}")
                continue
            entries.append({"hltv_match_id": row.match_id, "demo_id": page.demo_id,
                            "unix_ms": page.unix_ms or row.unix_ms, "event": page.event or row.event,
                            "hltv_event_id": page.event_id, "teams": page.teams or row.teams,
                            "maps_played": page.maps_played, "stars": row.stars, "slug": row.slug})
    except Blocked as exc:
        print(f"HLTV refused this request ({exc}). Stopping. Save the pages from your browser and pass "
              "--results-html/--match-html-dir instead.")
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = args.out_dir / f"{args.team}_plan.json"
    hltv.write_plan(plan_path, {"slug": args.team, "hltv_team_id": team_id, "since": since}, entries)
    queue = args.out_dir / f"{args.team}_queue.txt"
    queue.write_text(hltv.queue_text(entries), encoding="utf-8")
    print(f"{len(entries)} to download, {len(have)} already have, {len(skipped)} not tier-1 -> {plan_path.name}, "
          f"{queue.name}")
    print(f"Next: caffeinate -i bash scripts/hltv_download.sh {args.team}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
