"""Synthetic regressions for malformed histories and ambiguous player/event identity."""
import polars as pl
import pytest

from playbook.parse import _assign_round, _flag_opening, _resolve_teams, _validate_rounds, half_of
from playbook.utility import PlaceIndex, attribute_grenades


def rounds(nums=(1, 2)):
    return pl.DataFrame([
        dict(round_num=n, start_tick=i * 100, freeze_end_tick=i * 100 + 10,
             end_tick=i * 100 + 80, official_end_tick=i * 100 + 90,
             winner_side="terrorist") for i, n in enumerate(nums)
    ])


@pytest.mark.parametrize("nums", [(1, 1), (1, 2, 1), (6, 7), (1, 3)])
def test_reject_incomplete_or_restored_history(nums):
    with pytest.raises(ValueError, match="history"):
        _validate_rounds(rounds(nums))


@pytest.mark.parametrize("column,value", [("start_tick", 0), ("end_tick", 109), ("official_end_tick", None), ("winner_side", "unknown")])
def test_reject_invalid_bounds_and_winner(column, value):
    r = rounds().with_columns(pl.when(pl.col("round_num") == 2).then(pl.lit(value)).otherwise(pl.col(column)).alias(column))
    with pytest.raises(ValueError):
        _validate_rounds(r)


def test_round_gaps_do_not_capture_events():
    r = rounds()
    _validate_rounds(r)
    out = _assign_round(pl.DataFrame({"tick": [-1, 10, 95, 110, 191]}), "tick", r.drop("winner_side"))
    assert out.select("tick", "round_num").rows() == [(10, 1), (110, 2)]


def team_frames(missing_clans=False):
    # 1 stays, 2 reconnects; 5 replaces 2 in round 13 after the side switch.
    r = pl.DataFrame({"round_num": [1, 13, 25, 28, 31], "freeze_end_tick": [10, 20, 30, 40, 50]})
    rows = []
    for tick, first_side in [(10, 2), (20, 3), (30, 3), (40, 2), (50, 2)]:
        for sid in [1, 2 if tick in (10, 30) else 5, 3, 4]:
            rows.append((tick, sid, first_side if sid in (1, 2, 5) else 5 - first_side))
    tk = pl.DataFrame(rows, schema=["tick", "steamid", "team_num"], orient="row")
    roster = pl.DataFrame({"steamid": [1, 2, 3, 4, 5], "name": ["a", "b", "c", "d", "sub"],
                           "side": ["spectator"] * 5,
                           "team_clan_name": [None] * 5 if missing_clans else ["Alpha", None, "Bravo", None, None]},
                          schema_overrides={"team_clan_name": pl.String})
    return roster, tk, r


@pytest.mark.parametrize("missing_clans", [True, False])
def test_teams_survive_switch_substitution_reconnect_and_wrong_last_side(missing_clans):
    roster, tk, r = team_frames(missing_clans)
    teams, names = _resolve_teams(roster, tk, r, {})
    assert teams[1] == teams[2] == teams[5]
    assert teams[3] == teams[4] != teams[1]
    assert teams[1] == ("T-start team" if missing_clans else "Alpha")
    assert names[5] == "sub"
    assert [half_of(n) for n in r["round_num"]] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("sid", [0, None])
def test_bots_and_missing_ids_are_rejected(sid):
    roster, tk, r = team_frames()
    tk = tk.with_columns(pl.when(pl.col("steamid") == 5).then(pl.lit(sid)).otherwise(pl.col("steamid")).alias("steamid"))
    with pytest.raises(ValueError, match="Steam IDs"):
        _resolve_teams(roster, tk, r, {})


def test_warmup_bots_and_visitors_are_ignored_but_live_bots_are_not():
    from playbook.parse import _live_ticks

    roster, tk, r = team_frames()
    bounds = r.select("round_num", start_tick=pl.col("freeze_end_tick") - 5,
                      official_end_tick=pl.col("freeze_end_tick") + 4)
    warmup = pl.DataFrame({"tick": [1, 2], "steamid": [0, 77], "team_num": [2, 3]})
    live = _live_ticks(pl.concat([warmup, tk]), bounds)
    teams, _ = _resolve_teams(roster, live, r, {})
    assert 0 not in teams and 77 not in teams
    in_round = pl.DataFrame({"tick": [21], "steamid": [0], "team_num": [2]})
    with pytest.raises(ValueError, match="Steam IDs"):
        _resolve_teams(roster, _live_ticks(pl.concat([tk, in_round]), bounds), r, {})


def test_missing_freeze_end_side_is_explicit_error():
    roster, tk, r = team_frames()
    tk = tk.filter(~((pl.col("tick") == 20) & (pl.col("team_num") == 2)))
    with pytest.raises(ValueError, match="Missing"):
        _resolve_teams(roster, tk, r, {})


def test_identical_clan_names_are_rejected():
    roster, tk, r = team_frames()
    roster = roster.with_columns(team_clan_name=pl.lit("Same"))
    with pytest.raises(ValueError, match="same label"):
        _resolve_teams(roster, tk, r, {})


