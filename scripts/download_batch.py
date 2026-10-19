"""Download pro demos from Hugging Face by event, map and size budget (batch 2 onwards).

Standalone on purpose: needs only Python 3.8+ and huggingface_hub, so it runs on any
machine that can reach huggingface.co.

    python3 -m pip install -U huggingface_hub
    python3 scripts/download_batch.py --dry-run                       # list, sizes per map
    python3 scripts/download_batch.py --maps nuke dust2 ancient anubis overpass --max-gb 40
    python3 scripts/download_batch.py --events iem_cologne_major_2026 cac_2026 --max-gb 60

Selection: games of the chosen events and maps, all parts of multipart games (the parser
stitches them, see DESIGN.md), duplicate "(1)" uploads skipped. Games already on disk are
skipped and do not count against --max-gb. Within the budget, maps are filled round-robin
(newest match first per map) so every map gets data, rather than one map taking it all.
Files land in data/raw/cs2povarchive/<event>/<match>/<file>.dem (or under --out DIR).
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ID = "cs2povarchive/cs2-demos"
KNOWN_MAPS = ("mirage", "inferno", "nuke", "dust2", "ancient", "anubis", "overpass", "train", "vertigo")
POOL = ["mirage", "inferno", "nuke", "dust2", "ancient", "anubis", "overpass"]
PATH_RE = re.compile(
    r"^(?P<event>[^/]+)/(?P<match_id>\d+)-[^/]+/"
    r"(?P<team1>.+?)-vs-(?P<team2>.+?)(?:-m(?P<map_no>\d+))?-(?P<map>" + "|".join(KNOWN_MAPS) + r")"
    r"(?:-p(?P<part>\d+))?(?P<dup>\(\d+\))?\.dem$"
)
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "cs2povarchive"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", nargs="*", default=[], help="event folders (default: all)")
    ap.add_argument("--maps", nargs="*", default=POOL)
    ap.add_argument("--max-gb", type=float, default=40.0, help="budget for new downloads")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    out = a.out.expanduser().resolve()

    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError:
        sys.exit("huggingface_hub is missing: run  python3 -m pip install -U huggingface_hub")

    games = {}
    for e in HfApi().list_repo_tree(REPO_ID, repo_type="dataset", recursive=True):
        path = getattr(e, "path", "")
        m = PATH_RE.match(path)
        if not m or m["dup"] or (a.events and m["event"] not in a.events) or m["map"] not in a.maps:
            continue
        key = (int(m["match_id"]), int(m["map_no"] or 1), m["map"])
        g = games.setdefault(key, {"event": m["event"], "map": m["map"], "parts": [], "bytes": 0,
                                   "label": f"{m['team1']} vs {m['team2']}"})
        g["parts"].append(path)
        g["bytes"] += getattr(e, "size", 0) or 0
    for g in games.values():
        g["parts"].sort(key=lambda p: int(PATH_RE.match(p)["part"] or 0))
        g["have"] = all((out / p).exists() for p in g["parts"])

    by_map = {mp: sorted((k for k, g in games.items() if g["map"] == mp and not g["have"]),
                         key=lambda k: (-k[0], k[1])) for mp in a.maps}
    print("available (new / already on disk) per map:")
    for mp in a.maps:
        have = sum(1 for g in games.values() if g["map"] == mp and g["have"])
        gb = sum(games[k]["bytes"] for k in by_map[mp]) / 1e9
        print(f"  {mp:<9} {len(by_map[mp]):>4} new ({gb:5.1f} GB)   {have:>4} on disk")

    chosen, budget = [], a.max_gb * 1e9
    queues = {mp: list(ks) for mp, ks in by_map.items()}
    while any(queues.values()):
        for mp in a.maps:
            if queues[mp]:
                k = queues[mp].pop(0)
                if games[k]["bytes"] <= budget:
                    chosen.append(k)
                    budget -= games[k]["bytes"]
        if budget <= 0:
            break
    total = sum(games[k]["bytes"] for k in chosen) / 1e9
    print(f"\nselected {len(chosen)} games, {total:.1f} GB (budget {a.max_gb} GB):")
    for mp in a.maps:
        ks = [k for k in chosen if k[2] == mp]
        print(f"  {mp:<9} {len(ks)} games")
    if a.dry_run:
        return

    todo = [p for k in chosen for p in games[k]["parts"]]
    for i, path in enumerate(todo, 1):
        if (out / path).exists():
            continue
        print(f"[{i}/{len(todo)}] {path}", flush=True)
        hf_hub_download(REPO_ID, path, repo_type="dataset", local_dir=out)
    print(f"done -> {out}")


if __name__ == "__main__":
    main()
