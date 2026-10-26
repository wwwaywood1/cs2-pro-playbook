"""Checked team facts (playbook/insights.py)."""

import math

import numpy as np
import polars as pl
import pytest

from playbook import insights as I

BASE = dict(fast=.30, late=.20, hit=.80, A=.50, split=.35, lurk=.45, fake=.15,
            forward=.35, stack=.20, far=.50, rotate=.60)


def league(seed: int, teams: int = 24, rounds_per_team: int = 6, effects: dict | None = None,
           spread: float = .6) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Synthetic map: every team pairs up once per round of the schedule; within a match
    each behaviour has its own random logit shift (rounds of a match are correlated)."""
    rng = np.random.default_rng(seed)
    names = [f"T{i:02d}" for i in range(teams)]
    plans, ct = [], []
    demo = 0
    for _ in range(rounds_per_team):
        for a, b in rng.permutation(teams).reshape(-1, 2):
            demo += 1
            for team in (names[a], names[b]):
                probs = {**BASE, **(effects or {}).get(team, {})}
                shift = {k: rng.normal(0, spread) for k in probs}

                def draw(key):
                    logit = math.log(probs[key]/(1-probs[key]))+shift[key]
                    return bool(rng.random() < 1/(1+math.exp(-logit)))
                for r in range(12):
                    hit = draw("hit")
                    tempo = "no_hit" if not hit else "fast" if draw("fast") else "late" if draw("late") else "mid"
                    plans.append(dict(demo_id=f"d{demo:03d}", round_num=r, team=team, gun=r != 0, won=draw("hit"),
                                      tempo=tempo, commit_s=30. if hit else None,
                                      attempt=("A" if draw("A") else "B") if hit or rng.random() < .3 else None,
                                      split=draw("split") if hit else None, lurk=draw("lurk") if hit else None,
                                      fake_from=("B" if draw("fake") else None) if hit else None,
                                      recipe_id=None, lurker_steamid=None, lurker_name=None))
                    far = draw("far")
                    ct.append(dict(demo_id=f"d{demo:03d}", round_num=r+12, team=team, gun=r != 0, won=draw("hit"),
                                   n_forward=int(draw("forward")), stack_site="A" if draw("stack") else None,
                                   shape_20s=f"A{1 + r % 2} M1 B{3 - r % 2}", n_far=int(far),
                                   n_rotated=int(draw("rotate")) if far else None))
    return pl.DataFrame(plans), pl.DataFrame(ct)


def naive_facts(plans: pl.DataFrame, ct: pl.DataFrame) -> int:
    """The earlier rule: round-level two-proportion z, |z| >= 2, >= 10 pp, >= 15 rounds."""
    frames = {"plans": plans.filter(pl.col("gun")), "ct": ct.filter(pl.col("gun"))}
    found = 0
    for _, _, table, keep, hit, _, _ in I.COMPARE:
        d = frames[table] if keep is None else frames[table].filter(keep)
        counts = d.group_by("team").agg(n=pl.len(), k=hit.cast(pl.Int64).sum())
        n_all, k_all = counts["n"].sum(), counts["k"].sum()
        for n, k in counts.select("n", "k").iter_rows():
            n0, k0 = n_all - n, k_all - k
            p = (k + k0) / (n + n0)
            se = math.sqrt(p * (1 - p) * (1 / n + 1 / n0))
            z = (k / n - k0 / n0) / se if se else 0.
            found += n >= 15 and abs(k / n - k0 / n0) >= .10 and abs(z) >= 2
    return found


def compare_facts(by_team: dict) -> list[dict]:
    return [f for facts in by_team.values() for f in facts if f["kind"] == "compare"]


def test_identical_teams_give_no_facts():
    plans, ct = league(seed=3)
    assert naive_facts(plans, ct) >= 3  # the old rule finds "differences" in pure noise
    tests = I.compare_tests(plans, ct)
    assert tests["tested"].all() and tests.height == 24 * len(I.COMPARE)
    assert compare_facts(I.map_insights(plans, ct, [], {})) == []
    # team_insights (what export.py calls) corrects over the whole map as well.
    assert all(f["kind"] != "compare" for t in ("T00", "T07", "T19") for f in I.team_insights(t, plans, ct, [], {}))


def test_identical_teams_rarely_give_facts_across_seeds():
    found = [len(compare_facts(I.map_insights(*league(seed=s, spread=1.), [], {}))) for s in range(12)]
    assert sum(found) <= 2, found


def test_real_difference_is_reported_with_p_and_q():
    plans, ct = league(seed=3, effects={"T05": dict(fast=.85), "T11": dict(forward=.03)})
    facts = I.map_insights(plans, ct, [], {})
    fast = next(f for f in facts["T05"] if f["id"] == "t_tempo_fast")
    assert fast["direction"] == "more" and fast["value"] - fast["baseline"] >= I.MIN_DIFF
    assert fast["matches"] == 6 and fast["rounds"] > 50
    assert 0 <= fast["p"] <= fast["q"] <= I.FDR_Q and fast["z"] > 3
    assert "高于" in fast["text"]["zh"] and f"{round(100 * fast['value'])}%" in fast["text"]["en"]
    forward = next(f for f in facts["T11"] if f["id"] == "ct_forward")
    assert forward["direction"] == "less" and forward["side"] == "CT"
    assert {t for t, fs in facts.items() for f in fs if f["kind"] == "compare"} == {"T05", "T11"}
    # Same facts, same order, whether asked per team (export.py) or per map.
    assert I.team_insights("T05", plans, ct, [], {}) == facts["T05"]


def test_teams_below_five_matches_are_not_tested():
    plans, ct = league(seed=3, effects={"T05": dict(fast=.95)})
    few = sorted(plans.filter(pl.col("team") == "T05")["demo_id"].unique().to_list())[:2]
    keep = (pl.col("team") != "T05") | pl.col("demo_id").is_in(few)
    plans, ct = plans.filter(keep), ct.filter(keep)
    tests = I.compare_tests(plans, ct).filter(pl.col("team") == "T05")
    assert (tests["matches"] == 2).all() and not tests["tested"].any() and tests["q"].is_nan().all()
    assert all(f["kind"] != "compare" for f in I.team_insights("T05", plans, ct, [], {}))


def test_benjamini_hochberg_and_intra_match_correlation():
    # sorted p .01 .03 .04 .20 -> p*m/rank .04 .06 .0533 .20 -> step-up minimum
    q = I.benjamini_hochberg(np.array([.01, .04, .03, .20]))
    np.testing.assert_allclose(q, [.04, .16 / 3, .16 / 3, .20])
    assert I.benjamini_hochberg(np.array([])).size == 0
    n = np.full(40, 20)
    # Every round of a match identical: correlation 1; binomial counts: about 0.
    k_same = np.r_[np.zeros(20), np.full(20, 20)]
    groups = np.repeat([0, 1], 20)
    assert I.intra_match_correlation(n, k_same, np.arange(40) % 2) == pytest.approx(1.)
    rng = np.random.default_rng(0)
    assert I.intra_match_correlation(np.full(400, 20), rng.binomial(20, .3, 400), np.arange(400) % 10) < .03
    # Differences between teams are not within-team clustering.
    assert I.intra_match_correlation(n, k_same, groups) == 0.


def test_min_matches_is_the_exporter_bar():
    from playbook import export
    assert I.MIN_MATCHES_RELIABLE == export.MIN_MATCHES_RELIABLE
