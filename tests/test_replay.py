"""2D replay round files: frames per second, dead players hidden, events sorted, radar pixels."""
import polars as pl

from playbook.config import MapMeta
from playbook.replay import build_round

MM = MapMeta(name="de_test", display_name="Test", radar={"pos_x": 0.0, "pos_y": 100.0, "scale": 1.0})


def test_build_round():
    pos = []
    for t in range(4):
        pos.append({"demo_id": "d", "round_num": 1, "t_s": t, "steamid": "a", "name": "Ann", "side": "T", "team": "X",
                    "x": 10.0 + t, "y": 90.0, "alive": True})
        pos.append({"demo_id": "d", "round_num": 1, "t_s": t, "steamid": "b", "name": "Bob", "side": "CT", "team": "Y",
                    "x": 50.0, "y": 50.0, "alive": t < 2})
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
    assert [e["kind"] for e in r["events"]] == ["util", "kill"]
    assert r["events"][1]["by"] == 0 and r["events"][1]["victim"] == 1 and r["events"][0]["from"] is None
    assert r["wp_t"] == [0.5, 0.6, 0.8, 0.9]
    assert len(r["t_control"]) == len(r["frames"])
    assert 0 < r["t_control"][0] < 1
    assert r["t_control"][2] == 1 and r["t_control"][4] is None
    assert r["events"][1]["wpa"] == .2  # final outcome minus pre-kill T WP