def test_conflicting_clans_are_rejected():
    roster, tk, r = team_frames()
    roster = roster.with_columns(pl.when(pl.col("steamid") == 2).then(pl.lit("Wrong")).otherwise(pl.col("team_clan_name")).alias("team_clan_name"))
    with pytest.raises(ValueError, match="Conflicting"):
        _resolve_teams(roster, tk, r, {})


def test_player_never_seen_at_freeze_end_is_rejected():
    roster, tk, r = team_frames()
    tk = pl.concat([tk, pl.DataFrame({"tick": [12], "steamid": [99], "team_num": [2]})])
    with pytest.raises(ValueError, match="never observed"):
        _resolve_teams(roster, tk, r, {})


def test_opening_ignores_world_teamkill_preround_and_postround_and_breaks_ties():
    k = pl.DataFrame({"round_num": [1]*7 + [2], "tick": [1, 2, 3, 4, 4, 5, 6, 7],
                      "t_s": [-1., 0., 1., 2., 2., 3., 4., 1.],
                      "attacker_team": ["A", None, "A", "A", "B", "A", "A", None],
                      "victim_team": ["B", "B", "A", "B", "A", "B", None, "B"],
                      "is_teamkill": [False, None, True, False, False, False, None, None],
                      "is_post_round": [False]*5 + [True, False, False]})
    out = _flag_opening(k)
    assert out["is_opening"].to_list() == [False, False, False, True, False, False, False, False]


def grenade_frames(thrower=None, t0=100, shot_ticks=(90, 90)):
    g = pl.DataFrame({"entity_id": [1, 1], "entity_serial": [1, 1], "type": ["smoke"]*2,
                      "tick": [t0, t0+100], "x": [0., 100.], "y": [0., 0.], "z": [64., 0.],
                      "thrower_steamid": [thrower, thrower]}, schema_overrides={"thrower_steamid": pl.UInt64})
    s = pl.DataFrame({"weapon": ["weapon_smokegrenade"]*2, "tick": list(shot_ticks),
                      "steamid": [11, 22], "name": ["a", "b"], "side": ["terrorist"]*2,
                      "x": [0., 10.], "y": [0., 0.], "z": [0., 0.], "pitch": [0., 0.], "yaw": [0., 0.]},
                     schema_overrides={"steamid": pl.UInt64})
    smoke = pl.DataFrame(schema={"entity_id": pl.Int64, "entity_serial": pl.Int64, "start_tick": pl.Int64,
                                "x": pl.Float64, "y": pl.Float64, "z": pl.Float64})
    return g, s, smoke


def test_grenade_known_thrower_beats_nearer_teammate():
    # Both teammates fired at the same tick; nearest feet belongs to the wrong player.
    out = attribute_grenades(*grenade_frames(22))
    assert out["thrower_steamid"][0] == 22
    assert out["throw_x"][0] == 10


def test_grenade_no_candidate_preserves_known_thrower():
    out = attribute_grenades(*grenade_frames(33))
    assert out["thrower_steamid"][0] == 33
    assert not out["matched"][0]


@pytest.mark.parametrize("rate,matched", [(64, False), (128, True)])
def test_grenade_window_is_half_second(rate, matched):
    out = attribute_grenades(*grenade_frames(t0=100, shot_ticks=(50, 50)), tick_rate=rate)
    assert out["matched"][0] == matched


def test_unsigned_grenade_ticks_near_zero_do_not_underflow():
    g, s, smoke = grenade_frames(t0=10, shot_ticks=(5, 5))
    out = attribute_grenades(g.with_columns(pl.col("tick").cast(pl.UInt32)), s, smoke)
    assert out["matched"][0]


def test_empty_place_index_returns_unknown():
    index = PlaceIndex.from_frame(pl.DataFrame(schema={"x": pl.Float64, "y": pl.Float64, "z": pl.Float64, "place": pl.String}))
    assert index.query([0.], [0.], [0.]) == [None]


def test_empty_rounds_are_rejected():
    with pytest.raises(ValueError, match="No complete"):
        _validate_rounds(rounds().head(0))


def test_shared_round_boundary_belongs_to_next_round():
    r = rounds().with_columns(pl.when(pl.col("round_num") == 1).then(100).otherwise(pl.col("official_end_tick")).alias("official_end_tick"))
    _validate_rounds(r)
    out = _assign_round(pl.DataFrame({"tick": [100, 100], "event": ["first", "second"]}), "tick", r.drop("winner_side"))
    assert out["round_num"].to_list() == [2, 2]
    assert out["event"].to_list() == ["first", "second"]


@pytest.mark.parametrize("rate", [0, -1, float("nan"), float("inf")])
def test_invalid_grenade_tick_rate_is_rejected(rate):
    with pytest.raises(ValueError, match="tick_rate"):
        attribute_grenades(*grenade_frames(), tick_rate=rate)


@pytest.mark.parametrize("score,winner", [({"A": 12, "B": 12}, None), ({"A": 5, "B": 13}, "B"), ({}, None)])
def test_tied_match_has_no_winner(score, winner):
    from playbook.parse import _match_winner
    assert _match_winner(score) == winner
