"""Team heatmaps and player summaries on a tiny synthetic round (no demo needed)."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from playbook.config import MapMeta
from playbook.heatmap import GRID, build_heatmaps, combine, roster_order, to_array
from playbook.zones import make_summarizer, team_setup

MM = MapMeta(name="de_test", display_name="Test", radar={"pos_x": 0.0, "pos_y": 1024.0, "scale": 1.0},
             callout_region={"Spot": "A_SITE", "Far": "MID"}, region_lane={"A_SITE": "A", "MID": "MID"})
MM2 = MapMeta(name="de_two", display_name="Two",
              radar={"pos_x": 0.0, "pos_y": 1024.0, "scale": 1.0, "lower_level_max_z": -100.0})
SID = 76561198000000001


def cell(x: float, y: float, level: int = 0) -> int:
    col, row = int(x // 16), int((1024 - y) // 16)
    return level * GRID * GRID + row * GRID + col


def tables(z: float = 0.0, buy: str = "full") -> dict[str, pl.DataFrame]:
    # One T player, one round, plant at 8 s. Still at (100, 924) for t=4..7, then moves.
    # t=4 is dropped (first 5 s), t=5 has no "holding" credit unless t=4 was still: it was.
    ts = [4, 5, 6, 7, 8]
    xs = [100.0, 101.0, 102.0, 103.0, 400.0]
    pos = pl.DataFrame({
        "demo_id": ["d"] * 5, "round_num": [1] * 5, "t_s": ts, "steamid": [SID] * 5, "name": ["red1"] * 5,
        "team": ["Red"] * 5, "side": ["T"] * 5, "x": xs, "y": [924.0] * 5, "z": [z] * 5,
        "place": ["Spot"] * 4 + ["Far"], "region": ["A_SITE"] * 4 + ["MID"], "lane": ["A"] * 4 + ["MID"],
        "alive": [True] * 5,
    }, schema_overrides={"round_num": pl.Int32, "t_s": pl.Int32, "steamid": pl.UInt64})
    shots = pl.DataFrame({
        "demo_id": ["d", "d"], "round_num": [1, 1], "t_s": [6.5, 30.0], "is_post_round": [False, True],
        "steamid": [SID, SID], "team": ["Red", "Red"], "side": ["T", "T"], "x": [100.0, 100.0], "y": [924.0, 924.0],
        "z": [z, z],
    }, schema_overrides={"round_num": pl.Int32, "steamid": pl.UInt64})
    util = pl.DataFrame({
        "demo_id": ["d"], "round_num": [1], "nade_id": [7], "type": ["smoke"], "is_post_round": [False],
        "thrower_steamid": [SID], "thrower_team": ["Red"], "thrower_side": ["T"], "throw_t_s": [6.0],
        "land_x": [600.0], "land_y": [500.0], "land_z": [z], "land_place": ["Far"],
    }, schema_overrides={"round_num": pl.Int32, "thrower_steamid": pl.UInt64, "nade_id": pl.UInt32})
    kills = pl.DataFrame({
        "demo_id": ["d"], "round_num": [1], "t_s": [8.0], "is_post_round": [False], "is_teamkill": [False],
        "is_opening": [True], "attacker_steamid": [SID], "attacker_team": ["Red"], "attacker_side": ["T"],
        "attacker_place": ["Far"], "attacker_x": [400.0], "attacker_y": [924.0], "attacker_z": [z],
        "victim_steamid": [SID + 1], "victim_team": ["Blue"], "victim_side": ["CT"], "victim_place": ["Far"],
        "victim_x": [500.0], "victim_y": [924.0], "victim_z": [z],
    }, schema_overrides={"round_num": pl.Int32, "attacker_steamid": pl.UInt64, "victim_steamid": pl.UInt64})
    team_rounds = pl.DataFrame({
        "demo_id": ["d", "d"], "round_num": [1, 1], "team": ["Red", "Blue"], "side": ["T", "CT"],
        "plant_t_s": [8.0, 8.0], "buy_type": [buy, "full"],
    }, schema_overrides={"round_num": pl.Int32})
    player_rounds = pl.DataFrame({
        "demo_id": ["d", "d"], "round_num": [1, 1], "steamid": [SID, SID + 1], "name": ["red1", "blue1"],
        "team": ["Red", "Blue"], "side": ["T", "CT"], "buy_type": [buy, "full"],
    }, schema_overrides={"round_num": pl.Int32, "steamid": pl.UInt64})
    return {"positions": pos, "shots": shots, "utility": util, "kills": kills,
            "team_rounds": team_rounds, "player_rounds": player_rounds}


def as_dict(flat: list) -> dict[int, float]:
    return {int(flat[i]): flat[i + 1] for i in range(0, len(flat), 2)}


def test_player_layers_cells_and_phases():
    hm = build_heatmaps(tables(), MM)
    red = hm["teams"]["red"]
    p = red["players"][str(SID)]["data"]["T"]
    # t=4 dropped (spawn walk-out); t=5..7 in one cell; t=8 is the plant second -> post
    assert as_dict(p["early"]["presence"]) == {cell(100, 924): 3.0}
    assert as_dict(p["early"]["holding"]) == {cell(100, 924): 3.0}  # t=5 is still vs t=4
    assert as_dict(p["post"]["presence"]) == {cell(400, 924): 1.0}
    assert "holding" not in p["post"]  # moved 297 units in that second
    assert as_dict(p["early"]["shots"]) == {cell(100, 924): 1.0}  # post-round shot dropped
    assert as_dict(p["early"]["smoke"]) == {cell(600, 500): 1.0}  # landing point, by type
    assert as_dict(p["post"]["kills"]) == {cell(400, 924): 1.0}
    blue = hm["teams"]["blue"]
    assert as_dict(blue["players"][str(SID + 1)]["data"]["CT"]["post"]["deaths"]) == {cell(500, 924): 1.0}
    assert red["players"][str(SID)]["per_round"]["T"]["all"]["presence"] == 4.0
    assert red["roster"][0]["color"] == 0 and red["roster"][0]["rounds"] == {"T": 1, "CT": 0}
    assert red["roster"][0]["low_sample"]["T"] is True


def test_eco_rounds_are_excluded():
    hm = build_heatmaps(tables(buy="eco"), MM)
    assert "red" not in hm["teams"]  # the team had no gun round
    assert hm["baseline"]["rounds"] == {"T": 0, "CT": 1}


def test_lower_level_goes_to_second_layer():
    hm = build_heatmaps(tables(z=-300.0), MM2)
    p = hm["teams"]["red"]["players"][str(SID)]["data"]["T"]
    assert as_dict(p["early"]["presence"]) == {cell(100, 924, level=1): 3.0}
    assert hm["baseline"]["levels"] == 2


def test_summary_zones_holds_fights_utility():
    spots = pl.DataFrame({"spot_id": ["s1"], "type": ["smoke"], "place": ["Far"], "label": ["Far"],
                          "radar_x": [600.0], "radar_y": [524.0]})
    assign = pl.DataFrame({"demo_id": ["d"], "nade_id": [7], "spot_id": ["s1"]}, schema_overrides={"nade_id": pl.UInt32})
    lineups = pl.DataFrame({"demo_id": ["d"], "nade_id": [7], "lineup_id": ["L1"]}, schema_overrides={"nade_id": pl.UInt32})
    hm = build_heatmaps(tables(), MM, summaries=make_summarizer(MM, spots, assign, lineups))
    red = hm["teams"]["red"]
    s = red["summary"][str(SID)]["T"]
    assert s["zones"]["early"][0] == {"place": "Spot", "region": "A_SITE", "lane": "A", "share": 1.0}
    assert s["main_lane"]["post"] == {"lane": "MID", "share": 1.0}
    assert s["fights"]["kills_pr"] == 1.0 and s["fights"]["opening_kills"] == 1
    assert s["fights"]["places"] == [{"place": "Far", "kills": 1, "deaths": 0}]
    assert s["utility"]["per_round"]["smoke"] == 1.0
    assert s["utility"]["spots"][0]["spot_id"] == "s1" and s["utility"]["spots"][0]["lineups"] == [{"lineup_id": "L1", "n": 1}]
    assert s["holds"] == []  # 3 held seconds: below the minimum cluster size
    red["setup"] = team_setup(red)
    assert red["setup"]["T"]["early"] == {"A": ["red1"]}


def test_roster_order_is_stable_by_rounds_then_name():
    pr = pl.DataFrame({"team": ["X"] * 5, "steamid": [3, 1, 1, 2, 2], "name": ["c", "a", "a", "b", "b"]},
                      schema_overrides={"steamid": pl.UInt64})
    assert roster_order(pr) == {"X": ["1", "2", "3"]}


def test_combine_uses_shares_not_raw_units():
    layers = {"presence": [0, 90.0, 1, 10.0], "shots": [1, 2.0]}
    out = combine(layers, {"presence": 1, "shots": 1})
    assert out[0, 0, 0] == pytest.approx(0.9)
    assert out[0, 0, 1] == pytest.approx(1.1)
    assert out.sum() == pytest.approx(2.0)
    assert np.count_nonzero(to_array([5, 1.0])) == 1
