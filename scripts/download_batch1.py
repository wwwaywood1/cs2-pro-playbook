"""Download the first batch of pro demos (M1) from Hugging Face.

Standalone on purpose: needs only Python 3.8+ and huggingface_hub, so it runs on any
machine that can reach huggingface.co (the pipeline itself needs Python 3.11+).

    python3 -m pip install -U huggingface_hub
    python3 scripts/download_batch1.py            # download
    python3 scripts/download_batch1.py --dry-run  # only list what would be downloaded
    python3 download_batch1.py --out ~/Downloads/cs2-pro-playbook/data/raw/cs2povarchive

Selection (mirrors config/targets.toml and playbook/fetch.py):
  - IEM Cologne Major 2026, Mirage + Inferno, single-file games, newest first, 60 games
  - plus the newest single-file game of each other map in the pool (callout lists)
Files land in data/raw/cs2povarchive/<event>/<match>/<file>.dem next to this repo
(or under --out DIR). The pipeline reads that tree directly (python -m playbook parse data/raw).
Re-running skips files already downloaded.
"""

import re
import sys
from pathlib import Path

REPO_ID = "cs2povarchive/cs2-demos"
EVENTS = {"iem_cologne_major_2026"}
MAPS = {"mirage", "inferno"}
MAX_GAMES = 60
EXTRA_ONE_PER_MAP = ["nuke", "dust2", "ancient", "anubis", "overpass"]

KNOWN_MAPS = ("mirage", "inferno", "nuke", "dust2", "ancient", "anubis", "overpass", "train", "vertigo")
PATH_RE = re.compile(
    r"^(?P<event>[^/]+)/(?P<match_id>\d+)-[^/]+/"
    r"(?P<team1>.+?)-vs-(?P<team2>.+?)(?:-m(?P<map_no>\d+))?-(?P<map>" + "|".join(KNOWN_MAPS) + r")"
    r"(?:-p(?P<part>\d+))?(?P<dup>\(\d+\))?\.dem$"
)
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "cs2povarchive"


def main() -> None:
    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError:
        sys.exit("huggingface_hub is missing: run  python3 -m pip install -U huggingface_hub")

    files = [
        (e.path, getattr(e, "size", 0) or 0)
        for e in HfApi().list_repo_tree(REPO_ID, repo_type="dataset", recursive=True)
        if getattr(e, "path", "").endswith(".dem")
    ]
    games = {}
    for path, size in files:
        m = PATH_RE.match(path)
        if not m or m["dup"]:
            continue
        key = (int(m["match_id"]), int(m["map_no"] or 1), m["map"])
        g = games.setdefault(key, {"event": m["event"], "map": m["map"], "parts": [], "bytes": 0,
                                   "label": f"{m['team1']} vs {m['team2']}"})
        g["parts"].append(path)
        g["bytes"] += size

    pool = sorted(
        (k, g) for k, g in games.items() if len(g["parts"]) == 1 and g["event"] in EVENTS
    )
    pool.sort(key=lambda kg: (-kg[0][0], kg[0][1]))  # newest match first
    batch = [kg for kg in pool if kg[1]["map"] in MAPS][:MAX_GAMES]
    extra = [next(kg for kg in pool if kg[1]["map"] == mp) for mp in EXTRA_ONE_PER_MAP
             if any(kg[1]["map"] == mp for kg in pool)]

    for label, chosen in (("batch", batch), ("one per extra map", extra)):
        gb = sum(g["bytes"] for _, g in chosen) / 1e9
        print(f"{label}: {len(chosen)} games, {gb:.1f} GB")
        for (mid, mno, mp), g in chosen:
            print(f"  {mid} m{mno} {mp:<8} {g['label']}")
    if "--dry-run" in sys.argv:
        return

    out = OUT
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1]).expanduser().resolve()

    todo = [g["parts"][0] for _, g in batch + extra]
    for i, path in enumerate(todo, 1):
        if (out / path).exists():
            print(f"[{i}/{len(todo)}] already there: {path}")
            continue
        print(f"[{i}/{len(todo)}] {path}")
        hf_hub_download(REPO_ID, path, repo_type="dataset", local_dir=out)
    print(f"done -> {out}")


if __name__ == "__main__":
    main()
