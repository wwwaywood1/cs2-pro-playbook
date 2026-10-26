"""The partitioned / vectorised export paths equal the per-round filters they replace.

Each reference below is the pre-optimisation loop (radar6 clutch scan and molotov check,
replay per-second control, per-player zone filters), run on randomised tables.
"""
from collections import Counter
import json
import math

import numpy as np
import polars as pl
import pytest

from playbook.config import MapMeta
from playbook.heatmap import clean_frames
from playbook.radar6 import KEYS, _first_clutches, _molotov_displacements
from playbook import replay
from playbook.replay import RoundTables, build_round, callout_index, control_grid, map_context, t_control
from playbook.utility import PlaceIndex
from playbook.zones import make_summarizer
from test_heatmap import MM as HEATMAP_MM, SID, tables

MM = MapMeta(name="de_test", display_name="Test", radar={"pos_x": -500.0, "pos_y": 1500.0, "scale": 2.0})


def random_positions(seed: int = 3, rounds: int = 4, seconds: int = 30) -> pl.DataFrame:
    """Ten players random-walking; staggered deaths create 1vN states; some NaN z."""
    rng = np.random.default_rng(seed)
    rows = []
    for rnd in range(1, rounds + 1):
        xy = rng.normal(500, 200, (10, 2))
        death = rng.integers(2, seconds + 5, 10)
        for t in range(-2, seconds):
            xy = xy + rng.normal(0, 60, (10, 2))
            for sid in range(10):
                side = "T" if sid < 5 else "CT"
                rows.append(dict(demo_id="d" if rnd % 2 else "e", round_num=rnd, t_s=t, steamid=sid, name=f"p{sid}",
                                 side=side, team=side, x=float(xy[sid, 0]), y=float(xy[sid, 1]),
                                 z=float(rng.choice([0.0, 0.0, 100.0, 300.0, np.nan])), alive=bool(t < death[sid]),
                                 place=str(rng.choice(["A", "B", "Mid", ""]))))
    return pl.DataFrame(rows)


# --------------------------------------------------------------------------- radar6


def clutches_reference(pos: pl.DataFrame) -> dict:
    out = {}
    for key, frames in pos.group_by(KEYS):
        by_second = {t: g for (t,), g in frames.group_by("t_s")}
        seen, found = set(), []
        for t in sorted(by_second):
            for side in ("T", "CT"):
                own = by_second[t].filter(pl.col("side") == side)
                enemies = by_second[t].filter(pl.col("side") != side)
                if side in seen or own.height != 1 or enemies.is_empty():
                    continue
                seen.add(side)
                found.append((side, t, own["steamid"][0]))
        if found:
            out[key] = sorted(found)
    return out


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_first_clutches_equal_second_by_second_scan(seed):
    live = random_positions(seed).filter(pl.col("alive") & (pl.col("t_s") >= 0))
    # Duplicate sample (own count 2, not a clutch) and a null-side row (not an opponent).
    extra = live.filter((pl.col("round_num") == 1) & (pl.col("steamid") == 0))
    nobody = live.filter((pl.col("round_num") == 2) & (pl.col("steamid") == 9)).with_columns(
        side=pl.lit(None, dtype=pl.String))
    live = pl.concat([live, extra, nobody])
    got = {k: sorted(v) for k, v in _first_clutches(live).items()}
    assert got == clutches_reference(live)
    assert got  # the fixture really contains 1vN states


def molotov_reference(pos: pl.DataFrame, fires: list[tuple]) -> list[tuple]:
    rounds = {k: g for k, g in pos.group_by(KEYS)}
    out = []
    for demo, rnd, second, sid, side, pop, land_x, land_y, land_z in fires:
        frames = rounds.get((demo, rnd))
        if frames is None:
            continue
        by_second = {t: g for (t,), g in frames.group_by("t_s")}
        tracks = {s: g for (s,), g in frames.group_by("steamid")}
        initial = by_second.get(second)
        if initial is None:
            continue
        for enemy in initial.filter(pl.col("side") != side).iter_rows(named=True):
            if abs(enemy["z"] - land_z) > 120 or math.hypot(enemy["x"] - land_x, enemy["y"] - land_y) > 120:
                continue
            later = tracks[enemy["steamid"]].filter((pl.col("t_s") > pop) & (pl.col("t_s") <= pop + 3.5))
            if any(math.hypot(x - enemy["x"], y - enemy["y"]) > 150 for x, y in later.select("x", "y").iter_rows()):
                out.append((sid, side))
    return out


