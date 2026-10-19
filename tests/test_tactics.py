"""Tactic identification (playbook/tactics.py) on tiny synthetic inputs."""

from __future__ import annotations

import numpy as np
import polars as pl

from playbook.config import MapMeta
from playbook.tactics import (
    _bearing_groups,
    _tempo,
    average_linkage,
    density_clusters,
    jaccard_matrix,
    name_spots,
    site_centres,
    t_plans,
)

MM = MapMeta(name="de_test", display_name="Test", radar={"pos_x": 0.0, "pos_y": 4000.0, "scale": 4.0},
             callout_region={"BombsiteA": "A_SITE", "Ramp": "A_APPROACH", "Palace": "A_APPROACH", "BombsiteB": "B_SITE"},
             region_lane={"A_SITE": "A", "A_APPROACH": "A", "B_SITE": "B"})


def test_tempo_boundaries():
    assert [_tempo(None), _tempo(40), _tempo(40.5), _tempo(74.9), _tempo(75)] == ["no_hit", "fast", "mid", "mid", "late"]


def test_bearing_groups():
    assert _bearing_groups([]) == 0
    assert _bearing_groups([10]) == 1
    assert _bearing_groups([0, 10, 20]) == 1
    assert _bearing_groups([0, 90]) == 2
    assert _bearing_groups([-175, 175]) == 1  # wraps around 180


def test_density_clusters_blobs_noise_and_order():
    rng = np.random.default_rng(0)
    a = rng.normal([0, 0, 0], 20, (12, 3))
    b = rng.normal([1000, 0, 0], 20, (8, 3))
    pts = np.vstack([a, b, [[5000, 5000, 0]]])
    labels = density_clusters(pts, 160, 4)
    assert len(set(labels[:12])) == 1 and len(set(labels[12:20])) == 1 and labels[0] != labels[12]
    assert labels[-1] == -1
    perm = rng.permutation(len(pts))
    labels2 = density_clusters(pts[perm], 160, 4)
    # same partition regardless of input order
    groups = lambda lab, idx: {frozenset(idx[lab == k]) for k in set(lab) if k >= 0}  # noqa: E731
    assert groups(labels, np.arange(len(pts))) == groups(labels2, perm)


def test_jaccard_average_linkage():
    sets = [frozenset("ab"), frozenset("ab"), frozenset("cd"), frozenset("cde")]
    d = jaccard_matrix(sets)
    assert d[0, 1] == 0 and d[0, 2] == 1 and abs(d[2, 3] - 1 / 3) < 1e-9
    labels = average_linkage(d, 0.6)
    assert labels[0] == labels[1] and labels[2] == labels[3] and labels[0] != labels[2]
    assert len(set(average_linkage(d, 0.1))) == 3


def test_name_spots_nearest_within_radius():
    spots = pl.DataFrame({"spot_id": ["s1", "s2"], "side": ["T", "T"], "type": ["smoke", "smoke"],
                          "x": [0.0, 1000.0], "y": [0.0, 0.0]})
    names = [{"side": "T", "type": "smoke", "x": 50.0, "y": 0.0, "radius": 200, "en": "CT smoke", "zh": "警家烟"},
             {"side": "T", "type": "molotov", "x": 1000.0, "y": 0.0, "radius": 200, "en": "x", "zh": "x"}]
    assert name_spots(spots, names) == {"s1": {"en": "CT smoke", "zh": "警家烟"}}


def _round(entries: list[tuple[float, float]], plant_t: float | None = 35.0) -> dict[str, pl.DataFrame]:
    """One T round: each attacker walks from his entry point onto site A (centre 2000, 2000)
    at t = 28..31; two of them stand on BombsiteA from t = 30."""
    rows = []
    for i, (ex, ey) in enumerate(entries):
        for t in range(0, 40):
            if t < 29:
                x, y, place, region, lane = ex, ey, "Ramp" if i == 0 else "Palace", "A_APPROACH", "A"
            else:
                x, y, place, region, lane = 2000.0 + i * 30, 2000.0, "BombsiteA", "A_SITE", "A"
            rows.append({"demo_id": "d", "round_num": 1, "t_s": t, "steamid": 100 + i, "name": f"p{i}", "team": "Red",
                         "side": "T", "alive": True, "x": x, "y": y, "z": 0.0, "place": place, "region": region, "lane": lane})
    pos = pl.DataFrame(rows, schema_overrides={"round_num": pl.Int32, "t_s": pl.Int32, "steamid": pl.UInt64})
    tr = pl.DataFrame({
        "demo_id": ["d"], "round_num": [1], "team": ["Red"], "opponent": ["Blue"], "side": ["T"], "won": [True],
        "buy_type": ["full"], "plant_site": ["A" if plant_t else None], "plant_t_s": [plant_t],
        "shape_30s": ["A2"], "exec_n_util": [0], "exec_lane": [None],
    }, schema_overrides={"round_num": pl.Int32, "plant_t_s": pl.Float64, "exec_lane": pl.Utf8, "plant_site": pl.Utf8})
    util = pl.DataFrame(schema={"demo_id": pl.Utf8, "round_num": pl.Int32, "nade_id": pl.UInt32, "type": pl.Utf8,
                                "is_post_round": pl.Boolean, "thrower_side": pl.Utf8, "pop_t_s": pl.Float64,
                                "land_lane": pl.Utf8, "land_x": pl.Float64, "land_y": pl.Float64})
    plants = pl.DataFrame({"site": ["A"] * 3, "x": [2000.0] * 3, "y": [2000.0] * 3, "z": [0.0] * 3})
    return {"team_rounds": tr, "positions": pos, "utility": util, "plants": plants}


def test_t_plan_commit_target_split():
    sub = _round([(2800.0, 2000.0), (2000.0, 2800.0)])  # entries 1130 units apart, 90 degrees
    centres = site_centres(sub["plants"], sub["positions"])
    empty = pl.DataFrame(schema={"demo_id": pl.Utf8, "nade_id": pl.UInt32, "spot_id": pl.Utf8})
    p = t_plans(sub, MM, empty, centres).row(0, named=True)
    assert p["target"] == "A" and p["commit_s"] == 29.0 and p["tempo"] == "fast" and p["attempt"] == "A"
    assert p["split"] is True and p["entry_spread"] > 1000


def test_t_plan_single_entrance_is_not_split():
    sub = _round([(2800.0, 2000.0), (2820.0, 2030.0)])
    p = t_plans(sub, MM, pl.DataFrame(schema={"demo_id": pl.Utf8, "nade_id": pl.UInt32, "spot_id": pl.Utf8}),
                site_centres(sub["plants"], sub["positions"])).row(0, named=True)
    assert p["split"] is False


def test_t_plan_without_commit_is_no_hit_with_null_split():
    sub = _round([(2800.0, 2000.0)], plant_t=None)  # only one player ever reaches the core
    p = t_plans(sub, MM, pl.DataFrame(schema={"demo_id": pl.Utf8, "nade_id": pl.UInt32, "spot_id": pl.Utf8}),
                site_centres(sub["plants"], sub["positions"])).row(0, named=True)
    assert p["tempo"] == "no_hit" and p["target"] is None and p["split"] is None and p["lurk"] is None
