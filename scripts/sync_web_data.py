"""Copy exported site data and radar images into web/public for the frontend.

    python scripts/sync_web_data.py            # from data/site (after `python -m playbook run`)
    python scripts/sync_web_data.py --samples  # from samples/site (frontend dev without demos)

Radar images come from the awpy-data GitHub release (downloaded once into ~/.awpy) and are
not committed to this repo.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AWPY_DATA_VERSION = "2000933"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", action="store_true", help="use samples/site instead of data/site")
    args = ap.parse_args()

    src = ROOT / ("samples/site" if args.samples else "data/site")
    dst = ROOT / "web/public/data"
    if not (src / "index.json").exists():
        raise SystemExit(f"{src}/index.json not found; run `python -m playbook run` or use --samples")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"site data: {src} -> {dst}")

    from awpy import data as awpy_data

    radar_dir = ROOT / "web/public/radars"
    radar_dir.mkdir(parents=True, exist_ok=True)
    index = json.loads((src / "index.json").read_text(encoding="utf-8"))
    for m in index["maps"]:
        for name in (m["map"], f"{m['map']}_lower"):
            try:
                path = Path(awpy_data.radar_path(name, version=AWPY_DATA_VERSION))
            except FileNotFoundError:
                continue  # no lower level for this map
            shutil.copy(path, radar_dir / path.name)
            print(f"radar: {path.name}")


if __name__ == "__main__":
    main()