@pytest.mark.parametrize("seed", [4, 5])
def test_molotov_displacements_equal_per_round_filters(seed):
    rng = np.random.default_rng(seed)
    live = random_positions(seed).filter(pl.col("alive") & (pl.col("t_s") >= 0))
    fires = []
    for demo, rnd, t, sid, side, x, y in live.sample(120, seed=seed).select(
            *KEYS, "t_s", "steamid", "side", "x", "y").iter_rows():
        thrower_side = "CT" if side == "T" else "T"  # aimed at this player
        pop = t + float(rng.choice([-.5, -.25, 0., .25, .49]))
        fires.append((demo, rnd, math.floor(pop + .5), 100 + sid, thrower_side, pop,
                      x + float(rng.normal(0, 70)), y + float(rng.normal(0, 70)), float(rng.choice([0., 110., 130.]))))
    fires.append(("d", 99, 3, 7, "T", 3., 0., 0., 0.))  # round without frames
    got = _molotov_displacements(live, fires)
    assert Counter(got) == Counter(molotov_reference(live, fires))
    assert got  # some fires really displace someone
    assert _molotov_displacements(live, []) == []


# --------------------------------------------------------------------------- replay


def controls_reference(pos: pl.DataFrame, dur: int, grid: np.ndarray) -> list:
    controls = [None] * (dur + 1)
    for (second,), g in pos.filter(pl.col("alive") & pl.col("x").is_finite() & pl.col("y").is_finite()).group_by("t_s"):
        if 0 <= second <= dur:
            controls[second] = t_control(g.filter(pl.col("side") == "T").select("x", "y").to_numpy(),
                                         g.filter(pl.col("side") == "CT").select("x", "y").to_numpy(), grid)
    return controls


def test_control_grid_and_per_second_control_equal_reference():
    pos = random_positions(6)
    xy = pos.filter((pl.col("t_s") >= 0) & pl.col("x").is_finite() & pl.col("y").is_finite()).select("x", "y").to_numpy()
    low, high = xy.min(axis=0), xy.max(axis=0)
    size = np.maximum(high - low, 1.0) / 15
    expected = low + (np.unique(np.clip(((xy - low) / size).astype(int), 0, 14), axis=0) + .5) * size
    grid = control_grid(pos)
    assert grid.dtype == expected.dtype and np.array_equal(grid, expected)
    for (demo, rnd), g in pos.filter(pl.col("t_s") >= 0).sort("t_s").group_by(KEYS):
        for dur in (0, 12, 40):
            assert replay._controls(g, dur, grid) == controls_reference(g, dur, grid)


def test_callout_index_thinning_matches_full_place_index():
    rng = np.random.default_rng(8)
    n = 4000
    # Coarse coordinates collide in thinning cells; multiples of 8 sit on .5 rounding ties.
    pos = pl.DataFrame({"x": rng.integers(-40, 40, n) * 8.0, "y": rng.integers(-40, 40, n) * 8.0,
                        "z": rng.choice([0.0, 4.0, 12.0, -8.0, np.nan, np.inf], n),
                        "place": rng.choice(["A", "B", "Mid", "", None], n).tolist()})
    valid = pos.filter(pl.all_horizontal(pl.col(c).is_finite() for c in ("x", "y", "z")))
    full, thin = PlaceIndex.from_frame(valid), callout_index(pos)
    assert np.array_equal(full.pts, thin.pts) and np.array_equal(full.pts2d, thin.pts2d)
    assert full.labels.tolist() == thin.labels.tolist()
    assert callout_index(pos.drop("place")) is None


def test_round_tables_slices_equal_filters():
    pos = random_positions(9)
    sub = {"positions": pos, "rounds": pos.select(KEYS).unique(maintain_order=True)}
    for rounds in (None, [("d", 1), ("d", 3)]):
        tables = RoundTables(sub, rounds)
        for demo, rnd in [("d", 1), ("e", 2), ("d", 3), ("e", 4), ("x", 1)]:
            want = pos.filter((pl.col("demo_id") == demo) & (pl.col("round_num") == rnd))
            if rounds is not None and demo not in {d for d, _ in rounds}:
                want = want.clear()
            got = tables.get("positions", demo, rnd)
            assert got.schema == want.schema and got.equals(want)


