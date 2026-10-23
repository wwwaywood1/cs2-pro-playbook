"""Synthetic multipart histories, isolated ticks, and parser integration (GPT-03)."""
from pathlib import Path
from types import SimpleNamespace

import polars as pl
import pytest

from playbook.multipart import GameDemo, _stitch_rounds, ordered_paths
from playbook.parse import _validate_rounds


def rounds(nums, *, winner="terrorist"):
    return pl.DataFrame([
        dict(round_num=n, start_tick=i * 100, freeze_end_tick=i * 100 + 10,
             end_tick=i * 100 + 80, official_end_tick=i * 100 + 90,
             winner_side=winner, is_knife_round=False)
        for i, n in enumerate(nums)
    ], schema={"round_num": pl.Int32, "start_tick": pl.Int32, "freeze_end_tick": pl.Int32,
               "end_tick": pl.Int32, "official_end_tick": pl.Int32,
               "winner_side": pl.String, "is_knife_round": pl.Boolean})


def test_stitch_continuation_and_offset_all_bounds():
    r, kept, offsets = _stitch_rounds([rounds([1, 2]), rounds([3, 4])])
    _validate_rounds(r)
    assert r["round_num"].to_list() == [1, 2, 3, 4]
    assert offsets == [0, 191]
    assert [x.height for x in kept] == [2, 2]
    assert r.row(2, named=True)["freeze_end_tick"] == 201


def test_restore_keeps_later_complete_copy_and_replaces_old_suffix():
    r, kept, _ = _stitch_rounds([rounds([1, 2, 3]), rounds([2, 3, 4], winner="counter-terrorist")])
    assert [x["round_num"].to_list() for x in kept] == [[1], [2, 3, 4]]
    assert r["winner_side"].to_list() == ["terrorist"] + ["counter-terrorist"] * 3
    _validate_rounds(r)


def test_incomplete_trailing_round_uses_restored_complete_copy():
    p1 = rounds([1, 2]).with_columns(pl.when(pl.col("round_num") == 2).then(None).otherwise(pl.col("end_tick")).alias("end_tick"))
    r, kept, _ = _stitch_rounds([p1, rounds([2, 3])])
    assert [p.height for p in kept] == [1, 2]
    _validate_rounds(r)


def test_mid_round_start_keeps_earlier_complete_copy():
    p2 = rounds([2, 3]).with_columns(pl.when(pl.col("round_num") == 2).then(None).otherwise(pl.col("freeze_end_tick")).alias("freeze_end_tick"))
    r, kept, _ = _stitch_rounds([rounds([1, 2]), p2])
    assert [p["round_num"].to_list() for p in kept] == [[1, 2], [3]]
    _validate_rounds(r)


@pytest.mark.parametrize("parts,message", [
    ([rounds([1]), rounds([3])], "history"),
    ([rounds([1, 2]), rounds([2, 2])], "history"),
    ([rounds([2]), rounds([3])], "history"),
    ([rounds([1, 2, 3]), rounds([2])], "suffix"),
    ([rounds([1]), rounds([2], winner="unknown")], "winner"),
])
def test_inconsistent_histories_are_rejected(parts, message):
    with pytest.raises(ValueError, match=message):
        _stitch_rounds(parts)


def test_mid_round_without_freeze_end_and_complete_copy_is_rejected():
    p2 = rounds([2, 3]).with_columns(pl.when(pl.col("round_num") == 2).then(None).otherwise(pl.col("freeze_end_tick")).alias("freeze_end_tick"))
    with pytest.raises(ValueError, match="no complete copy"):
        _stitch_rounds([rounds([1]), p2])


def test_internal_incomplete_round_is_rejected():
    p2 = rounds([2, 3, 4]).with_columns(pl.when(pl.col("round_num") == 3).then(None).otherwise(pl.col("end_tick")).alias("end_tick"))
    with pytest.raises(ValueError, match="interior"):
        _stitch_rounds([rounds([1, 2, 3]), p2])


def test_three_parts_and_empty_pregame_recording():
    r, _, _ = _stitch_rounds([rounds([]), rounds([1, 2]), rounds([2, 3])])
    assert r["round_num"].to_list() == [1, 2, 3]


def game_adapter(parts, raw_rounds):
    demo = GameDemo.__new__(GameDemo)
    demo.parts = parts
    demo.tick_rate = 64
    demo.convars = {"mp_maxrounds": "24"}
    demo.rounds, demo.local_rounds, demo.offsets = _stitch_rounds(raw_rounds)
    return demo


