"""Team heatmaps: where each of a team's players stands, holds, fights and lands utility.

Built per team, with every player's grids restricted to the rounds he played for that
team, so the site can show one team, one side, and its players in five colours.

Cleaning (the same frames feed playbook/zones.py, the summaries tactics build on)
  - gun rounds only (the player's team bought full or force); pistol and eco rounds
    have different positions and would blur the picture
  - living players only, live round time only (no freeze time, no post-round)
  - presence/holding skip the first SPAWN_SKIP_S seconds (everyone walking out of spawn)
Layers (counted on a GRID x GRID grid over the 1024 px radar, per side and phase)
  presence  living seconds in the cell (positions are sampled once per second)
  holding   living seconds moving less than HOLD_SPEED units in that second
  shots     gun fire events, at the shooter
  kills     at the attacker;  deaths  at the victim
  smoke / flash / molotov / he   grenades at their LANDING point (where they were thrown
            from is in the lineup library, not here)
Phases
  post   after the plant (post-plant for T, retake for CT); takes precedence
  early  round time < EARLY_S
  mid    the rest
Values are per round played on that side (seconds or counts per cell).
Cell index = level * GRID * GRID + row * GRID + col; Nuke-style maps put points below
lower_level_max_z on level 1.
"""

from __future__ import annotations

import math

import numpy as np
import polars as pl

from playbook.config import MapMeta, team_slug
from playbook.semantics import round_plants

GRID = 64
CELL_PX = 1024 / GRID
EARLY_S = 20
SPAWN_SKIP_S = 5
HOLD_SPEED = 40.0
GUN_BUYS = ("full", "force")
MIN_RELIABLE_ROUNDS = 20  # per player and side; below this the site flags the player
LAYERS = ("presence", "holding", "shots", "kills", "deaths", "smoke", "flash", "molotov", "he")
UTIL_LAYER = {"smoke": "smoke", "flashbang": "flash", "molotov": "molotov", "he": "he"}
PHASES = ("early", "mid", "post")
SIDES = ("T", "CT")
N_COLORS = 5  # red, blue, purple, green, orange on the site
KEYS = ["demo_id", "round_num"]


def _cells(df: pl.DataFrame, mm: MapMeta, x: str, y: str, z: str) -> pl.DataFrame:
    """Add radar pixel coordinates and `cell`; drop rows outside the radar."""
    df = df.filter(pl.all_horizontal(pl.col(c).is_finite() for c in (x, y, z)))
    r = mm.radar
    level = pl.lit(0, dtype=pl.Int64)
    if "lower_level_max_z" in r:
        level = pl.when(pl.col(z) < r["lower_level_max_z"]).then(1).otherwise(0).cast(pl.Int64)
    return (
        df.with_columns(
            radar_x=(pl.col(x) - r["pos_x"]) / r["scale"],
            radar_y=(r["pos_y"] - pl.col(y)) / r["scale"],
            _lvl=level,
        )
        .with_columns(
            _col=(pl.col("radar_x") / CELL_PX).floor().cast(pl.Int64),
            _row=(pl.col("radar_y") / CELL_PX).floor().cast(pl.Int64),
        )
        .filter(pl.col("_col").is_between(0, GRID - 1) & pl.col("_row").is_between(0, GRID - 1))
        .with_columns(cell=pl.col("_lvl") * GRID * GRID + pl.col("_row") * GRID + pl.col("_col"), level=pl.col("_lvl"))
        .drop("_col", "_row", "_lvl")
    )


def _phase(t_col: str) -> pl.Expr:
    return (
        pl.when(pl.col("plant_t_s").is_not_null() & (pl.col(t_col) >= pl.col("plant_t_s"))).then(pl.lit("post"))
        .when(pl.col(t_col) < EARLY_S).then(pl.lit("early"))
        .otherwise(pl.lit("mid"))
    )


