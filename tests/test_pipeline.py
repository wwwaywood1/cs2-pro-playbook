"""End-to-end checks on a real professional demo.

Uses B8 vs Vitality on Mirage (HLTV match 2394170), hosted as an awpy test fixture:
https://github.com/pnxenopoulos/awpy-fixtures/releases/download/hltv-de_mirage-2394170/hltv-de_mirage-2394170.dem
(sha256 321cfe8bd30501f9040a9ae0cfaca900b6db1cc6cc6ab026f56b86a5b3e20ddc)

Set PLAYBOOK_TEST_DEMO to its path, or put it in data/raw/. Skipped otherwise.
Expected values: the final score (Vitality 13-5) is the known result; plant rounds/sites
and roles were read off the parsed round log and checked for consistency with the
round end reasons and with how these players are known to play (ZywOo AWPs, ropz lurks).
"""

import os
from pathlib import Path

import polars as pl
import pytest

from playbook.config import ROOT

DEMO = Path(os.environ.get("PLAYBOOK_TEST_DEMO", ROOT / "data" / "raw" / "hltv-de_mirage-2394170.dem"))
pytestmark = pytest.mark.skipif(not DEMO.exists(), reason=f"test demo not found at {DEMO}")


@pytest.fixture(scope="module")
def tables():
    from playbook.parse import parse_demo
    from playbook.semantics import add_semantics

    return add_semantics(parse_demo(DEMO, verbose=False))


def test_match_result(tables):
    m = tables["matches"].row(0, named=True)
    assert m["map"] == "de_mirage"
    assert {m["team_a"]: m["score_a"], m["team_b"]: m["score_b"]} == {"B8": 5, "Vitality": 13}
    assert m["n_rounds"] == 18


def test_sides_swap_at_half(tables):
    r = tables["rounds"]
    assert set(r.filter(pl.col("half") == 1)["ct_team"]) == {"Vitality"}
    assert set(r.filter(pl.col("half") == 2)["ct_team"]) == {"B8"}


def test_score_before_round_is_cumulative(tables):
    last = tables["rounds"].filter(pl.col("round_num") == 18).row(0, named=True)
    # B8 (CT) had 5, Vitality (T) had 12 going into the final round
    assert (last["score_ct_before"], last["score_t_before"]) == (5, 12)


def test_plants_and_sites(tables):
    p = tables["plants"].sort("round_num")
    assert p["round_num"].to_list() == [6, 11, 12, 15, 16, 17, 18]
    assert p["site"].to_list() == ["B", "A", "B", "A", "A", "A", "B"]


def test_one_opening_kill_per_round(tables):
    k = tables["kills"]
    assert k.group_by("round_num").agg(pl.col("is_opening").sum())["is_opening"].to_list() == [1] * 18


def test_grenade_attribution(tables):
    u = tables["utility"]
    assert u.height > 250
    assert u["matched"].mean() > 0.95  # thrower recovered for almost every grenade
    assert u["land_place"].null_count() == 0


def test_positions_complete(tables):
    start = tables["positions"].filter(pl.col("t_s") == 0)
    assert start.group_by("round_num").len()["len"].to_list() == [10] * 18


def test_roles_match_known_players(tables):
    pr = tables["player_rounds"]
    awp = pr.group_by("name").agg(pl.col("is_awp").mean()).sort("is_awp", descending=True)
    assert awp["name"][0] == "ZywOo"
    t = pr.filter((pl.col("team") == "Vitality") & (pl.col("side") == "T"))
    lurk = t.group_by("name").agg(pl.col("dist_to_team_30s").mean()).sort("dist_to_team_30s", descending=True)
    assert lurk["name"][0] == "ropz"


def test_team_rounds_shape(tables):
    tr = tables["team_rounds"]
    assert tr.height == 36  # 18 rounds x 2 teams
    assert tr.group_by("round_num").agg(pl.col("won").sum())["won"].to_list() == [1] * 18
