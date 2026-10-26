"""Checked facts about a team on a map, compared with every other team on that map.

Each fact is a number with its sample, the baseline (all other teams' gun rounds on the
map), a z score, p and q values, plus a short template sentence in Chinese and English.
This is the base for written analysis and teaching: an LLM may later rephrase these
sentences, but every claim must come from a fact here (DESIGN.md › Roadmap M4).

How a "compare" fact is tested (one test per team x fact, ~10 per team on a map):

* Unit = one team's rounds in one match (demo). Rounds of the same match share an
  opponent, a game state and a plan, so they are not independent; every variance below
  is computed from per-match counts, never from rounds as if they were coin flips.
* Statistic: share of the team minus share of all other teams (ratio of sums, i.e. the
  shares the sentence shows). Its variance is, for the team and for the rest separately,
  the larger of
    - the cluster-robust (sandwich) variance from per-match residuals, with the G/(G-1)
      small-sample factor, and
    - the design-effect variance under the null, p0(1-p0) * sum n_m (1 + (n_m - 1) rho) / n^2,
      with p0 the pooled share and rho the intra-match correlation estimated on the whole
      map by one-way ANOVA (matches nested in teams; Donner & Klar's adjusted test).
  The second term keeps a team whose few matches happen to look alike (or that never did
  the thing at all, robust variance 0) from looking more certain than the map-wide
  match-to-match variation allows; the first protects against teams that vary more than
  the map average. z = difference / sqrt(variance), two-sided normal p value.
* Only teams with >= MIN_MATCHES_RELIABLE matches (and >= MIN_ROUNDS rounds) in the
  comparison are tested; the same 5-match bar the exporter uses for low_sample.
* Multiplicity: Benjamini-Hochberg across all tested team x fact pairs of the map; a fact
  needs q <= FDR_Q and a difference of at least MIN_DIFF.
* Calibration (289-map snapshot, 6 maps x 200 shuffles of team labels across whole
  (match, team) units, i.e. no real team differences): 0.07 facts per map on average and
  P(p < 0.001) = 0.0005 per test. The earlier rule (round-level two-proportion |z| >= 2,
  >= 15 rounds, no correction) produced 8 facts per map under the same shuffles, against
  11 per map observed.

"Signature" facts (most used recipe, lurker, default setup) are descriptions of the team's
own rounds with their counts, not comparisons; they need MIN_SHARE.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import polars as pl

MIN_DIFF = 0.10
FDR_Q = 0.10
MIN_SHARE = 0.25
MIN_ROUNDS = 15
MIN_MATCHES_RELIABLE = 5  # same bar as export.MIN_MATCHES_RELIABLE (low_sample)

LABEL_ZH = {"fast": "快攻", "mid": "中期进攻", "late": "拖后进攻", "no_hit": "没打进包点",
            "A": "A 点", "B": "B 点"}
LABEL_EN = {"fast": "fast hits", "mid": "mid-round hits", "late": "late hits", "no_hit": "rounds without a hit",
            "A": "A", "B": "B"}

_HIT = pl.col("commit_s").is_not_null()
# id, side, table, which gun rounds count, what is counted, sentence subject zh / en
COMPARE = [
    ("t_tempo_fast", "T", "plans", None, pl.col("tempo") == "fast", LABEL_ZH["fast"], LABEL_EN["fast"]),
    ("t_tempo_late", "T", "plans", None, pl.col("tempo") == "late", LABEL_ZH["late"], LABEL_EN["late"]),
    ("t_site_A", "T", "plans", pl.col("attempt").is_not_null(), pl.col("attempt") == "A",
     "进攻 A 点的回合", "Rounds going A"),
    ("t_site_B", "T", "plans", pl.col("attempt").is_not_null(), pl.col("attempt") == "B",
     "进攻 B 点的回合", "Rounds going B"),
    ("t_split", "T", "plans", _HIT, pl.col("split").fill_null(False), "分兵进点", "Split hits"),
    ("t_lurk", "T", "plans", _HIT, pl.col("lurk").fill_null(False), "有人摸边的进攻", "Hits with a lurker"),
    ("t_fake", "T", "plans", _HIT, pl.col("fake_from").is_not_null(), "先假打再转点", "Fakes before the hit"),
    ("ct_forward", "CT", "ct", None, pl.col("n_forward") > 0, "开局有人前压的回合", "Rounds with an early push"),
    ("ct_stack", "CT", "ct", None, pl.col("stack_site").is_not_null(), "堆点防守的回合", "Stacked rounds"),
    ("ct_rotate", "CT", "ct", pl.col("n_far").fill_null(0) > 0, pl.col("n_rotated") > 0,
     "进攻开始后有人及时回防的回合", "Rounds where a CT rotated in time"),
]
SPECS = {spec[0]: spec for spec in COMPARE}


def _pct(x: float) -> str:
    return f"{round(100 * x)}%"


def _sig(x: float) -> float:
    return float(f"{x:.3g}")


def benjamini_hochberg(p: np.ndarray) -> np.ndarray:
    """BH-adjusted p values (q values), monotone step-up."""
    p = np.asarray(p, float)
    if not p.size:
        return p
    order = np.argsort(p, kind="stable")
    ranked = p[order] * p.size / np.arange(1, p.size + 1)
    q = np.empty_like(p)
    q[order] = np.minimum(np.minimum.accumulate(ranked[::-1])[::-1], 1.0)
    return q


def intra_match_correlation(n: np.ndarray, k: np.ndarray, group: np.ndarray) -> float:
    """ANOVA estimate of the intra-cluster correlation of a binary outcome.

    Clusters (one team's rounds in one match: n rounds, k successes) are nested in groups
    (teams), so differences between teams do not count as within-team clustering.
    """
    n, k = np.asarray(n, float), np.asarray(k, float)
    groups, idx = np.unique(group, return_inverse=True)
    df_c, df_w = len(n) - len(groups), n.sum() - len(n)
    if df_c <= 0 or df_w <= 0:
        return 0.0
    n_g, k_g = np.bincount(idx, n), np.bincount(idx, k)
    msc = float(np.sum(n * (k / n - (k_g / n_g)[idx]) ** 2)) / df_c
    msw = float(np.sum(k - k * k / n)) / df_w
    n0 = (n.sum() - float(np.sum(np.bincount(idx, n * n) / n_g))) / df_c
    denom = msc + (n0 - 1) * msw
    return float(np.clip((msc - msw) / denom, 0.0, 1.0)) if denom > 0 else 0.0


def cluster_tests(units: pl.DataFrame) -> pl.DataFrame:
    """Each team vs all other teams from per-match counts.

    units: one row per (demo_id, team) with n rounds and k successes.
    Returns team, value, baseline, rounds, matches, z, p (see module docstring).
    """
    if units.is_empty():
        return pl.DataFrame(schema={"team": pl.String, "value": pl.Float64, "baseline": pl.Float64,
                                    "rounds": pl.Int64, "matches": pl.Int64, "z": pl.Float64, "p": pl.Float64})
    teams, idx = np.unique(units["team"].to_numpy(), return_inverse=True)
    n, k = units["n"].to_numpy().astype(float), units["k"].to_numpy().astype(float)
    rho = intra_match_correlation(n, k, idx)

    def sums(v):
        return np.bincount(idx, v, minlength=len(teams))

    g_t = np.bincount(idx, minlength=len(teams)).astype(float)
    n_t, k_t, nn_t, kn_t, kk_t = sums(n), sums(k), sums(n * n), sums(k * n), sums(k * k)
    g_r, n_r, k_r = len(n) - g_t, n.sum() - n_t, k.sum() - k_t
    nn_r, kn_r, kk_r = (n * n).sum() - nn_t, (k * n).sum() - kn_t, (k * k).sum() - kk_t
    p0 = k.sum() / n.sum()

    with np.errstate(divide="ignore", invalid="ignore"):
        def variance(p_hat, g, size, nn, kn, kk):
            model = p0 * (1 - p0) * (size + rho * (nn - size)) / size ** 2
            ss = np.maximum(kk - 2 * p_hat * kn + p_hat ** 2 * nn, 0.0)  # sum of (k - p n)^2
            robust = np.where(g > 1, g / np.maximum(g - 1, 1) * ss / size ** 2, 0.0)
            return np.where(size > 0, np.maximum(model, robust), np.nan)

        share, base = k_t / n_t, np.where(n_r > 0, k_r / n_r, np.nan)
        var = variance(share, g_t, n_t, nn_t, kn_t, kk_t) + variance(base, g_r, n_r, nn_r, kn_r, kk_r)
        z = np.where(var > 0, (share - base) / np.sqrt(var), 0.0)
    z = np.nan_to_num(z)
    p = np.array([math.erfc(abs(v) / math.sqrt(2)) for v in z])
    return pl.DataFrame({"team": teams.tolist(), "value": share, "baseline": base, "rounds": n_t.astype(int),
                         "matches": g_t.astype(int), "z": z, "p": p})


def compare_tests(plans: pl.DataFrame, ct: pl.DataFrame) -> pl.DataFrame:
    """Every team x compare-fact test on the map, with BH q values over the tested pairs."""
    frames = {"plans": plans.filter(pl.col("gun")), "ct": ct.filter(pl.col("gun"))}
    out = []
    for fid, side, table, keep, hit, _, _ in COMPARE:
        d = frames[table].filter(pl.col("team").is_not_null())
        if keep is not None:
            d = d.filter(keep)
        units = d.group_by("demo_id", "team").agg(n=pl.len(), k=hit.cast(pl.Int64).sum()).sort("team", "demo_id")
        out.append(cluster_tests(units).with_columns(id=pl.lit(fid), side=pl.lit(side)))
    tests = pl.concat(out).with_columns(tested=(pl.col("matches") >= MIN_MATCHES_RELIABLE)
                                        & (pl.col("rounds") >= MIN_ROUNDS) & pl.col("baseline").is_not_nan())
    q = np.full(tests.height, np.nan)
    tested = tests["tested"].to_numpy()
    q[tested] = benjamini_hochberg(tests["p"].to_numpy()[tested])
    return tests.with_columns(q=pl.Series(q))


_LAST: dict = {}


def _map_tests(plans: pl.DataFrame, ct: pl.DataFrame) -> pl.DataFrame:
    """compare_tests, computed once per map when team_insights is called team by team."""
    if _LAST.get("plans") is not plans or _LAST.get("ct") is not ct:
        _LAST.clear()
        _LAST.update(plans=plans, ct=ct, tests=compare_tests(plans, ct))
    return _LAST["tests"]


def _compare_fact(test: dict) -> dict | None:
    if not test["tested"] or test["q"] > FDR_Q or abs(test["value"] - test["baseline"]) < MIN_DIFF:
        return None
    _, side, _, _, _, zh, en = SPECS[test["id"]]
    share, base, n = test["value"], test["baseline"], test["rounds"]
    more = share > base
    return {
        "id": test["id"], "side": side, "kind": "compare", "value": round(share, 3), "baseline": round(base, 3),
        "rounds": n, "matches": test["matches"], "z": round(test["z"], 2), "p": _sig(test["p"]), "q": _sig(test["q"]),
        "direction": "more" if more else "less",
        "text": {
            "zh": f"{zh}占 {_pct(share)}，{'高于' if more else '低于'}其他队伍的 {_pct(base)}（{n} 个枪局）",
            "en": f"{en}: {_pct(share)} vs {_pct(base)} for other teams ({n} gun rounds)",
        },
    }


def team_insights(team: str, plans: pl.DataFrame, ct: pl.DataFrame, recipes: list[dict],
                  spot_names: dict[str, dict]) -> list[dict]:
    """Facts for one team. plans/ct: all teams on the map (tactics.analyse_map output);
    the multiple-testing correction always covers every team on the map."""
    tests = {r["id"]: r for r in _map_tests(plans, ct).filter(pl.col("team") == team).iter_rows(named=True)}
    p = plans.filter(pl.col("gun"))
    mine = p.filter(pl.col("team") == team)
    facts: list[dict | None] = []

    def compare(fid: str) -> None:
        if fid in tests:
            facts.append(_compare_fact(tests[fid]))

    for fid in ("t_tempo_fast", "t_tempo_late", "t_site_A", "t_site_B", "t_split", "t_lurk", "t_fake"):
        compare(fid)

    # signature recipe: the team's most used execute, if it is a real habit
    used = mine.filter(pl.col("recipe_id").is_not_null()).group_by("recipe_id").agg(
        n=pl.len(), won=pl.col("won").sum()).sort("n", "recipe_id", descending=[True, False])
    hits = mine.filter(pl.col("commit_s").is_not_null()).height
    if used.height and hits >= MIN_ROUNDS:
        rid, n, won = used.row(0)
        if n / hits >= MIN_SHARE * 0.5 and n >= 4:
            r = next(x for x in recipes if x["id"] == rid)
            parts_zh = " + ".join((spot_names.get(c["spot_id"]) or {}).get("zh") or c["label"] for c in r["core"])
            parts_en = " + ".join((spot_names.get(c["spot_id"]) or {}).get("en") or c["label"] for c in r["core"])
            facts.append({
                "id": "t_signature_recipe", "side": "T", "kind": "signature", "value": round(n / hits, 3),
                "rounds": hits, "recipe_id": rid, "won": int(won), "win_rate": round(won / n, 3),
                "text": {"zh": f"最常用的爆弹：{r['site']} 点 {parts_zh}（{n} 次，赢 {int(won)} 次）",
                         "en": f"Go-to execute: {r['site']} with {parts_en} ({n} times, won {int(won)})"},
            })

    lurks = mine.filter(pl.col("lurk").fill_null(False)).group_by("lurker_steamid").agg(
        n=pl.len(), name=pl.col("lurker_name").mode().sort().first()).sort("n", "name", "lurker_steamid", descending=[True, False, False])
    if lurks.height and hits >= MIN_ROUNDS:
        sid, n, name = lurks.row(0)
        if n / hits >= MIN_SHARE * 0.5 and n >= 4:
            facts.append({
                "id": "t_main_lurker", "side": "T", "kind": "signature", "value": round(n / hits, 3), "rounds": hits,
                "steamid": str(sid), "name": name,
                "text": {"zh": f"{name} 是最常摸边的人（{n} 次进攻时在另一侧或远离进攻点）",
                         "en": f"{name} is the usual lurker ({n} hits with him on the other side or far away)"},
            })

    # CT side
    cm = ct.filter(pl.col("gun") & (pl.col("team") == team))
    compare("ct_forward")
    compare("ct_stack")
    if cm.height >= MIN_ROUNDS:
        top = cm.group_by("shape_20s").agg(n=pl.len(), won=pl.col("won").sum()).drop_nulls("shape_20s").sort(
            "n", "shape_20s", descending=[True, False])
        if top.height:
            shape, n, won = top.row(0)
            if n / cm.height >= MIN_SHARE:
                facts.append({
                    "id": "ct_default_setup", "side": "CT", "kind": "signature", "value": round(n / cm.height, 3),
                    "rounds": cm.height, "shape": shape, "won": int(won), "win_rate": round(won / n, 3),
                    "text": {"zh": f"CT 默认站位 {shape}（开局 20 秒，{_pct(n / cm.height)} 的枪局，胜率 {_pct(won / n)}）",
                             "en": f"Default CT setup {shape} at 20 s ({_pct(n / cm.height)} of gun rounds, won {_pct(won / n)})"},
                })
    compare("ct_rotate")
    return [f for f in facts if f]


def map_insights(plans: pl.DataFrame, ct: pl.DataFrame, recipes: list[dict],
                 spot_names: dict[str, dict]) -> dict[str, list[dict]]:
    """team -> facts for every team on the map (one BH family)."""
    teams = sorted(set(plans["team"].drop_nulls().to_list()) | set(ct["team"].drop_nulls().to_list()))
    return {team: team_insights(team, plans, ct, recipes, spot_names) for team in teams}


def fingerprint(facts: list[dict]) -> str:
    """Identity of a team's fact list; scripts/insight_text.py stamps written summaries with it."""
    key = json.dumps([[f["id"], f["text"]["en"]] for f in facts], sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def attach_summaries(teams: list[dict], path: Path) -> int:
    """Add the checked LLM paragraph (config/insight_text/<map>.json) to each team whose facts
    are unchanged since it was written. Stale or missing paragraphs are simply left out."""
    if not path.exists():
        return 0
    written = json.loads(path.read_text())
    n = 0
    for p in teams:
        w = written.get(p["slug"])
        if w and p.get("insights") and w.get("fingerprint") == fingerprint(p["insights"]):
            p["summary"] = {"zh": w["zh"], "en": w["en"], "facts": w["facts"]}
            n += 1
    return n