def clean_frames(sub: dict[str, pl.DataFrame], mm: MapMeta) -> dict[str, pl.DataFrame]:
    """Cleaned event frames (gun rounds, living players, live time), each with
    steamid, team, side, phase, cell, radar_x/y. Keys: presence, shots, kills, deaths, utility."""
    tr = sub["team_rounds"]
    gun = tr.filter(pl.col("buy_type").is_in(GUN_BUYS)).select(*KEYS, "team")
    plant = round_plants(sub).select(*KEYS, "plant_t_s")

    def prep(df: pl.DataFrame) -> pl.DataFrame:
        return df.join(gun, on=[*KEYS, "team"], how="inner", validate="m:1").join(plant, on=KEYS, how="left", validate="m:1")

    pos = sub["positions"].filter(pl.col("alive") & (pl.col("t_s") >= 0)).sort(*KEYS, "steamid", "t_s")
    pos = pos.with_columns(
        step=((pl.col("x") - pl.col("x").shift(1).over(*KEYS, "steamid")) ** 2
              + (pl.col("y") - pl.col("y").shift(1).over(*KEYS, "steamid")) ** 2
              + (pl.col("z") - pl.col("z").shift(1).over(*KEYS, "steamid")) ** 2).sqrt(),
        gap=pl.col("t_s") - pl.col("t_s").shift(1).over(*KEYS, "steamid"),
    ).filter(pl.col("t_s") >= SPAWN_SKIP_S)
    pos = _cells(prep(pos), mm, "x", "y", "z").with_columns(
        phase=_phase("t_s"), holding=(pl.col("gap") == 1) & (pl.col("step") < HOLD_SPEED)
    ).select(*KEYS, "steamid", "name", "team", "side", "t_s", "phase", "x", "y", "z", "place", "region", "lane",
             "holding", "cell", "level", "radar_x", "radar_y")

    shot_cols = [*KEYS, "steamid", "team", "side", "t_s", "phase", "cell", "level", "radar_x", "radar_y"]
    out = {"presence": pos}
    if "shots" in sub and not sub["shots"].is_empty():
        sh = sub["shots"].filter(~pl.col("is_post_round") & (pl.col("t_s") >= 0))
        out["shots"] = _cells(prep(sh), mm, "x", "y", "z").with_columns(phase=_phase("t_s")).select(shot_cols)
    else:
        out["shots"] = pos.head(0).select(shot_cols)

    k = sub["kills"].filter(~pl.col("is_post_round") & (pl.col("t_s") >= 0))
    kills = k.filter(~pl.col("is_teamkill").fill_null(True) & pl.col("attacker_steamid").is_not_null()
                     & pl.col("attacker_x").is_not_null())
    kills = kills.rename({"attacker_steamid": "steamid", "attacker_team": "team", "attacker_side": "side",
                          "attacker_place": "place"})
    fight_cols = [*KEYS, "steamid", "team", "side", "t_s", "phase", "place", "is_opening", "cell", "level", "radar_x", "radar_y"]
    out["kills"] = _cells(prep(kills), mm, "attacker_x", "attacker_y", "attacker_z").with_columns(
        phase=_phase("t_s")).select(fight_cols)
    deaths = k.rename({"victim_steamid": "steamid", "victim_team": "team", "victim_side": "side", "victim_place": "place"})
    out["deaths"] = _cells(prep(deaths), mm, "victim_x", "victim_y", "victim_z").with_columns(
        phase=_phase("t_s")).select(fight_cols)

    u = sub["utility"].filter(
        ~pl.col("is_post_round") & (pl.col("throw_t_s") >= 0) & pl.col("thrower_steamid").is_not_null() & pl.col("thrower_side").is_not_null()
        & pl.col("land_x").is_not_null() & pl.col("type").is_in(list(UTIL_LAYER))
    ).rename({"thrower_steamid": "steamid", "thrower_team": "team", "thrower_side": "side"})
    out["utility"] = _cells(prep(u), mm, "land_x", "land_y", "land_z").with_columns(
        phase=_phase("throw_t_s"), layer=pl.col("type").replace_strict(UTIL_LAYER),
    ).select(*KEYS, "nade_id", "steamid", "team", "side", "type", "layer", "throw_t_s", "phase", "land_place",
             "land_x", "land_y", "land_z", "cell", "level", "radar_x", "radar_y")
    for name in out:
        out[name] = out[name].with_columns(pl.col("steamid").cast(pl.UInt64)).filter(
            pl.col("side").is_in(SIDES) & pl.col("team").is_not_null())
    return out


