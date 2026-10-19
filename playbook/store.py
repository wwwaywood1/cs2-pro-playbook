"""Parquet storage: data/parsed/<table>/<demo_id>.parquet, one file per demo per table.

One file per demo keeps reruns cheap (skip demos already parsed) and lets a failed
demo be retried without touching the rest.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from playbook.config import PARSED_DIR

TABLES = [
    "matches", "players", "rounds", "economy", "loadouts", "positions",
    "kills", "plants", "utility", "shots", "team_rounds", "player_rounds",
]


def write_tables(tables: dict[str, pl.DataFrame], demo_id: str, root: Path = PARSED_DIR) -> None:
    for name, df in tables.items():
        out = root / name / f"{demo_id}.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(out)


def is_parsed(demo_id: str, root: Path = PARSED_DIR) -> bool:
    return all((root / name / f"{demo_id}.parquet").exists() for name in TABLES)


def read_table(name: str, root: Path = PARSED_DIR) -> pl.DataFrame:
    files = sorted((root / name).glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"no parsed data for table '{name}' under {root}")
    return pl.concat([pl.read_parquet(f) for f in files], how="diagonal_relaxed")


def read_all(root: Path = PARSED_DIR) -> dict[str, pl.DataFrame]:
    return {name: read_table(name, root) for name in TABLES if (root / name).exists()}