def replay_sub() -> dict[str, pl.DataFrame]:
    pos = random_positions(10)
    rounds = pos.select(KEYS).unique(maintain_order=True).with_columns(
        dur_s=pl.lit(21.5), t_team=pl.lit("TT"), ct_team=pl.lit("CC"), winner_side=pl.lit("T"), reason=pl.lit("bomb"))
    kills = pos.filter(pl.col("t_s").is_in([5, 9])).select(
        *KEYS, t_s=pl.col("t_s").cast(pl.Float64) + .3, is_post_round=pl.lit(False), attacker_steamid=pl.col("steamid"),
        victim_steamid=(pl.col("steamid") + 5) % 10, victim_x="x", victim_y="y", victim_z="z",
        victim_place="place", weapon=pl.lit("ak47"), headshot=pl.lit(True))
    utility = pos.filter(pl.col("t_s") == 3).select(
        *KEYS, pop_t_s=pl.lit(3.4), is_post_round=pl.col("steamid") == 2, type=pl.lit("smoke"),
        thrower_steamid="steamid", land_x="x", land_y="y", land_z="z", land_place="place", throw_x="x", throw_y="y")
    plants = rounds.select(*KEYS, t_s=pl.lit(15.0), site=pl.lit("A"), steamid=pl.lit(1), x=pl.lit(10.0),
                           y=pl.lit(20.0), z=pl.lit(0.0), place=pl.lit("A"))
    matches = pl.DataFrame({"demo_id": ["d", "e"], "date": ["2026-01-01", None], "event": ["X", "Y"]})
    return dict(positions=pos, rounds=rounds, kills=kills, utility=utility, plants=plants, matches=matches)


def test_build_round_with_round_tables_matches_filtered_build():
    sub = replay_sub()
    grid, index = control_grid(sub["positions"]), callout_index(sub["positions"])
    keys = [("d", 1), ("e", 2), ("d", 3), ("e", 4), ("d", 2)]
    tables = RoundTables(sub, keys)
    dump = lambda o: json.dumps(o, separators=(",", ":"))  # noqa: E731
    for demo, rnd in keys:
        plain = build_round(sub, MM, demo, rnd, [.5] * 25, grid, index)
        fast = build_round(sub, MM, demo, rnd, [.5] * 25, grid, index, tables)
        assert dump(plain) == dump(fast)
        assert (plain is None) == ((demo, rnd) == ("d", 2))


def test_map_context_is_memoised_by_content():
    pos = random_positions(11)
    grid, index = map_context(pos)
    assert np.array_equal(grid, control_grid(pos)) and not grid.flags.writeable
    again = map_context(pos.clone())  # equal content, different frame object
    assert again[0] is grid and again[1] is index
    moved = map_context(pos.with_columns(x=pl.col("x") + 1000))
    assert moved[0] is not grid and not np.array_equal(moved[0], grid)


# --------------------------------------------------------------------------- zones


def two_team_tables() -> dict[str, pl.DataFrame]:
    a, b = tables(), tables()
    for key, frame in b.items():
        frame = frame.with_columns(demo_id=pl.lit("e"))
        for col in ("team", "attacker_team", "thrower_team"):
            if col in frame.columns:
                frame = frame.with_columns(pl.col(col).replace({"Red": "Green"}))
        b[key] = frame
    return {key: pl.concat([a[key], b[key]]) for key in a}


@pytest.mark.parametrize("with_spots", [False, True])
def test_zone_summaries_equal_per_player_filters_and_follow_new_frames(with_spots):
    frames = clean_frames(two_team_tables(), HEATMAP_MM)
    other = clean_frames(tables(), HEATMAP_MM)
    args = ()
    if with_spots:  # utility joined to spots / lineups once per frame instead of per player
        spots = pl.DataFrame({"spot_id": ["s1"], "type": ["smoke"], "place": ["Far"], "label": ["Far"],
                              "radar_x": [600.0], "radar_y": [524.0]})
        assign = pl.DataFrame({"demo_id": ["d", "e"], "nade_id": [7, 7], "spot_id": ["s1", "s1"]},
                              schema_overrides={"nade_id": pl.UInt32})
        lineups = pl.DataFrame({"demo_id": ["d"], "nade_id": [7], "lineup_id": ["L1"]},
                               schema_overrides={"nade_id": pl.UInt32})
        args = (spots, assign, lineups)
    summarize = make_summarizer(HEATMAP_MM, *args)
    for fr in (frames, other, frames):  # the slice cache follows the frames it is given
        for team, sid, side in [("Red", SID, "T"), ("Green", SID, "T"), ("Blue", SID + 1, "CT"), ("Red", SID, "CT")]:
            mine = {name: f.filter((pl.col("team") == team) & (pl.col("steamid") == sid) & (pl.col("side") == side))
                    for name, f in fr.items()}
            assert summarize(fr, team, sid, side, 2) == make_summarizer(HEATMAP_MM, *args)(mine, team, sid, side, 2)
    if with_spots:  # the joined path really ran: Red's smoke has a lineup, Green's (demo e) none
        red, green = (summarize(frames, team, SID, "T", 2)["utility"]["spots"] for team in ("Red", "Green"))
        assert red[0]["lineups"] == [{"lineup_id": "L1", "n": 1}] and green[0]["lineups"] == []
