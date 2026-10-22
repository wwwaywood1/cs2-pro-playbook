"""Facing decoder, targeted refresh, radar orientation and frontend interpolation."""
import json
import math
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import polars as pl
import pytest

from playbook.config import load_map
from playbook.parse import position_yaw
from playbook.replay import radar_yaw
from playbook.store import TABLES, is_parsed
from scripts.reparse_replay_yaw import add_yaw


def test_awpy_eye_angle_yaw_is_nullable_degrees():
    angles = pl.DataFrame({"m_angEyeAngles": ["QAngle(10.5, -24.919052, 0)", "QAngle(0, 1.8e2, 0)",
                                              None, "bad", "QAngle(0, NaN, 0)", "QAngle(0, inf, 0)"]})
    result = angles.select(position_yaw())["yaw"]
    assert result.dtype == pl.Float64
    assert result.to_list() == [-24.919052, 180., None, None, None, None]


def test_yaw_only_refresh_preserves_rows_and_missing_players():
    pos = pl.DataFrame({"tick": [64, 0, 128], "steamid": [1, 1, 2], "alive": [True, True, False],
                        "x": [20., 10., 30.], "yaw": [999., 999., 999.]})
    calls = []

    def ticks(props, players_only):
        calls.append((props, players_only))
        return pl.DataFrame({"tick": [0, 32, 64], "steamid": [1, 1, 1],
                             "m_angEyeAngles": ["QAngle(0, 0, 0)", "QAngle(0, 50, 0)", "QAngle(0, 90, 0)"]})

    result = add_yaw(pos, SimpleNamespace(ticks=ticks))
    assert result.drop("yaw").equals(pos.drop("yaw"))
    assert result["yaw"].to_list() == [90., 0., None]
    assert calls == [(["m_angEyeAngles"], True)]


def test_store_reparses_legacy_positions_without_version_key(tmp_path):
    for name in TABLES:
        (tmp_path / name).mkdir()
        pl.DataFrame({"demo_id": ["d"]}).write_parquet(tmp_path / name / "d.parquet")
    assert not is_parsed("d", tmp_path)
    pl.DataFrame({"yaw": [None]}, schema={"yaw": pl.Float64}).write_parquet(tmp_path / "positions/d.parquet")
    assert is_parsed("d", tmp_path)


@pytest.mark.parametrize("world,radar", [(0, 0), (90, 270), (180, 180), (-90, 90),
                                        (359.8, 0), (450, 270), (None, None), (float("nan"), None), (float("inf"), None)])
def test_radar_yaw_cardinal_directions_and_unknown(world, radar):
    assert radar_yaw(world) == radar


def test_mirage_t_spawn_toward_mid_points_down_and_left_on_radar():
    mm = load_map("de_mirage")
    # Real sample: TYLOO-paiN Mirage, piriajr (T), round 16, t=1s,
    # tick 128354, looking from TSpawn toward the observed TopofMid centre.
    spawn, mid = (1422.0943603515625, 36.43707275390625), (348.92604064941406, -306.3343505859375)
    world_yaw = -162.27562
    angle = math.radians(radar_yaw(world_yaw))
    start, end = mm.to_radar(*spawn), mm.to_radar(*mid)
    expected = math.atan2(end[1] - start[1], end[0] - start[0])
    assert math.cos(angle - expected) > .9999
    assert math.cos(angle) < 0 and math.sin(angle) > 0


def test_frontend_shortest_angle_and_reduced_motion():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node with native TypeScript support is not installed")
    source = Path(__file__).resolve().parents[1] / "web/src/replayMath.ts"
    script = f'''import assert from 'node:assert/strict';
import {{frameYaw}} from {json.dumps(source.as_uri())};
assert.equal(frameYaw([[350], [10]], 0, .5), 0);
assert.equal(frameYaw([[10], [350]], 0, .5), 0);
assert.equal(frameYaw([[20], [100]], 0, .25), 40);
assert.equal(frameYaw([[350], [10]], 0, .5, false), 350);
assert.equal(frameYaw([[350], [10]], 0, 1, false), 10);
assert.equal(frameYaw(undefined, 0, .5), null);
assert.equal(frameYaw([], 0, .5), null);
assert.equal(frameYaw([[null], [10]], 0, .5), null);
assert.equal(frameYaw([[90], [null]], 0, .5), 90);
assert.equal(frameYaw([[NaN]], 0, 0), null);
assert.equal(frameYaw([[90]], 1, 0), null);
'''
    subprocess.run([node, "--input-type=module", "-e", script], check=True, capture_output=True, text=True)
