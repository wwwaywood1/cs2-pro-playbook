"""Win probability: state building, leakage-free folds, ΔWP sign conventions."""
import numpy as np
import polars as pl
import pytest

from playbook import winprob as W


def _tables(n_demos=6, rounds=4, secs=30, seed=0):
    rng = np.random.default_rng(seed)
    pos, rnd, plants, eco, matches, kills, util = [], [], [], [], [], [], []
    for d in range(n_demos):
        demo = f"d{d}"
        matches.append({"demo_id": demo, "map": "de_mirage" if d % 2 else "de_nuke"})
        for r in range(1, rounds + 1):
            t_wins = bool(rng.integers(0, 2))
            rnd.append({"demo_id": demo, "round_num": r, "dur_s": float(secs), "winner_side": "T" if t_wins else "CT",
                        "score_ct_before": 0, "score_t_before": 0})
            for side in ("T", "CT"):
                eco.append({"demo_id": demo, "round_num": r, "side": side, "equipment_value": 20000, "n_players": 5})
            for s in range(secs + 1):
                for i in range(5):
                    for side in ("T", "CT"):
                        losing = (side == "CT") == t_wins
                        dead = losing and s > secs // 2 and i < 3
                        pos.append({"demo_id": demo, "round_num": r, "t_s": float(s), "steamid": f"{side}{i}",
                                    "side": side, "lane": "A", "health": 0 if dead else 100, "alive": not dead})
            winner, loser = ("T", "CT") if t_wins else ("CT", "T")
            kills.append({"demo_id": demo, "round_num": r, "t_s": secs // 2 + 0.5, "is_post_round": False,
                          "is_teamkill": False, "attacker_steamid": f"{winner}0", "attacker_team": winner,
                          "attacker_side": winner, "victim_steamid": f"{loser}0", "victim_team": loser,
                          "victim_side": loser, "weapon": "ak47"})
    schema_p = {"t_s": pl.Float64}
    return {"positions": pl.DataFrame(pos, schema_overrides=schema_p), "rounds": pl.DataFrame(rnd),
            "plants": pl.DataFrame(schema={"demo_id": pl.Utf8, "round_num": pl.Int64, "t_s": pl.Float64,
                                           "site": pl.Utf8, "steamid": pl.Utf8, "team": pl.Utf8}),
            "economy": pl.DataFrame(eco), "matches": pl.DataFrame(matches), "kills": pl.DataFrame(kills),
            "utility": pl.DataFrame(schema={"demo_id": pl.Utf8, "round_num": pl.Int64, "type": pl.Utf8,
                                            "pop_t_s": pl.Float64, "is_post_round": pl.Boolean,
                                            "thrower_steamid": pl.Utf8, "thrower_team": pl.Utf8,
                                            "thrower_side": pl.Utf8})}


def test_states_counts_and_label():
    t = _tables()
    d = W.states(t)
    assert d.height == 6 * 4 * 31
    first = d.filter(pl.col("t_s") == 0)
    assert (first["alive_T"] == 5).all() and (first["alive_CT"] == 5).all()
    assert set(d["t_win"].unique().to_list()) <= {0, 1}
    assert (d["time_left"] == W.ROUND_TIME_S - d["t_s"]).all()


def test_folds_never_share_a_match():
    pytest.importorskip("sklearn")
    from sklearn.model_selection import GroupKFold
    d = W.states(_tables())
    x, _ = W.feature_matrix(d, ["de_mirage", "de_nuke"])
    g = d["demo_id"].to_numpy()
    for tr, te in GroupKFold(n_splits=3).split(x, d["t_win"].to_numpy(), g):
        assert not set(g[tr]) & set(g[te])


def test_oof_learns_alive_signal_and_kill_sign():
    pytest.importorskip("sklearn")
    t = _tables(n_demos=10)
    d = W.states(t)
    oof, m = W.fit_oof(d)
    late = d.with_columns(pl.Series("p", oof)).filter(pl.col("t_s") > 20)
    assert (late.filter(pl.col("t_win") == 1)["p"].mean() > late.filter(pl.col("t_win") == 0)["p"].mean())
    ev = W.action_values(t, W.wp_lookup(d, oof))
    assert (ev.filter(pl.col("action") == "kill")["dwp"].mean() > 0)
    assert (ev.filter(pl.col("action") == "death")["dwp"].mean() < 0)
    assert 0 <= m["model"]["brier"] <= 0.25