def events(frames: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """steamid, team, side, phase, layer, cell, w (one row per counted event)."""
    base = ["steamid", "team", "side", "phase", "cell"]
    p = frames["presence"]
    parts = [
        p.select(*base, layer=pl.lit("presence")),
        p.filter(pl.col("holding")).select(*base, layer=pl.lit("holding")),
        frames["shots"].select(*base, layer=pl.lit("shots")),
        frames["kills"].select(*base, layer=pl.lit("kills")),
        frames["deaths"].select(*base, layer=pl.lit("deaths")),
        frames["utility"].select(*base, "layer"),
    ]
    return pl.concat(parts).with_columns(w=pl.lit(1.0))


def _pack(g: pl.DataFrame, rounds: int) -> list:
    """Sparse cells as a flat list [cell, value, cell, value, ...], values per round."""
    flat: list = []
    for cell, w in g.sort("cell").select("cell", "w").iter_rows():
        flat.extend((int(cell), float(f"{w / rounds:.3g}")))
    return flat


def grids(ev: pl.DataFrame, rounds: dict[str, int]) -> dict:
    """{'per_round': {side: {phase|all: {layer: v}}}, 'data': {side: {phase: {layer: sparse}}}}."""
    agg = ev.group_by("side", "phase", "layer", "cell").agg(w=pl.col("w").sum()).sort("side", "phase", "layer")
    data: dict = {}
    for (side, phase, layer), g in agg.group_by("side", "phase", "layer", maintain_order=True):
        n = rounds.get(side, 0)
        if n:
            data.setdefault(side, {}).setdefault(phase, {})[layer] = _pack(g, n)
    totals: dict = {}
    for side, phase, layer, w in ev.group_by("side", "phase", "layer").agg(w=pl.col("w").sum()).sort(
            "side", "phase", "layer").iter_rows():
        n = rounds.get(side, 0)
        if n:
            totals.setdefault(side, {}).setdefault(phase, {})[layer] = round(w / n, 3)
    for side, by_phase in totals.items():
        by_phase["all"] = {layer: round(sum(p.get(layer, 0.0) for p in by_phase.values()), 3) for layer in LAYERS}
    return {"per_round": totals, "data": data}


def roster_order(player_rounds: pl.DataFrame) -> dict[str, list[str]]:
    """Per team, steamids by rounds played (all maps), then name. The site gives the first
    five the colours red, blue, purple, green, orange, so a player keeps his colour on
    every map and side."""
    g = (
        player_rounds.filter(pl.col("team").is_not_null() & pl.col("steamid").is_not_null())
        .group_by("team", "steamid").agg(n=pl.len(), name=pl.col("name").mode().sort().first())
        .with_columns(_key=pl.col("name").str.to_lowercase())
        .sort("team", "n", "_key", "steamid", descending=[False, True, False, False])
    )
    return {team: [str(s) for s in d["steamid"].to_list()] for (team,), d in g.group_by("team", maintain_order=True)}


def gun_rounds(sub: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """player_rounds restricted to gun rounds of the player's team."""
    return sub["player_rounds"].filter(pl.col("buy_type").is_in(GUN_BUYS) & pl.col("steamid").is_not_null())


def build_heatmaps(sub: dict[str, pl.DataFrame], mm: MapMeta, order: dict[str, list[str]] | None = None,
                   summaries=None) -> dict:
    """{'baseline': ..., 'teams': {slug: {...}}, 'frames': cleaned frames} for one map.

    `summaries(frames, team, steamid, side, rounds)` (see playbook.zones) adds the
    per-player summary; leave it None for grids only."""
    frames = clean_frames(sub, mm)
    ev = events(frames)
    pr = gun_rounds(sub)
    tr = sub["team_rounds"].filter(pl.col("buy_type").is_in(GUN_BUYS))
    order = order or roster_order(sub["player_rounds"])

    teams = {}
    for (team,), td in tr.filter(pl.col("team").is_not_null()).group_by("team", maintain_order=True):
        team_rounds = {s: td.filter(pl.col("side") == s).height for s in SIDES}
        tev = ev.filter(pl.col("team") == team)
        mine = pr.filter(pl.col("team") == team)
        global_order = order.get(team, [])
        here = {str(s) for s in mine["steamid"].unique().to_list()}
        ranked = [s for s in global_order if s in here] + sorted(here - set(global_order))
        roster, players, summary = [], {}, {}
        for steamid in ranked:
            d = mine.filter(pl.col("steamid") == int(steamid))
            rounds = {s: d.filter(pl.col("side") == s).height for s in SIDES}
            color = global_order.index(steamid) if steamid in global_order else len(global_order)
            roster.append({"steamid": steamid, "name": d["name"].mode().sort().first(), "color": color, "rounds": rounds,
                           "low_sample": {s: rounds[s] < MIN_RELIABLE_ROUNDS for s in SIDES}})
            players[steamid] = grids(tev.filter(pl.col("steamid") == int(steamid)), rounds)
            if summaries is not None:
                summary[steamid] = {s: summaries(frames, team, int(steamid), s, rounds[s]) for s in SIDES if rounds[s]}
        roster.sort(key=lambda r: (r["color"], r["name"] or ""))
        slug = team_slug(team)
        teams[slug] = {
            "team": team, "slug": slug, "map": mm.name, "n_matches": td["demo_id"].n_unique(),
            "rounds": team_rounds, "roster": roster, "team_grid": grids(tev, team_rounds),
            "players": players, "summary": summary,
        }

    all_rounds = {s: tr.filter(pl.col("side") == s).height for s in SIDES}
    levels = 2 if "lower_level_max_z" in mm.radar else 1
    # Callout anchors for map/text linking. Keep floors separate and use only the
    # same cleaned observations as the heatmaps; fight-only places remain linkable.
    place_positions = (
        pl.concat([frames[name].select("place", "level", "radar_x", "radar_y")
                   for name in ("presence", "kills", "deaths")], how="vertical_relaxed")
        .filter(pl.col("place").is_not_null() & (pl.col("place") != "")
                & pl.col("radar_x").is_finite() & pl.col("radar_y").is_finite())
        .group_by("place", "level").agg(pl.col("radar_x").median().round(1),
                                       pl.col("radar_y").median().round(1))
        .sort("place", "level").to_dicts()
    )
    baseline = {
        "place_positions": place_positions,
        "map": mm.name, "grid": GRID, "cell_px": CELL_PX, "levels": levels,
        "layers": list(LAYERS), "phases": list(PHASES), "sides": list(SIDES), "n_colors": N_COLORS,
        "early_s": EARLY_S, "spawn_skip_s": SPAWN_SKIP_S, "hold_speed": HOLD_SPEED, "gun_rounds_only": True,
        "min_reliable_rounds": MIN_RELIABLE_ROUNDS,
        "value": "per round on that side: seconds (presence, holding) or counts per cell",
        "cell_index": "level * grid * grid + row * grid + col",
        "rounds": all_rounds,
        **grids(ev, all_rounds),
    }
    return {"baseline": baseline, "teams": teams, "frames": frames}


def to_array(flat: list, levels: int = 1) -> np.ndarray:
    """Unpack a sparse list into a (levels, GRID, GRID) array."""
    a = np.zeros(levels * GRID * GRID)
    for i in range(0, len(flat), 2):
        a[int(flat[i])] = flat[i + 1]
    return a.reshape(levels, GRID, GRID)


def merge_phases(entry: dict, side: str, phases: list[str] | tuple[str, ...] = PHASES) -> dict[str, list]:
    """Sum the chosen phases of one side into one sparse list per layer."""
    acc: dict[str, dict[int, float]] = {}
    for ph in phases:
        for layer, flat in entry["data"].get(side, {}).get(ph, {}).items():
            d = acc.setdefault(layer, {})
            for i in range(0, len(flat), 2):
                d[flat[i]] = d.get(flat[i], 0.0) + flat[i + 1]
    return {k: [x for c in sorted(v) for x in (c, v[c])] for k, v in acc.items()}


def combine(layers: dict[str, list], weights: dict[str, float], levels: int = 1) -> np.ndarray:
    """Each layer as a share of its own total, then weighted (units differ across layers)."""
    out = np.zeros((levels, GRID, GRID))
    for name, w in weights.items():
        if not w or name not in layers:
            continue
        a = to_array(layers[name], levels)
        s = a.sum()
        if s > 0 and math.isfinite(s):
            out += w * a / s
    return out