def test_events_ticks_economy_and_snapshots_follow_round_ownership():
    def part(label):
        events = pl.DataFrame({"tick": [10, 110, 210, 999], "source": [label] * 4}, schema_overrides={"tick": pl.Int32})

        def snapshots(*, ticks):
            return pl.DataFrame({"tick": ticks, "source": [label] * len(ticks)})
        return SimpleNamespace(kills=events, bomb=events, shots=events,
                               ticks=lambda *a, **k: events, snapshots=snapshots,
                               round_economy=pl.DataFrame({"round_num": [1, 2, 3] if label == "old" else [2, 3, 4],
                                                           "equipment_value": [4200, 6000, 21000]}))
    demo = game_adapter([part("old"), part("new")], [rounds([1, 2, 3]), rounds([2, 3, 4])])
    for frame in [demo.kills, demo.bomb, demo.shots, demo.ticks([]),
                  demo.snapshots(ticks=demo.rounds["freeze_end_tick"].to_list())]:
        assert frame["source"].to_list() == ["old", "new", "new", "new"]
        assert frame["tick"].to_list() == [10, 301, 401, 501]
    assert demo.round_economy["round_num"].to_list() == [1, 2, 3, 4]


def test_reused_grenade_handles_are_attributed_per_part(monkeypatch):
    calls = []

    def attribute(g, shots, smokes, tick_rate):
        calls.append(g)
        return pl.DataFrame({"nade_id": [0], "throw_tick": [10], "pop_tick": [20], "thrower_steamid": [g]})
    monkeypatch.setattr("playbook.utility.attribute_grenades", attribute)
    parts = [SimpleNamespace(grenades=i, shots=None, smokes=None) for i in (11, 22)]
    demo = game_adapter(parts, [rounds([1]), rounds([2])])
    u = demo.attributed_grenades()
    assert calls == [11, 22]
    assert u["nade_id"].to_list() == [0, 1]
    assert u["throw_tick"].to_list() == [10, 101]
    assert u["pop_tick"].to_list() == [20, 111]
    assert u["thrower_steamid"].to_list() == [11, 22]


@pytest.mark.parametrize("names", [["a-p2.dem"], ["a-p1.dem", "a-p3.dem"],
                                   ["a.dem", "a-p1.dem"], ["a-p1.dem", "b-p2.dem"],
                                   ["a-p1.dem", "a-p1.dem"]])
def test_reject_ambiguous_or_missing_parts(names):
    with pytest.raises(ValueError):
        ordered_paths([Path(n) for n in names])


@pytest.mark.parametrize("change,message", [({"map_name": "de_nuke"}, "map or build"),
                                            ({"build_num": 2}, "map or build"),
                                            ({"tick_rate": 128}, "tick rate"),
                                            ({"mp_maxrounds": "30"}, "mp_maxrounds")])
def test_incompatible_parts_rejected(monkeypatch, change, message):
    def source(path):
        header = {"map_name": "de_mirage", "build_num": 1}
        convars = {"mp_maxrounds": "24"}
        rate = 64
        n = 1 if path.stem.endswith("p1") else 2
        if n == 2:
            header.update({k: v for k, v in change.items() if k in header})
            convars.update({k: v for k, v in change.items() if k in convars})
            rate = change.get("tick_rate", rate)
        return SimpleNamespace(header=header, convars=convars, tick_rate=rate, rounds=rounds([n]))
    monkeypatch.setattr("playbook.multipart.Demo", source)
    with pytest.raises(ValueError, match=message):
        GameDemo([Path("a-p1.dem"), Path("a-p2.dem")])


def test_buy_types_do_not_restart_at_each_part_or_overtime():
    from playbook.multipart import _round_buy_types

    e = pl.DataFrame({"round_num": [1, 3, 3, 4, 4, 13, 25, 28],
                      "equipment_value": [4200, 4999, 5000, 19999, 20000, 4200, 25000, 15000]})
    assert _round_buy_types(e, 24)["buy_type"].to_list() == [
        "pistol", "eco", "force", "force", "full", "pistol", "full", "force"]


def test_restore_suffix_can_finish_in_a_third_part():
    r, kept, _ = _stitch_rounds([rounds([1, 2, 3, 4]), rounds([3]), rounds([4, 5])])
    assert [x["round_num"].to_list() for x in kept] == [[1, 2], [3], [4, 5]]
    _validate_rounds(r)
