"""2D round replays: positions per second, kills, grenade pops, the plant and T win probability.

One small JSON per round, `data/site/<map>/replay/<demo_id>/<round>.json`, for the showcase
teams' matches and the example rounds of every execute recipe. Coordinates are radar pixels
(1024 x 1024 image), rounded to integers; positions are sampled at 1 Hz like the parsed tables.

    {"demo_id", "round_num", "map", "teams": {"T", "CT"}, "winner": "T"|"CT", "duration": s,
     "players": [{"name", "side", "team"}],          # index = column in frames
     "frames": [[[x, y] | null, ...], ...],          # one row per second; null = dead / not seen
     "yaw": [[degrees | null, ...], ...],          # parallel to frames; SVG/radar clockwise from +x
     "events": [{"t", "kind": "kill"|"util"|"plant", ...}],
     "wp_t": [p, ...]}                               # T win probability per second (may be empty)
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
import hashlib

import numpy as np
import polars as pl

from playbook.config import MapMeta
from playbook.utility import PlaceIndex

KEYS = ["demo_id", "round_num"]
UTIL_KINDS = {"smoke": "smoke", "flashbang": "flash", "flash": "flash", "molotov": "molotov",
              "incendiary": "molotov", "he": "he", "hegrenade": "he"}
CONTEXT_CACHE_SIZE = 16  # maps whose control grid / callout index stay memoised


class RoundTables:
    """One map's tables split by (demo_id, round_num) once.

    build_round then looks a round up instead of filtering every table of the map
    again (O(rounds x table) -> O(table)). Rows keep their original order, so every
    round slice equals ``sub[name].filter(demo & round)``. With ``rounds`` given, only
    those demos are partitioned; each table is split on first use.
    """

    def __init__(self, sub: dict[str, pl.DataFrame], rounds: Iterable[tuple[str, int]] | None = None):
        self.sub = sub
        self.demos = sorted({demo for demo, _ in rounds}) if rounds is not None else None
        self._parts: dict[str, dict] = {}

    def get(self, name: str, demo: str, rnd: int) -> pl.DataFrame:
        if name not in self._parts:
            df = self.sub[name]
            if self.demos is not None:
                df = df.filter(pl.col("demo_id").is_in(self.demos))
            self._parts[name] = df.partition_by(KEYS, as_dict=True)
        part = self._parts[name].get((demo, rnd))
        return part if part is not None else self.sub[name].clear()


def radar_yaw(yaw: float | None) -> int | None:
    """World +y is radar -y: negate yaw for SVG rotation, clockwise from right."""
    return int(round(-yaw)) % 360 if yaw is not None and np.isfinite(yaw) else None


def _px(mm: MapMeta, x: float | None, y: float | None) -> list[int] | None:
    if x is None or y is None:
        return None
    rx, ry = mm.to_radar(float(x), float(y))
    return [int(round(rx)), int(round(ry))]


def control_grid(positions: pl.DataFrame) -> np.ndarray:
    """Centres of occupied cells in a map-wide 15×15 world-XY grid."""
    xy = positions.filter((pl.col("t_s") >= 0) & pl.col("x").is_finite() & pl.col("y").is_finite()).select("x", "y").to_numpy()
    if not len(xy):
        return np.empty((0, 2))
    low, high = xy.min(axis=0), xy.max(axis=0)
    size = np.maximum(high - low, 1.0) / 15
    ij = np.clip(((xy - low) / size).astype(int), 0, 14)
    # Same rows, same lexicographic order as np.unique(ij, axis=0), via one 1-D unique.
    flat = np.unique(ij[:, 0] * 15 + ij[:, 1])
    cells = np.stack([flat // 15, flat % 15], axis=1).astype(ij.dtype)
    return low + (cells + .5) * size


def _fingerprint(positions: pl.DataFrame) -> tuple:
    """Content key of the columns control_grid / callout_index read."""
    cols = [c for c in ("t_s", "x", "y", "z", "place") if c in positions.columns]
    digest = hashlib.blake2b(positions.select(cols).hash_rows().to_numpy().tobytes(), digest_size=16).hexdigest()
    return positions.height, tuple((c, str(positions.schema[c])) for c in cols), digest


_CONTEXT: OrderedDict[tuple, tuple] = OrderedDict()


def map_context(positions: pl.DataFrame) -> tuple[np.ndarray, PlaceIndex | None]:
    """(control_grid, callout_index) of one map's positions, memoised by content.

    The regular replay export and the AI-lab replay top-up both need them for the same
    map; the second call is a cache hit instead of a rebuild.
    """
    key = _fingerprint(positions)
    if key in _CONTEXT:
        _CONTEXT.move_to_end(key)
        return _CONTEXT[key]
    grid = control_grid(positions)
    grid.flags.writeable = False  # shared by every caller of this map
    value = grid, callout_index(positions)
    _CONTEXT[key] = value
    while len(_CONTEXT) > CONTEXT_CACHE_SIZE:
        _CONTEXT.popitem(last=False)
    return value


def t_control(t: np.ndarray, ct: np.ndarray, grid: np.ndarray) -> float | None:
    if not len(grid) or (not len(t) and not len(ct)):
        return None
    if not len(t):
        return 0.0
    if not len(ct):
        return 1.0
    td = ((grid[:, None, :] - t[None, :, :]) ** 2).sum(axis=2).min(axis=1)
    cd = ((grid[:, None, :] - ct[None, :, :]) ** 2).sum(axis=2).min(axis=1)
    return round(float((td < cd).mean()), 3)


def kill_wpa(at: float, side: str | None, wp: list, duration: float, winner: str) -> float | None:
    """Same floor(t) → floor(t)+2 window as winprob.action_values; terminal outcome fallback."""
    before, after = int(np.floor(at)), int(np.floor(at)) + 2
    if side not in ("T", "CT") or before < 0 or before >= len(wp) or wp[before] is None:
        return None
    post = wp[after] if after < len(wp) else None
    if post is None and after >= duration:
        post = float(winner == "T")
    if post is None:
        return None
    return round((post - wp[before]) * (1 if side == "T" else -1), 4)


def _first_per_cell(valid: pl.DataFrame, z_weight: float = 2.0, cell: float = 16.0) -> pl.DataFrame:
    """The rows PlaceIndex keeps: the first named row of each thinning cell (16 units,
    z weighted by 2, as in PlaceIndex). Pre-thinning yields an identical index without
    sorting every observed position in np.unique(axis=0)."""
    named = valid.filter(pl.col("place").fill_null("") != "")
    x, y, z = (named[c].to_numpy() for c in ("x", "y", "z"))
    key = np.round(np.stack([x, y, z * z_weight], axis=1) / cell).astype(np.int64)
    first = (pl.DataFrame(key, schema=["kx", "ky", "kz"], orient="row").with_row_index("i")
             .unique(subset=["kx", "ky", "kz"], keep="first", maintain_order=True)["i"])
    return named[first]


def callout_index(positions: pl.DataFrame) -> PlaceIndex | None:
    """Observed callouts, preserving floor height; shared by all replay rounds."""
    if not {"x", "y", "z", "place"} <= set(positions.columns):
        return None
    valid = positions.filter(pl.all_horizontal(pl.col(c).is_finite() for c in ("x", "y", "z")))
    return PlaceIndex.from_frame(_first_per_cell(valid))


def event_place(row: dict, prefix: str, index: PlaceIndex | None) -> str | None:
    place = row.get(f"{prefix}place")
    if place:
        return place
    xyz = [row.get(f"{prefix}{axis}") for axis in ("x", "y", "z")]
    if index is None or any(v is None or not np.isfinite(v) for v in xyz):
        return None
    return index.query(*[[v] for v in xyz])[0]


def _controls(pos: pl.DataFrame, dur: int, grid: np.ndarray) -> list[float | None]:
    """t_control for every second 0..dur with a living player, for the whole round at once.

    Same numbers as calling t_control per second: squared distances are computed once
    per (player-second, cell), the nearest T / CT per cell is a segment minimum, and
    (td < cd).mean() is count / cells (numpy's bool mean divides the same float count).
    """
    controls: list[float | None] = [None] * (dur + 1)
    live = pos.filter(pl.col("alive") & pl.col("x").is_finite() & pl.col("y").is_finite())
    if live.is_empty() or not len(grid):
        return controls
    side = live["side"].to_numpy()
    code = np.where(side == "T", 0, np.where(side == "CT", 1, 2))
    order = np.lexsort((code, live["t_s"].to_numpy()))
    seconds, code = live["t_s"].to_numpy()[order], code[order]
    xy = live.select("x", "y").to_numpy()[order]
    starts = np.flatnonzero(np.r_[True, (seconds[1:] != seconds[:-1]) | (code[1:] != code[:-1])])
    # dx² + dy², the same single addition t_control's .sum(axis=2) performs
    d2 = (xy[:, 0, None] - grid[None, :, 0]) ** 2 + (xy[:, 1, None] - grid[None, :, 1]) ** 2
    nearest = np.minimum.reduceat(d2, starts, axis=0)
    by_side: tuple[dict, dict] = ({}, {})
    for row, (second, c) in enumerate(zip(seconds[starts].tolist(), code[starts].tolist())):
        if c < 2:
            by_side[c][second] = nearest[row]
    for second in dict.fromkeys(seconds[starts].tolist()):
        if 0 <= second <= dur:
            td, cd = by_side[0].get(second), by_side[1].get(second)
            if td is None and cd is None:
                continue
            controls[second] = (0.0 if td is None else 1.0 if cd is None
                                else round(float(np.count_nonzero(td < cd) / len(grid)), 3))
    return controls


def build_round(sub: dict[str, pl.DataFrame], mm: MapMeta, demo: str, rnd: int,
                wp: list[float] | None = None, grid: np.ndarray | None = None,
                place_index: PlaceIndex | None = None, tables: RoundTables | None = None) -> dict | None:
    """One replay round. Pass ``tables`` (RoundTables of the same ``sub``) when building
    many rounds of a map: each table is then partitioned once instead of filtered per round."""
    if tables is None:
        key = (pl.col("demo_id") == demo) & (pl.col("round_num") == rnd)

        def table(name: str) -> pl.DataFrame:
            return sub[name].filter(key)
    else:
        def table(name: str) -> pl.DataFrame:
            return tables.get(name, demo, rnd)
    r = table("rounds")
    pos = table("positions").filter(pl.col("t_s") >= 0).sort("t_s")
    if r.is_empty() or pos.is_empty():
        return None
    r0 = r.row(0, named=True)
    dur = int(np.ceil(float(r0["dur_s"])))
    roster = (pos.group_by("steamid").agg(pl.col("name").mode().first(), pl.col("side").first(), pl.col("team").first())
              .sort("side", "name", descending=[True, False]))
    sids = roster["steamid"].to_list()
    index = {s: i for i, s in enumerate(sids)}
    frames: list[list] = [[None] * len(sids) for _ in range(dur + 1)]
    yaw: list[list] = [[None] * len(sids) for _ in range(dur + 1)]
    if "yaw" not in pos.columns:
        pos = pos.with_columns(pl.lit(None, dtype=pl.Float64).alias("yaw"))
    for sid, t, x, y, alive, angle in pos.select("steamid", "t_s", "x", "y", "alive", "yaw").iter_rows():
        if 0 <= t <= dur and alive:
            frames[t][index[sid]] = _px(mm, x, y)
            if frames[t][index[sid]] is not None:
                yaw[t][index[sid]] = radar_yaw(angle)
    if grid is None:
        grid = control_grid(sub["positions"])
    controls = _controls(pos, dur, grid)
    sides = dict(roster.select("steamid", "side").iter_rows())
    if place_index is None:
        place_index = callout_index(sub["positions"])
    events: list[dict] = []
    k = table("kills").filter(~pl.col("is_post_round"))
    for row in k.iter_rows(named=True):
        events.append({"t": round(float(row["t_s"]), 1), "kind": "kill",
                       "by": index.get(row["attacker_steamid"]), "victim": index.get(row["victim_steamid"]),
                       "at": _px(mm, row["victim_x"], row["victim_y"]), "weapon": row["weapon"],
                       "headshot": bool(row.get("headshot")),
                       "side": row.get("attacker_side") or sides.get(row["attacker_steamid"]),
                       "place": event_place(row, "victim_", place_index),
                       "wpa": kill_wpa(float(row["t_s"]), row.get("attacker_side") or sides.get(row["attacker_steamid"]), wp or [],
                                       float(r0["dur_s"]), r0["winner_side"])})
    u = table("utility").filter(~pl.col("is_post_round") & pl.col("pop_t_s").is_not_null()
                                & pl.col("land_x").is_not_null())
    for row in u.iter_rows(named=True):
        kind = UTIL_KINDS.get(str(row["type"]).lower())
        if kind:
            events.append({"t": round(float(row["pop_t_s"]), 1), "kind": "util", "nade": kind,
                           "by": index.get(row["thrower_steamid"]), "at": _px(mm, row["land_x"], row["land_y"]),
                           "from": _px(mm, row.get("throw_x"), row.get("throw_y")),
                           "side": row.get("thrower_side") or sides.get(row["thrower_steamid"]),
                           "place": event_place(row, "land_", place_index),
                           "is_flash": kind == "flash"})
    p = table("plants")
    for row in p.head(1).iter_rows(named=True):
        events.append({"t": round(float(row["t_s"]), 1), "kind": "plant", "site": row["site"],
                       "at": _px(mm, row["x"], row["y"]),
                       "by": index.get(row.get("steamid")), "side": "T",
                       "place": event_place(row, "", place_index)})
    events.sort(key=lambda e: e["t"])
    match = sub.get("matches", pl.DataFrame())
    rows = match.filter(pl.col("demo_id") == demo).to_dicts() if "demo_id" in match.columns else []
    metadata = {field: rows[0].get(field) if rows else None for field in ("date", "date_precision", "event")}
    return {**metadata,
        "demo_id": demo, "round_num": int(rnd), "map": mm.name,
        "teams": {"T": r0["t_team"], "CT": r0["ct_team"]}, "winner": r0["winner_side"],
        "reason": r0.get("reason"), "duration": dur,
        "players": [{"name": n, "side": s, "team": tm} for n, s, tm in roster.select("name", "side", "team").iter_rows()],
        "frames": frames, "yaw": yaw, "events": events, "wp_t": [round(float(v), 3) if v is not None else None for v in (wp or [])],
        "t_control": controls,
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
            values = [None] * (int(g["t_s"].max()) + 1)
            for second, value in g.select("t_s", "wp").iter_rows():
                if second >= 0:
                    values[second] = float(value)
            out[(demo, int(rnd))] = values
    return out
