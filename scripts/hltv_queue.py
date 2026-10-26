#!/usr/bin/env python3
"""Write the page for downloading one team's planned HLTV demos by hand.

    python scripts/hltv_queue.py aurora      # -> _sync/aurora_queue.html, open it in Safari

The page lists the matches of ``_sync/<team>_plan.json`` in the order of
``_sync/<team>_queue.txt`` (both written by scripts/hltv_plan.py): stars, date, event, teams
and a link, to the demo when its id is known, else to the match page (click "GOTV Demo"
there). Matches whose demos are already here are greyed out, and the page remembers which
links you clicked. HLTV allows manual downloads only, so this script contacts nobody: it
reads the plan and looks at data/raw. When the downloads have finished, run
``bash scripts/refresh.sh`` (or ask Claude to); refresh rewrites this page as well.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playbook import hltv  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("team", help="team slug, as in _sync/<team>_plan.json")
    ap.add_argument("--sync-dir", type=Path, default=ROOT / "_sync")
    args = ap.parse_args(argv)
    plan = args.sync_dir / f"{args.team}_plan.json"
    if not plan.exists():
        print(f"No plan {plan} (run scripts/hltv_plan.py {args.team} first)")
        return 1
    page, total, here = hltv.write_queue_page(args.team, args.sync_dir, ROOT)
    print(f"{page}: {total} match(es), {here} already here, {total - here} to download. "
          "Open it in Safari and click the links one by one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
