"""Decode only facing direction for demos referenced by existing replay JSONs.

Run from the repository root with ``.venv/bin/python scripts/reparse_replay_yaw.py``.
Existing ticks/rosters, multipart round ownership and every non-yaw value are
preserved. Only positions parquet files are replaced, atomically per demo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import polars as pl
from awpy import Demo

from playbook.cli import _demo_paths
from playbook.config import PARSED_DIR, RAW_DIR, SITE_DIR
from playbook.multipart import GameDemo
from playbook.parse import demo_identity, position_yaw


def add_yaw(positions: pl.DataFrame, demo) -> pl.DataFrame:
    keys = ["tick", "steamid"]
    original = positions.drop("yaw", strict=False)
    angles = (demo.ticks(["m_angEyeAngles"], players_only=True)
              .with_columns(pl.col("tick").cast(pl.Int64))
              .join(original.select(keys).unique(), on=keys, how="semi")
              .select(*keys, position_yaw()))
    updated = original.join(angles, on=keys, how="left", validate="m:1", maintain_order="left")
    if not updated.drop("yaw").equals(original):
        raise ValueError("Yaw refresh changed existing position values")
    if not updated.filter(pl.col("alive") & pl.col("yaw").is_not_null()).height:
        raise ValueError("No live yaw decoded; check the awpy property name")
    return updated


def metadata_digest(parsed: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(parsed.glob("*/*.parquet")):
        if path.parent.name != "positions":
            digest.update(str(path.relative_to(parsed)).encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW_DIR)
    parser.add_argument("--parsed", type=Path, default=PARSED_DIR)
    parser.add_argument("--site", type=Path, default=SITE_DIR)
    parser.add_argument("--timings", type=Path, default=Path("delegation/GPT-28_yaw_timings.json"))
    args = parser.parse_args()
    started = time.monotonic()
    ids = sorted({p.parent.name for p in args.site.glob("*/replay/*/*.json")})
    raw = {}
    for paths in _demo_paths([args.raw]):
        demo_id = demo_identity(paths[0])["demo_id"]
        if demo_id in ids:
            if demo_id in raw:
                raise ValueError(f"Ambiguous raw recordings for {demo_id}")
            raw[demo_id] = paths
    missing = set(ids) - raw.keys()
    if not ids or missing:
        raise ValueError(f"No replays or missing raw demos: {sorted(missing)}")
    before = metadata_digest(args.parsed)
    records = []
    for i, demo_id in enumerate(ids, 1):
        start = time.monotonic()
        paths = raw[demo_id]
        demo = GameDemo(paths) if len(paths) > 1 else Demo(paths[0])
        target = args.parsed / "positions" / f"{demo_id}.parquet"
        updated = add_yaw(pl.read_parquet(target), demo)
        temporary = target.with_suffix(".parquet.tmp")
        updated.write_parquet(temporary)
        temporary.replace(target)
        live = updated.filter(pl.col("alive"))
        record = dict(demo_id=demo_id, parts=len(paths), rows=updated.height,
                      alive_rows=live.height, alive_yaw_rows=live["yaw"].count(),
                      seconds=round(time.monotonic() - start, 3))
        records.append(record)
        print(f"[{i}/{len(ids)}] {demo_id}: {record['seconds']:.3f}s, "
              f"yaw {record['alive_yaw_rows']}/{live.height} live rows", flush=True)
    after = metadata_digest(args.parsed)
    report = dict(demos=len(records), seconds=round(time.monotonic() - started, 3),
                  metadata_before_sha256=before, metadata_after_sha256=after, records=records)
    args.timings.parent.mkdir(parents=True, exist_ok=True)
    args.timings.write_text(json.dumps(report, indent=2) + "\n")
    if before != after:
        raise ValueError("Non-position tables changed during refresh")
    print(f"Completed in {report['seconds']:.3f}s; non-position tables byte-identical.")


if __name__ == "__main__":
    main()
