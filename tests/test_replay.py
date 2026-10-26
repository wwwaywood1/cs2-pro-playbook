"""2D replay round files: frames per second, dead players hidden, events sorted, radar pixels."""
import polars as pl
import pytest

from playbook.config import MapMeta
from playbook.replay import build_round

MM = MapMeta(name="de_test", display_name="Test", radar={"pos_x": 0.0, "pos_y": 100.0, "scale": 1.0})


@pytest.mark.parametrize("with_yaw", [False, True])
def test_build_round(with_yaw):
    pos = []
    for t in range(4):
        pos.append({"demo_id": "d", "round_num": 1, "t_s": t, "steamid": "a", "name": "Ann", "side": "T", "team": "X",
                    "x": 10.0 + t, "y": 90.0, "alive": True})
        pos.append({"demo_id": "d", "round_num": 1, "t_s": t, "steamid": "b", "name": "Bob", "side": "CT", "team": "Y",
                    "x": 50.0, "y": 50.0, "alive": t < 2})
    if with_yaw:
        for row in pos:
            row["yaw"] = [0., 90., 180., None][row["t_s"]] if row["steamid"] == "a" else -90.
    sub = {
        "matches": pl.DataFrame([{"demo_id": "d", "date": "2026-05-09", "date_precision": "day", "event": "Test Event"}]),
        "positions": pl.DataFrame(pos),
        "rounds": pl.DataFrame([{"demo_id": "d", "round_num": 1, "dur_s": 3.2, "t_team": "X", "ct_team": "Y",
                                 "winner_side": "T", "reason": "ct_killed"}]),
        "kills": pl.DataFrame([{"demo_id": "d", "round_num": 1, "t_s": 2.4, "is_post_round": False, "attacker_steamid": "a",
                                "victim_steamid": "b", "victim_x": 50.0, "victim_y": 50.0, "weapon": "ak47", "headshot": True}]),
        "utility": pl.DataFrame([{"demo_id": "d", "round_num": 1, "pop_t_s": 1.0, "is_post_round": False, "type": "smoke",
                                  "thrower_steamid": "a", "land_x": 30.0, "land_y": 70.0, "throw_x": None, "throw_y": None}],
                                schema_overrides={"throw_x": pl.Float64, "throw_y": pl.Float64}),
        "plants": pl.DataFrame(schema={"demo_id": pl.Utf8, "round_num": pl.Int64, "t_s": pl.Float64, "site": pl.Utf8,
                                       "x": pl.Float64, "y": pl.Float64}),
    }
    r = build_round(sub, MM, "d", 1, [0.5, 0.6, 0.8, 0.9])
    assert (r["date"], r["date_precision"], r["event"]) == ("2026-05-09", "day", "Test Event")
    assert r["duration"] == 4 and len(r["frames"]) == 5
    names = [p["name"] for p in r["players"]]
    assert names == ["Ann", "Bob"]                           # T first
    assert r["frames"][0] == [[10, 10], [50, 50]]          # radar px: y flipped around pos_y
    assert r["frames"][2][1] is None                        # dead players are hidden
    assert len(r["yaw"]) == len(r["frames"])
    assert all(len(angles) == len(r["players"]) for angles in r["yaw"])
    assert r["yaw"] == ([[0, 90], [270, 90], [180, None], [None, None], [None, None]]
                         if with_yaw else [[None, None]] * 5)
    assert [e["kind"] for e in r["events"]] == ["util", "kill"]
    assert r["events"][1]["by"] == 0 and r["events"][1]["victim"] == 1 and r["events"][0]["from"] is None
    assert r["wp_t"] == [0.5, 0.6, 0.8, 0.9]
    assert len(r["t_control"]) == len(r["frames"])
    assert 0 < r["t_control"][0] < 1
    assert r["t_control"][2] == 1 and r["t_control"][4] is None
    assert r["events"][1]["wpa"] == .2  # final outcome minus pre-kill T WP


def restart_round() -> dict[str, pl.DataFrame]:
    """A round whose restart before freeze end killed everyone ("world" self-kills at t < 0)."""
    pos = [{"demo_id": "d", "round_num": 1, "t_s": t, "steamid": sid, "name": name, "side": side, "team": team,
            "x": x, "y": 50.0, "alive": True}
           for t in range(4) for sid, name, side, team, x in [("a", "Ann", "T", "X", 10.0), ("b", "Bob", "CT", "Y", 60.0)]]
    kill = {"demo_id": "d", "round_num": 1, "is_post_round": False, "victim_x": 60.0, "victim_y": 50.0,
            "headshot": False}
    nade = {"demo_id": "d", "round_num": 1, "is_post_round": False, "type": "molotov", "thrower_steamid": "a",
            "land_x": 30.0, "land_y": 70.0, "throw_x": 10.0, "throw_y": 50.0}
    return {
        "positions": pl.DataFrame(pos),
        "rounds": pl.DataFrame([{"demo_id": "d", "round_num": 1, "dur_s": 3.2, "t_team": "X", "ct_team": "Y",
                                 "winner_side": "T", "reason": "ct_killed"}]),
        "kills": pl.DataFrame([
            {**kill, "t_s": -33.5, "attacker_steamid": "a", "victim_steamid": "a", "weapon": "world"},
            {**kill, "t_s": -33.5, "attacker_steamid": "b", "victim_steamid": "b", "weapon": "world"},
            {**kill, "t_s": 0.0, "attacker_steamid": "a", "victim_steamid": "b", "weapon": "ak47"},
        ]),
        "utility": pl.DataFrame([{**nade, "pop_t_s": pop} for pop in (1.0, 5.04, 5.06, 9.0)]),
        "plants": pl.DataFrame(schema={"demo_id": pl.Utf8, "round_num": pl.Int64, "t_s": pl.Float64, "site": pl.Utf8,
                                       "x": pl.Float64, "y": pl.Float64}),
    }


def test_kills_before_freeze_end_are_not_events_and_kill_nobody():
    r = build_round(restart_round(), MM, "d", 1, [0.5, 0.6, 0.8, 0.9])
    kills = [e for e in r["events"] if e["kind"] == "kill"]
    assert [(e["t"], e["by"], e["victim"], e["weapon"]) for e in kills] == [(0.0, 0, 1, "ak47")]  # t = 0 is live
    # The site hides a player once a kill event with him as victim has t <= now.
    assert not any(e["kind"] == "kill" and e["victim"] == 0 for e in r["events"])
    assert r["frames"][0] == [[10, 50], [60, 50]]


def test_grenades_popping_after_the_round_end_are_not_events():
    r = build_round(restart_round(), MM, "d", 1)
    assert r["duration"] == 4
    # Kept up to duration + 1 s (as rounded in the file): 5.04 -> 5.0 stays, 5.06 -> 5.1 goes.
    assert [e["t"] for e in r["events"] if e["kind"] == "util"] == [1.0, 5.0]
