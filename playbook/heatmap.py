"""Heatmaps: where a player (or team) spends time, holds, shoots and throws utility.

Each layer is counted on a GRID x GRID grid over the 1024 px radar image, separately
per side (T/CT) and round phase, and divided by the number of rounds played on that
side, so values are "per round" rates (seconds, shots or grenades per round per cell).
The site combines layers by first turning each into a share of its own total, then
weighting (sliders, default 1:1:1), because seconds, shots and grenades are not
comparable units.

Layers
  presence    living seconds in the cell (positions are sampled once per second)
  holding     living seconds moving less than HOLD_SPEED units in that second
              (holding an angle rather than passing through)
  shots       gun fire events (shots table), by shooter position
  util_throw  grenades thrown, by release position
  util_land   grenades thrown, by landing position
  kills       kills, by attacker position
  deaths      deaths, by victim position
Phases
  post   after the plant (post-plant for T, retake for CT); takes precedence
  early  round time < EARLY_S (setups, early map control)
  mid    the rest: from EARLY_S until the plant or round end
Levels
  maps with two floors (Nuke) put points below lower_level_max_z on level 1.
Cell index = level * GRID * GRID + row * GRID + col.
"""

from __future__ import annotations

import math

import numpy as np
import polars as pl

from playbook.config import MapMeta, team_slug

GRID = 64
CELL_PX = 1024 / GRID
EARLY_S = 20
HOLD_SPEED = 40.0
LAYERS = ("presence", "holding", "shots", "util_throw", "util_land", "kills", "deaths")
PHASES = ("early", "mid", "post")
SIDES = ("T", "CT")
KEYS = ["demo_id", "round_num"]


def _cells(df: pl.DataFrame, mm: MapMeta, x: str, y: str, z: str) -> pl.DataFrame:
    """Add `cell` (or drop rows that fall outside the radar)."""
    r = mm.radar
    col = ((pl.col(x) - r["pos_x"]) / r["scale"] / CELL_PX).floor().cast(pl.Int64)
    row = ((r["pos_y"] - pl.col(y)) / r["scale"] / CELL_PX).floor().cast(pl.Int64)
    level = pl.lit(0, dtype=pl.Int64)
    if "lower_level_max_z" in r:
        level = pl.when(pl.col(z) < r["lower_level_max_z"]).then(1).otherwise(0).cast(pl.Int64)
    return (
        df.with_columns(_col=col, _row=row, _lvl=level)
        .filter(pl.col("_col").is_between(0, GRID - 1) & pl.col("_row").is_between(0, GRID - 1))
        .with_columns(cell=pl.col("_lvl") * GRID * GRID + pl.col("_row") * GRID + pl.col("_col"))
        .drop("_col", "_row", "_lvl")
    )


def _phase(t_col: str) -> pl.Expr:
    return (
        pl.when(pl.col("plant_t_s").is_not_null() & (pl.col(t_col) >= pl.col("plant_t_s"))).then(pl.lit("post"))
        .when(pl.col(t_col) < EARLY_S).then(pl.lit("early"))
        .otherwise(pl.lit("mid"))
    )


def events(sub: dict[str, pl.DataFrame], mm: MapMeta) -> pl.DataFrame:
    """One row per counted event: steamid, team, side, phase, layer, cell, weight."""
    plant = sub["team_rounds"].filter(pl.col("side") == "T").select(*KEYS, "plant_t_s")
    out = []

    pos = sub["positions"].filter(pl.col("alive") & (pl.col("t_s") >= 0)).sort(*KEYS, "steamid", "t_s")
    prev = pl.col("x").shift(1).over(*KEYS, "steamid"), pl.col("y").shift(1).over(*KEYS, "steamid")
    pos = pos.with_columns(
        step=((pl.col("x") - prev[0]) ** 2 + (pl.col("y") - prev[1]) ** 2).sqrt(),
        gap=pl.col("t_s") - pl.col("t_s").shift(1).over(*KEYS, "steamid"),
    )
    pos = _cells(pos.join(plant, on=KEYS, how="left"), mm, "x", "y", "z").with_columns(phase=_phase("t_s"))
    base = ["steamid", "team", "side", "phase", "cell"]
    out.append(pos.select(*base, layer=pl.lit("presence"), w=pl.lit(1.0)))
    out.append(pos.filter((pl.col("gap") == 1) & (pl.col("step") < HOLD_SPEED)).select(*base, layer=pl.lit("holding"), w=pl.lit(1.0)))

    if "shots" in sub and not sub["shots"].is_empty():
        sh = sub["shots"].filter(~pl.col("is_post_round") & (pl.col("t_s") >= 0)).join(plant, on=KEYS, how="left")
        sh = _cells(sh, mm, "x", "y", "z").with_columns(phase=_phase("t_s"))
        out.append(sh.select(*base, layer=pl.lit("shots"), w=pl.lit(1.0)))

    u = sub["utility"].filter(~pl.col("is_post_round") & pl.col("thrower_steamid").is_not_null() & pl.col("thrower_side").is_not_null())
    u = u.join(plant, on=KEYS, how="left").rename({"thrower_steamid": "steamid", "thrower_team": "team", "thrower_side": "side"})
    thr = _cells(u.filter(pl.col("throw_x").is_not_null()), mm, "throw_x", "throw_y", "throw_z").with_columns(phase=_phase("throw_t_s"))
    out.append(thr.select(*base, layer=pl.lit("util_throw"), w=pl.lit(1.0)))
    land = _cells(u.filter(pl.col("land_x").is_not_null()), mm, "land_x", "land_y", "land_z").with_columns(phase=_phase("throw_t_s"))
    out.append(land.select(*base, layer=pl.lit("util_land"), w=pl.lit(1.0)))

    k = sub["kills"].filter(~pl.col("is_post_round")).join(plant, on=KEYS, how="left")
    kk = k.filter(~pl.col("is_teamkill").fill_null(True) & pl.col("attacker_steamid").is_not_null() & pl.col("attacker_x").is_not_null())
    kk = _cells(kk.rename({"attacker_steamid": "steamid", "attacker_team": "team", "attacker_side": "side"}),
                mm, "attacker_x", "attacker_y", "attacker_z").with_columns(phase=_phase("t_s"))
    out.append(kk.select(*base, layer=pl.lit("kills"), w=pl.lit(1.0)))
    dd = _cells(k.rename({"victim_steamid": "steamid", "victim_team": "team", "victim_side": "side"}),
                mm, "victim_x", "victim_y", "victim_z").with_columns(phase=_phase("t_s"))
    out.append(dd.select(*base, layer=pl.lit("deaths"), w=pl.lit(1.0)))

    ev = pl.concat([e.with_columns(pl.col("steamid").cast(pl.UInt64), pl.col("cell").cast(pl.Int64)) for e in out])
    return ev.filter(pl.col("side").is_in(SIDES) & pl.col("team").is_not_null())


