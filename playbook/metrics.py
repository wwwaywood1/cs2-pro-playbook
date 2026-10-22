"""Combat rates from player-round counters, independent of heatmap geometry/buys.

Callers restrict input to one map, team and player (and optionally one side).
Semantic kills exclude post-round events and teamkills; every played round counts.
"""
from __future__ import annotations

import polars as pl


def combat_totals(played: pl.DataFrame) -> dict:
    rounds = played.height
    kills = int(played["kills"].sum())
    return {"rounds": rounds, "kills": kills,
            "kpr": round(kills / rounds, 3) if rounds else None}
