"""Heatmap grids on a tiny synthetic round (no demo needed)."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from playbook.config import MapMeta
from playbook.heatmap import GRID, build_heatmaps, combine, to_array

MM = MapMeta(name="de_test", display_name="Test", radar={"pos_x": 0.0, "pos_y": 1024.0, "scale": 1.0})
MM2 = MapMeta(name="de_two", display_name="Two", radar={"pos_x": 0.0, "pos_y": 1024.0, "scale": 1.0, "lower_level_max_z": -100.0})
SID = 76561198000000001


def cell(x: float, y: float, level: int = 0) -> int:
    col, row = int(x // 16), int((1024 - y) // 16)
    return level * GRID * GRID + row * GRID + col


def tables(z: float = 0.0) -> dict[str, pl.DataFrame]:
    # One T player, one round, planted at 3 s: still at (100, 924) for t=0..2, then moves.
    pos = pl.DataFrame({
        "demo_id": ["d"] * 4, "round_num": [1] * 4, "t_s": [0, 1, 2, 3], "steamid": [SID] * 4,
        "team": ["Red"] * 4, "side": ["T"] * 4, "x": [100.0, 105.0, 110.0, 400.0], "y": [924.0] * 4,
        "z": [z] * 4, "alive": [True] * 4,
    }, schema_overrides={"round_num": pl.Int32, "t_s": pl.Int32, "steamid": pl.UInt64})
    shots = pl.DataFrame({
        "demo_id": ["d", "d"], "round_num": [1, 1], "t_s": [1.5, 30.0], "is_post_round": [False, True],
        "steamid": [SID, SID], "team": ["Red", "Red"], "side": ["T", "T"], "x": [100.0, 100.0], "y": [924.0, 924.0],
        "z": [z, z],
    }, schema_overrides={"round_num": pl.Int32, "steamid": pl.UInt64})
    util = pl.DataFrame({
        "demo_id": ["d"], "round_num": [1], "is_post_round": [False], "thrower_steamid": [SID],
        "thrower_team": ["Red"], "thrower_side": ["T"], "throw_t_s": [2.0], "throw_x": [110.0], "throw_y": [924.0],
        "throw_z": [z], "land_x": [600.0], "land_y": [500.0], "land_z": [z],
    }, schema_overrides={"round_num": pl.Int32, "thrower_steamid": pl.UInt64})
    kills = pl.DataFrame({
        "demo_id": ["d"], "round_num": [1], "t_s": [3.0], "is_post_round": [False], "is_teamkill": [False],
        "attacker_steamid": [SID], "attacker_team": ["Red"], "attacker_side": ["T"],
        "attacker_x": [400.0], "attacker_y": [924.0], "attacker_z": [z],
        "victim_steamid": [SID + 1], "victim_team": ["Blue"], "victim_side": ["CT"],
        "victim_x": [500.0], "victim_y": [924.0], "victim_z": [z],
    }, schema_overrides={"round_num": pl.Int32, "attacker_steamid": pl.UInt64, "victim_steamid": pl.UInt64})
    team_rounds = pl.DataFrame({
        "demo_id": ["d", "d"], "round_num": [1, 1], "team": ["Red", "Blue"], "side": ["T", "CT"], "plant_t_s": [3.0, 3.0],
    }, schema_overrides={"round_num": pl.Int32})
    player_rounds = pl.DataFrame({
        "demo_id": ["d", "d"], "round_num": [1, 1], "steamid": [SID, SID + 1], "name": ["red1", "blue1"],
        "team": ["Red", "Blue"], "side": ["T", "CT"],
    }, schema_overrides={"round_num": pl.Int32, "steamid": pl.UInt64})
    return {"positions": pos, "shots": shots, "utility": util, "kills": kills,
            "team_rounds": team_rounds, "player_rounds": player_rounds}


def as_dict(flat: list) -> dict[int, float]:
    return {int(flat[i]): flat[i + 1] for i in range(0, len(flat), 2)}


def test_layers_cells_and_phases():
    hm = build_heatmaps(tables(), MM)
    p = hm["players"][str(SID)]
    early = p["data"]["T"]["early"]
    # t=0,1,2 in one cell (x 100..110 -> col 6); t=3 is after the plant -> phase post
    assert as_dict(early["presence"]) == {cell(100, 924): 3.0}
    assert as_dict(early["holding"]) == {cell(100, 924): 2.0}  # t=0 has no previous sample
    assert as_dict(p["data"]["T"]["post"]["presence"]) == {cell(400, 924): 1.0}
    assert "holding" not in p["data"]["T"]["post"]  # moved 290 units in that second
    assert as_dict(early["shots"]) == {cell(100, 924): 1.0}  # the post-round shot is dropped
    assert as_dict(early["util_throw"]) == {cell(110, 924): 1.0}
    assert as_dict(early["util_land"]) == {cell(600, 500): 1.0}
    assert as_dict(p["data"]["T"]["post"]["kills"]) == {cell(400, 924): 1.0}
    victim = hm["players"][str(SID + 1)]
    assert as_dict(victim["data"]["CT"]["post"]["deaths"]) == {cell(500, 924): 1.0}
    assert p["per_round"]["T"]["all"]["presence"] == 4.0
    assert p["rounds"] == {"T": 1, "CT": 0}


def test_team_and_baseline_per_round():
    hm = build_heatmaps(tables(), MM)
    team = hm["teams"]["red"]
    assert team["per_round"]["T"]["all"]["shots"] == 1.0
    base = hm["baseline"]
    assert base["grid"] == GRID and base["levels"] == 1
    assert base["rounds"] == {"T": 1, "CT": 1}


def test_lower_level_goes_to_second_layer():
    hm = build_heatmaps(tables(z=-300.0), MM2)
    p = hm["players"][str(SID)]
    assert as_dict(p["data"]["T"]["early"]["presence"]) == {cell(100, 924, level=1): 3.0}
    assert hm["baseline"]["levels"] == 2


def test_combine_uses_shares_not_raw_units():
    layers = {"presence": [0, 90.0, 1, 10.0], "shots": [1, 2.0]}
    out = combine(layers, {"presence": 1, "shots": 1})
    # presence shares 0.9 / 0.1, shots share 1.0 in cell 1
    assert out[0, 0, 0] == pytest.approx(0.9)
    assert out[0, 0, 1] == pytest.approx(1.1)
    assert out.sum() == pytest.approx(2.0)
    assert np.count_nonzero(to_array([5, 1.0])) == 1
