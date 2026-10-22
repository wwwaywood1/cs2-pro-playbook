"""Optional end-to-end checks on MOUZ vs Legacy, Cologne 2026, Nuke (GPT-03).

Download both files from cs2povarchive/cs2-demos (Apache-2.0):
  iem_cologne_major_2026/2394905-mouz-vs-legacy-iem-cologne-major/
    mouz-vs-legacy-m2-nuke-p1.dem
    mouz-vs-legacy-m2-nuke-p2.dem
Set PLAYBOOK_TEST_MULTIPART_DIR to their parent directory, or keep the dataset
layout under data/raw/cs2povarchive. No network access occurs during tests.
"""
import os
from pathlib import Path

import polars as pl
import pytest

from playbook.config import ROOT

DIRECTORY = Path(os.environ.get("PLAYBOOK_TEST_MULTIPART_DIR", ROOT / "data/raw/cs2povarchive/iem_cologne_major_2026/2394905-mouz-vs-legacy-iem-cologne-major"))
PARTS = [DIRECTORY / f"mouz-vs-legacy-m2-nuke-p{i}.dem" for i in (1, 2)]
pytestmark = pytest.mark.skipif(not all(p.exists() for p in PARTS), reason="MOUZ-Legacy Nuke multipart fixture absent")


@pytest.fixture(scope="module")
def tables():
    from playbook.parse import parse_demo
    from playbook.semantics import add_semantics

    return add_semantics(parse_demo(PARTS, verbose=False))


def test_multipart_identity_rounds_and_score(tables):
    from playbook.parse import demo_identity

    m = tables["matches"].row(0, named=True)
    assert m["demo_id"] == demo_identity(PARTS[0])["demo_id"]
    assert m["demo_file"] == "+".join(p.name for p in PARTS)
    assert m["map"] == "de_nuke"
    assert m["n_rounds"] == m["score_a"] + m["score_b"] == 19
    assert {m["team_a"]: m["score_a"], m["team_b"]: m["score_b"]} == {"MOUZ": 13, "Legacy": 6}
    assert tables["economy"].filter(pl.col("buy_type") == "pistol")["round_num"].unique().sort().to_list() == [1, 13]
    r = tables["rounds"]
    assert r["round_num"].to_list() == list(range(1, 20))
    assert (r["score_ct_before"] + r["score_t_before"]).to_list() == list(range(19))
    assert r["start_tick"][2] > r["official_end_tick"][1]
    assert tables["players"]["steamid"].n_unique() == tables["players"].height == 10
    assert tables["team_rounds"].height == 38


def test_all_multipart_event_tables_have_valid_round_bounds(tables):
    r = tables["rounds"].select("round_num", "start_tick", "freeze_end_tick", "end_tick", "official_end_tick")
    for name, tick in (("positions", "tick"), ("kills", "tick"), ("plants", "tick"),
                       ("shots", "tick"), ("utility", "throw_tick")):
        events = tables[name].join(r, on="round_num", how="left")
        assert events.height == tables[name].height
        assert events["start_tick"].null_count() == 0
        assert events.filter((pl.col(tick) < pl.col("start_tick")) | (pl.col(tick) > pl.col("official_end_tick"))).is_empty()
        if name in ("positions", "shots"):
            assert events["team"].null_count() == 0
    assert tables["utility"]["nade_id"].n_unique() == tables["utility"].height
    assert tables["positions"].filter(pl.col("t_s") == 0).group_by("round_num").len()["len"].to_list() == [10] * 19
    assert tables["positions"].schema["yaw"] == pl.Float64
    assert tables["positions"].filter(pl.col("t_s") == 0)["yaw"].null_count() == 0
