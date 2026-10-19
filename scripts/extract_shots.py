"""Add the `shots` table (gun fire events) to demos parsed before it existed.

    python scripts/extract_shots.py data/raw [--parsed data/parsed] [--budget 140]

Only the weapon_fire events are read (much faster than a full parse). Rounds come
from the stored `rounds` table, so round numbers match the other tables exactly.
Writes data/parsed/shots/<demo_id>.parquet and skips demos that already have one.
--budget stops starting new demos after that many seconds (rerun to continue), which
suits shells that limit how long one command may run.

New parses include the table already (playbook.parse.shots_table).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playbook.parse import demo_identity, shots_table  # noqa: E402

MULTIPART = ("-p1", "-p2", "-p3", "(1)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--parsed", type=Path, default=ROOT / "data" / "parsed")
    ap.add_argument("--budget", type=float, default=0, help="seconds; 0 = no limit")
    a = ap.parse_args()

    from awpy import Demo

    demos = sorted(p for i in a.inputs for p in (i.rglob("*.dem") if i.is_dir() else [i]))
    demos = [p for p in demos if not p.stem.endswith(MULTIPART) and "(1)" not in p.stem]
    t0 = time.time()
    done = skipped = 0
    for path in demos:
        demo_id = demo_identity(path)["demo_id"]
        out = a.parsed / "shots" / f"{demo_id}.parquet"
        if out.exists():
            skipped += 1
            continue
        if not (a.parsed / "rounds" / f"{demo_id}.parquet").exists():
            print(f"{demo_id}: not parsed yet, skipping")
            continue
        if a.budget and time.time() - t0 > a.budget:
            break
        t = time.time()
        demo = Demo(path)
        demo.load("shots")
        rounds = pl.read_parquet(a.parsed / "rounds" / f"{demo_id}.parquet")
        loadouts = pl.read_parquet(a.parsed / "loadouts" / f"{demo_id}.parquet")
        rate = float(pl.read_parquet(a.parsed / "matches" / f"{demo_id}.parquet")["tick_rate"][0])
        shots = shots_table(demo.shots, rounds, loadouts, demo_id, rate)
        out.parent.mkdir(parents=True, exist_ok=True)
        shots.write_parquet(out)
        done += 1
        print(f"{demo_id}: {shots.height} shots ({time.time() - t:.0f}s)", flush=True)
    remaining = len(demos) - skipped - done
    print(f"done {done}, already had {skipped}, remaining {remaining}")


if __name__ == "__main__":
    main()