def _wp_table(rows):
    return pl.DataFrame(rows, schema={"demo_id": pl.Utf8, "round_num": pl.Int64, "t_s": pl.Float64, "wp_t": pl.Float64},
                        orient="row")


def _one_round_tables(dur=10.0, winner="T", kill_t=9.5, util=()):
    kills = pl.DataFrame([{"demo_id": "d", "round_num": 1, "t_s": kill_t, "is_post_round": False, "is_teamkill": False,
                           "attacker_steamid": "a", "attacker_team": "A", "attacker_side": "T",
                           "victim_steamid": "v", "victim_team": "B", "victim_side": "CT", "weapon": "ak47"}])
    utility = pl.DataFrame([{"demo_id": "d", "round_num": 1, "type": typ, "pop_t_s": at, "is_post_round": False,
                             "thrower_steamid": "a", "thrower_team": "A", "thrower_side": "T"} for typ, at in util],
                           schema={"demo_id": pl.Utf8, "round_num": pl.Int64, "type": pl.Utf8, "pop_t_s": pl.Float64,
                                   "is_post_round": pl.Boolean, "thrower_steamid": pl.Utf8, "thrower_team": pl.Utf8,
                                   "thrower_side": pl.Utf8})
    return {"kills": kills, "utility": utility,
            "plants": pl.DataFrame(schema={"demo_id": pl.Utf8, "round_num": pl.Int64, "t_s": pl.Float64,
                                           "site": pl.Utf8, "steamid": pl.Utf8, "team": pl.Utf8}),
            "rounds": pl.DataFrame([{"demo_id": "d", "round_num": 1, "dur_s": dur, "winner_side": winner}]),
            "matches": pl.DataFrame([{"demo_id": "d", "map": "de_mirage"}])}


def test_round_ending_kill_takes_the_outcome():
    t = _one_round_tables(dur=10.0, winner="T", kill_t=9.5)
    wp = _wp_table([("d", 1, float(s), 0.6) for s in range(11)])
    ev = W.action_values(t, wp, adjust_drift=False)
    kill = ev.filter(pl.col("action") == "kill")
    assert kill.height == 1 and kill["dwp"][0] == pytest.approx(0.4)    # 0.6 -> 1.0 (T won)
    death = ev.filter(pl.col("action") == "death")
    assert death["dwp"][0] == pytest.approx(-0.4)


def test_flashbangs_count_as_utility():
    assert "flashbang" in W.UTILITY and "flash" not in W.UTILITY and "decoy" not in W.UTILITY
    from playbook.utility import WEAPON_TYPE
    assert set(W.UTILITY) <= set(WEAPON_TYPE.values())
    t = _one_round_tables(dur=30.0, kill_t=25.0, util=[("flashbang", 3.2), ("decoy", 4.0)])
    wp = _wp_table([("d", 1, float(s), 0.5) for s in range(31)])
    ev = W.action_values(t, wp, adjust_drift=False)
    assert ev.filter(pl.col("action") == "utility")["detail"].to_list() == ["flashbang"]


def test_drift_adjustment_removes_the_clock():
    # WP falls 1 pp per second for T whatever happens: a mid-round flash changes nothing real
    t = _one_round_tables(dur=40.0, winner="CT", kill_t=39.5, util=[("smoke", 20.4)])
    wp = _wp_table([("d", 1, float(s), 0.8 - 0.01 * s) for s in range(41)])
    raw = W.action_values(t, wp, adjust_drift=False).filter(pl.col("action") == "utility")["dwp"][0]
    adj = W.action_values(t, wp).filter(pl.col("action") == "utility")["dwp"][0]
    assert raw == pytest.approx(-0.02) and adj == pytest.approx(0.0, abs=1e-9)


def test_pre_freeze_kills_are_ignored():
    t = _one_round_tables(dur=10.0, kill_t=-5.0)
    wp = _wp_table([("d", 1, float(s), 0.5) for s in range(11)])
    assert W.action_values(t, wp).filter(pl.col("action").is_in(["kill", "death"])).height == 0


def test_recipe_wp_uses_the_outcome_when_the_round_ends_early():
    plans = pl.DataFrame([{"demo_id": "d", "round_num": 1, "recipe_id": "r1", "commit_s": 8.0}])
    wp = _wp_table([("d", 1, float(s), 0.5) for s in range(13)])
    rounds = pl.DataFrame([{"demo_id": "d", "round_num": 1, "winner_side": "T"}])
    assert W.recipe_wp(plans, wp, rounds=rounds)["r1"]["after"] == 1.0
    assert W.recipe_wp(plans, wp)["r1"]["after"] == 0.5
