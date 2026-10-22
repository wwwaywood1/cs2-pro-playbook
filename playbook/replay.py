"""2D round replays: positions per second, kills, grenade pops, the plant and T win probability.

One small JSON per round, `data/site/<map>/replay/<demo_id>/<round>.json`, for the showcase
teams' matches and the example rounds of every execute recipe. Coordinates are radar pixels
(1024 x 1024 image), rounded to integers; positions are sampled at 1 Hz like the parsed tables.

    {"demo_id", "round_num", "map", "teams": {"T", "CT"}, "winner": "T"|"CT", "duration": s,
     "players": [{"name", "side", "team"}],          # index = column in frames
     "frames": [[[x, y] | null, ...], ...],          # one row per second; null = dead / not seen
     "events": [{"t", "kind": "kill"|"util"|"plant", ...}],
     "wp_t": [p, ...]}                               # T win probability per second (may be empty)
"""

from __future__ import annotations

import numpy as np
import polars as pl

from playbook.config import MapMeta

KEYS = ["demo_id", "round_num"]
UTIL_KINDS = {"smoke": "smoke", "flashbang": "flash", "flash": "flash", "molotov": "molotov",
              "incendiary": "molotov", "he": "he", "hegrenade": "he"}


def _px(mm: MapMeta, x: float | None, y: float | None) -> list[int] | None:
    if x is None or y is None:
        return None
    rx, ry = mm.to_radar(float(x), float(y))
    return [int(round(rx)), int(round(ry))]


def build_round(sub: dict[str, pl.DataFrame], mm: MapMeta, demo: str, rnd: int,
                wp: list[float] | None = None) -> dict | None:
    key = (pl.col("demo_id") == demo) & (pl.col("round_num") == rnd)
    r = sub["rounds"].filter(key)
    pos = sub["positions"].filter(key & (pl.col("t_s") >= 0)).sort("t_s")
    if r.is_empty() or pos.is_empty():
        return None
    r0 = r.row(0, named=True)
    dur = int(np.ceil(float(r0["dur_s"])))
    roster = (pos.group_by("steamid").agg(pl.col("name").mode().first(), pl.col("side").first(), pl.col("team").first())
              .sort("side", "name", descending=[True, False]))
    sids = roster["steamid"].to_list()
    index = {s: i for i, s in enumerate(sids)}
    frames: list[list] = [[None] * len(sids) for _ in range(dur + 1)]
    for sid, t, x, y, alive in pos.select("steamid", "t_s", "x", "y", "alive").iter_rows():
        if 0 <= t <= dur and alive:
            frames[t][index[sid]] = _px(mm, x, y)
    events: list[dict] = []
    k = sub["kills"].filter(key & ~pl.col("is_post_round"))
    for row in k.iter_rows(named=True):
        events.append({"t": round(float(row["t_s"]), 1), "kind": "kill",
                       "by": index.get(row["attacker_steamid"]), "victim": index.get(row["victim_steamid"]),
                       "at": _px(mm, row["victim_x"], row["victim_y"]), "weapon": row["weapon"],
                       "headshot": bool(row.get("headshot"))})
    u = sub["utility"].filter(key & ~pl.col("is_post_round") & pl.col("pop_t_s").is_not_null()
                              & pl.col("land_x").is_not_null())
    for row in u.iter_rows(named=True):
        kind = UTIL_KINDS.get(str(row["type"]).lower())
        if kind:
            events.append({"t": round(float(row["pop_t_s"]), 1), "kind": "util", "nade": kind,
                           "by": index.get(row["thrower_steamid"]), "at": _px(mm, row["land_x"], row["land_y"]),
                           "from": _px(mm, row.get("throw_x"), row.get("throw_y"))})
    p = sub["plants"].filter(key)
    for row in p.head(1).iter_rows(named=True):
        events.append({"t": round(float(row["t_s"]), 1), "kind": "plant", "site": row["site"],
                       "at": _px(mm, row["x"], row["y"])})
    events.sort(key=lambda e: e["t"])
    return {
        "demo_id": demo, "round_num": int(rnd), "map": mm.name,
        "teams": {"T": r0["t_team"], "CT": r0["ct_team"]}, "winner": r0["winner_side"],
        "reason": r0.get("reason"), "duration": dur,
        "players": [{"name": n, "side": s, "team": tm} for n, s, tm in roster.select("name", "side", "team").iter_rows()],
        "frames": frames, "events": events, "wp_t": [round(float(v), 3) for v in (wp or [])],
    }


def wp_by_round(states: pl.DataFrame, oof: np.ndarray, rounds: set[tuple[str, int]]) -> dict[tuple[str, int], list[float]]:
    """T win probability per second for the requested rounds (out-of-fold values from winprob)."""
    if not rounds:
        return {}
    demos = sorted({d for d, _ in rounds})
    mask = states["demo_id"].is_in(demos).to_numpy()
    s = states.filter(mask).select(*KEYS, "t_s").with_columns(pl.Series("wp", oof[mask]))
    out: dict[tuple[str, int], list[float]] = {}
    for (demo, rnd), g in s.group_by(KEYS, maintain_order=True):
        if (demo, rnd) in rounds:
            out[(demo, int(rnd))] = g.sort("t_s")["wp"].to_list()
    return out
