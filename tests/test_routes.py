"""Entry routes: dwell-based via callouts, resampling, grouping and medoid choice."""
import numpy as np
import polars as pl

from playbook.config import MapMeta
from playbook.tactics import _resample, _via, recipe_routes

MM = MapMeta(name="de_test", display_name="Test", radar={"pos_x": 0.0, "pos_y": 0.0, "scale": 1.0})


def test_via_needs_dwell_and_dedupes():
    assert _via(["S", "S", "X", "R", "R", "R", "A", "A"]) == ("S", "R", "A")
    assert _via(["S", "S", "R", "R", "S", "S"]) == ("S", "R", "S")


def test_resample_even_spacing():
    pts = _resample(np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]]), 5)
    assert pts.shape == (5, 2)
    assert np.allclose(pts[0], [0, 0]) and np.allclose(pts[-1], [10, 10]) and np.allclose(pts[2], [10, 0])


def _round(demo, rnd, players):
    rows = []
    for sid, path in players.items():
        for t, (x, y, place) in enumerate(path):
            rows.append({"demo_id": demo, "round_num": rnd, "t_s": t, "steamid": sid, "team": "Alpha",
                         "side": "T", "x": x, "y": -y, "place": place, "lane": "A" if x > 50 else "MID",
                         "alive": True})
    return rows


def test_routes_group_by_choke_and_drop_rare():
    ramp = [(0, 0, "S"), (0, 0, "S"), (40, 0, "R"), (60, 0, "R"), (80, 0, "Site"), (90, 0, "Site")]
    mid = [(0, 0, "S"), (0, 0, "S"), (0, 40, "M"), (0, 60, "M"), (80, 60, "Site"), (90, 60, "Site")]
    rows, plans = [], []
    for r in range(1, 6):
        players = {f"p{i}": ramp for i in range(4)}
        players["p9"] = mid if r == 1 else ramp  # mid used once: 1 of 25 paths, below the share floor
        rows += _round("d1", r, players)
        plans.append({"demo_id": "d1", "round_num": r, "team": "Alpha", "recipe_id": "rec", "commit_s": 5.0})
    pos = pl.DataFrame(rows).with_columns(pl.col("round_num").cast(pl.Int32), pl.col("t_s").cast(pl.Int32))
    out = recipe_routes(pl.DataFrame(plans).with_columns(pl.col("round_num").cast(pl.Int32)), pos, MM)
    routes = out["rec"]
    assert len(routes) == 1 and routes[0]["via"][-1] == "Site" and routes[0]["n"] == 24
    assert routes[0]["points"][0] == [0.0, 0.0] and routes[0]["points"][-1][0] == 90.0
