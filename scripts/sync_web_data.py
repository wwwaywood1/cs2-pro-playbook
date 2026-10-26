"""Copy exported site data and radar images into web/public for the frontend.

    python scripts/sync_web_data.py                 # from data/site (after `python -m playbook run`)
    python scripts/sync_web_data.py --samples       # from samples/site (frontend dev without demos)
    python scripts/sync_web_data.py --site DIR      # from another export directory

The copy replaces web/public/data completely, so files a newer export no longer writes
do not linger. When the source lacks the small derived indexes (search_index.json and
<map>/lineup_index.json, playbook/site_index.py), they are generated in the copy.

Radar images come from the awpy-data GitHub release (downloaded once into ~/.awpy) and are
not committed to this repo. They are copied for every exported map and for every map of the
teams-hub orbit pool, which the hub draws even when an export has no data for it.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AWPY_DATA_VERSION = "2000933"


def orbit_pool() -> list[str]:
    """Map ids of ORBIT_POOL in web/src/pages/teamsHubOrbit.ts (the hub always shows them)."""
    try:
        source = (ROOT / "web/src/pages/teamsHubOrbit.ts").read_text(encoding="utf-8")
    except OSError:
        return []
    block = source.partition("export const ORBIT_POOL")[2].partition("] as const")[0]
    return re.findall(r'\[\s*"(de_\w+)"', block)


def main() -> None:
    ap = argparse.ArgumentParser()
    source = ap.add_mutually_exclusive_group()
    source.add_argument("--samples", action="store_true", help="use samples/site instead of data/site")
    source.add_argument("--site", type=Path, help="copy this export directory instead of data/site")
    args = ap.parse_args()

    src = args.site.resolve() if args.site else ROOT / ("samples/site" if args.samples else "data/site")
    dst = ROOT / "web/public/data"
    if not (src / "index.json").exists():
        raise SystemExit(f"{src}/index.json not found; run `python -m playbook run` or use --samples")
    if dst.exists():
        shutil.rmtree(dst)
    # macOS sidecar files (._*, .DS_Store) ride along when an export is packed with tar on a Mac
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("._*", ".DS_Store"))
    print(f"site data: {src} -> {dst}")

    index = json.loads((src / "index.json").read_text(encoding="utf-8"))
    if not (dst / "search_index.json").exists() or any(
            not (dst / m["map"] / "lineup_index.json").exists() and (dst / m["map"] / "lineups.json").exists()
            for m in index["maps"]):
        sys.path.insert(0, str(ROOT))
        from playbook.site_index import write_site_indexes
        write_site_indexes(dst)
        print("site indexes: generated search_index.json and lineup_index.json")

    from awpy import data as awpy_data

    radar_dir = ROOT / "web/public/radars"
    radar_dir.mkdir(parents=True, exist_ok=True)
    # The teams-hub orbit draws every pool map, with or without data in this export.
    maps = list(dict.fromkeys([m["map"] for m in index["maps"]] + orbit_pool()))
    for map_name in maps:
        for name in (map_name, f"{map_name}_lower"):
            try:
                path = Path(awpy_data.radar_path(name, version=AWPY_DATA_VERSION))
            except FileNotFoundError:
                continue  # no lower level for this map
            shutil.copy(path, radar_dir / path.name)
            print(f"radar: {path.name}")


if __name__ == "__main__":
    main()