def _pack(g: pl.DataFrame, rounds: int) -> list:
    """Sparse cells as a flat list [cell, value, cell, value, ...], values per round."""
    flat: list = []
    for cell, w in g.sort("cell").select("cell", "w").iter_rows():
        v = w / rounds
        flat.extend((int(cell), float(f"{v:.3g}")))
    return flat


def _grids(ev: pl.DataFrame, rounds: dict[str, int]) -> dict:
    agg = ev.group_by("side", "phase", "layer", "cell").agg(w=pl.col("w").sum())
    data: dict = {}
    for (side, phase, layer), g in agg.group_by("side", "phase", "layer"):
        n = rounds.get(side, 0)
        if n:
            data.setdefault(side, {}).setdefault(phase, {})[layer] = _pack(g, n)
    sums = ev.group_by("side", "phase", "layer").agg(w=pl.col("w").sum())
    totals: dict = {}
    for side, phase, layer, w in sums.iter_rows():
        n = rounds.get(side, 0)
        if n:
            totals.setdefault(side, {}).setdefault(phase, {})[layer] = round(w / n, 3)
    for side, by_phase in totals.items():
        by_phase["all"] = {layer: round(sum(p.get(layer, 0.0) for p in by_phase.values()), 3) for layer in LAYERS}
    return {"rounds": rounds, "per_round": totals, "data": data}


def build_heatmaps(sub: dict[str, pl.DataFrame], mm: MapMeta) -> dict:
    """{'meta': ..., 'players': {steamid: {...}}, 'teams': {slug: {...}}} for one map."""
    ev = events(sub, mm)
    pr = sub["player_rounds"]
    tr = sub["team_rounds"]

    players = {}
    for (sid,), d in pr.filter(pl.col("steamid").is_not_null()).group_by("steamid"):
        rounds = {s: d.filter(pl.col("side") == s).height for s in SIDES}
        g = _grids(ev.filter(pl.col("steamid") == sid), rounds)
        players[str(sid)] = {"steamid": str(sid), "name": d["name"].mode().first(), "team": d["team"].mode().first(),
                             "n_matches": d["demo_id"].n_unique(), **g}

    teams = {}
    for (team,), d in tr.filter(pl.col("team").is_not_null()).group_by("team"):
        rounds = {s: d.filter(pl.col("side") == s).height for s in SIDES}
        g = _grids(ev.filter(pl.col("team") == team), rounds)
        teams[team_slug(team)] = {"team": team, "slug": team_slug(team), "n_matches": d["demo_id"].n_unique(), **g}

    # Baseline: every team on this map, per team-round, for "this team vs everyone" views.
    all_rounds = {s: tr.filter(pl.col("side") == s).height for s in SIDES}
    baseline = _grids(ev, all_rounds)
    levels = 2 if "lower_level_max_z" in mm.radar else 1
    meta = {
        "map": mm.name, "grid": GRID, "cell_px": CELL_PX, "levels": levels,
        "layers": list(LAYERS), "phases": list(PHASES), "sides": list(SIDES),
        "early_s": EARLY_S, "hold_speed": HOLD_SPEED,
        "value": "per round: seconds (presence, holding) or counts (shots, utility, kills, deaths) per cell",
        "cell_index": "level * grid * grid + row * grid + col",
        "default_weights": {"presence": 1, "shots": 1, "util_throw": 1},
        **baseline,
    }
    return {"baseline": meta, "players": players, "teams": teams}


def to_array(flat: list, levels: int = 1) -> np.ndarray:
    """Unpack a sparse list into a (levels, GRID, GRID) array."""
    a = np.zeros(levels * GRID * GRID)
    for i in range(0, len(flat), 2):
        a[int(flat[i])] = flat[i + 1]
    return a.reshape(levels, GRID, GRID)


def combine(layers: dict[str, list], weights: dict[str, float], levels: int = 1) -> np.ndarray:
    """What the site draws: each layer as a share of its own total, then weighted."""
    out = np.zeros((levels, GRID, GRID))
    for name, w in weights.items():
        if not w or name not in layers:
            continue
        a = to_array(layers[name], levels)
        s = a.sum()
        if s > 0 and math.isfinite(s):
            out += w * a / s
    return out
