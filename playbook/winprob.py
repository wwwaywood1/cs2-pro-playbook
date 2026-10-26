"""Round win probability and win-probability added (WPA) per action.

The simple, reproducible counterpart of Szmida & Toka (MIT Sloan 2025, temporal heterogeneous
GNN) and Xenopoulos et al. (arXiv 2011.01324): a gradient-boosted classifier on 1 Hz game
states predicts whether the T side wins the round; an action is worth the change in that
probability around it, seen from the acting team.

Leakage: predictions used for the site are out-of-fold (GroupKFold by match), so a match is
never scored by a model that saw it. Metrics are reported on those out-of-fold predictions.
"""

from __future__ import annotations

import math

import numpy as np
import polars as pl

from playbook.utility import WEAPON_TYPE

ROUND_TIME_S = 115.0   # CS2 round timer after freeze time
BOMB_TIME_S = 40.0     # C4 timer
LANES = ("T_SPAWN", "A", "MID", "B", "CT_SPAWN", "OTHER")
# grenade types as the parser names them ("flashbang", not "flash"); decoys carry no value
UTILITY = tuple(sorted(set(WEAPON_TYPE.values()) - {"decoy"}))
N_FOLDS = 5
DRIFT_BUCKET_S = 10     # time buckets for the no-event drift baseline (5 s after a plant)


def states(t: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """One row per (demo, round, second) during live play, T-side perspective, with the label."""
    p = t["positions"].filter(pl.col("t_s") >= 0)
    alive = p.filter(pl.col("alive"))
    base = p.group_by("demo_id", "round_num", "t_s").agg(pl.len().alias("_n"))
    agg = alive.group_by("demo_id", "round_num", "t_s").agg(
        *[(pl.col("side") == s).sum().alias(f"alive_{s}") for s in ("T", "CT")],
        *[pl.col("health").filter(pl.col("side") == s).sum().alias(f"hp_{s}") for s in ("T", "CT")],
        *[((pl.col("side") == s) & (pl.col("lane") == ln)).sum().alias(f"{s}_{ln}")
          for s in ("T", "CT") for ln in LANES],
    )
    d = base.join(agg, on=["demo_id", "round_num", "t_s"], how="left").fill_null(0).drop("_n")

    r = t["rounds"].select("demo_id", "round_num", "dur_s", "winner_side",
                           "score_ct_before", "score_t_before")
    d = d.join(r, on=["demo_id", "round_num"], how="inner").filter(pl.col("t_s") <= pl.col("dur_s"))

    plants = t["plants"].group_by("demo_id", "round_num").agg(
        pl.col("t_s").min().alias("plant_s"), pl.col("site").first().alias("plant_site"))
    d = d.join(plants, on=["demo_id", "round_num"], how="left")
    planted = pl.col("plant_s").is_not_null() & (pl.col("t_s") >= pl.col("plant_s"))
    d = d.with_columns(
        planted.cast(pl.Int8).alias("planted"),
        (planted & (pl.col("plant_site") == "A")).cast(pl.Int8).alias("planted_A"),
        pl.when(planted).then(BOMB_TIME_S - (pl.col("t_s") - pl.col("plant_s")))
          .otherwise(ROUND_TIME_S - pl.col("t_s")).clip(0, None).alias("time_left"),
    )

    eco = t["economy"].select("demo_id", "round_num", "side", "equipment_value", "n_players")
    for s in ("T", "CT"):
        e = eco.filter(pl.col("side") == s).select(
            "demo_id", "round_num",
            (pl.col("equipment_value") / pl.col("n_players").clip(1, None)).alias(f"_eq_{s}"))
        d = d.join(e, on=["demo_id", "round_num"], how="left")
        d = d.with_columns((pl.col(f"_eq_{s}").fill_null(0) * pl.col(f"alive_{s}")).alias(f"equip_{s}")).drop(f"_eq_{s}")

    maps = t["matches"].select("demo_id", "map")
    d = d.join(maps, on="demo_id", how="left").with_columns(
        (pl.col("alive_T") - pl.col("alive_CT")).alias("alive_diff"),
        (pl.col("equip_T") - pl.col("equip_CT")).alias("equip_diff"),
        (pl.col("score_t_before") - pl.col("score_ct_before")).alias("score_diff"),
        (pl.col("winner_side") == "T").cast(pl.Int8).alias("t_win"),
    )
    return d.sort("demo_id", "round_num", "t_s")


def feature_matrix(d: pl.DataFrame, maps: list[str]) -> tuple[np.ndarray, list[str]]:
    cols = ["alive_T", "alive_CT", "alive_diff", "hp_T", "hp_CT", "equip_T", "equip_CT", "equip_diff",
            "time_left", "planted", "planted_A", "score_diff",
            *[f"{s}_{ln}" for s in ("T", "CT") for ln in LANES]]
    x = d.select(cols).to_numpy().astype(np.float32)
    onehot = np.stack([(d["map"] == m).to_numpy() for m in maps], axis=1).astype(np.float32)
    return np.hstack([x, onehot]), cols + [f"map_{m}" for m in maps]


BASELINE = ["alive_T", "alive_CT", "time_left", "planted"]


def _metrics(y: np.ndarray, p: np.ndarray) -> dict:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    bins = np.minimum((p * 10).astype(int), 9)
    calib = [{"bin": f"{b / 10:.1f}-{(b + 1) / 10:.1f}", "n": int((bins == b).sum()),
              "predicted": round(float(p[bins == b].mean()), 3) if (bins == b).any() else None,
              "observed": round(float(y[bins == b].mean()), 3) if (bins == b).any() else None}
             for b in range(10)]
    return {"log_loss": round(float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))), 4),
            "brier": round(float(np.mean((p - y) ** 2)), 4),
            "accuracy": round(float(np.mean((p >= .5) == y)), 4), "calibration": calib}


def fit_oof(d: pl.DataFrame, seed: int = 0, model_artifacts: list | None = None) -> tuple[np.ndarray, dict]:
    """Out-of-fold T win probability for every state, plus metrics vs the baseline."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold

    maps = sorted(d["map"].unique().to_list())
    x, names = feature_matrix(d, maps)
    xb = d.select(BASELINE).to_numpy().astype(np.float32)
    y = d["t_win"].to_numpy()
    groups = d["demo_id"].to_numpy()
    oof, oof_b = np.zeros(len(y)), np.zeros(len(y))
    folds = GroupKFold(n_splits=min(N_FOLDS, len(set(groups))))
    importance = np.zeros(len(names))
    for tr, te in folds.split(x, y, groups):
        m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_leaf_nodes=31,
                                           l2_regularization=1.0, random_state=seed)
        m.fit(x[tr], y[tr])
        oof[te] = m.predict_proba(x[te])[:, 1]
        if model_artifacts is not None:
            model_artifacts.append({'model': m, 'test_demos': set(groups[te]),
                                    'train_indices': tr, 'maps': maps, 'names': names})
        b = LogisticRegression(max_iter=1000).fit(xb[tr], y[tr])
        oof_b[te] = b.predict_proba(xb[te])[:, 1]
        # permutation-free importance proxy: drop in log loss when one feature is shuffled (cheap sample)
        rng = np.random.default_rng(seed)
        sample = te[rng.choice(len(te), size=min(4000, len(te)), replace=False)]
        base_ll = _metrics(y[sample], m.predict_proba(x[sample])[:, 1])["log_loss"]
        for j in range(len(names)):
            xs = x[sample].copy()
            xs[:, j] = rng.permutation(xs[:, j])
            importance[j] += _metrics(y[sample], m.predict_proba(xs)[:, 1])["log_loss"] - base_ll
    raw = oof.copy()
    if model_artifacts is not None:
        from sklearn.isotonic import IsotonicRegression
        for artifact in model_artifacts:
            tr = artifact.pop('train_indices')
            artifact['calibrator'] = IsotonicRegression(out_of_bounds='clip', y_min=0., y_max=1.).fit(raw[tr], y[tr])
    oof = calibrate_oof(oof, y, groups)
    top = sorted(zip(names, importance / folds.get_n_splits()), key=lambda kv: -kv[1])[:10]
    metrics = {"model_uncalibrated": _metrics(y, raw), "rows": int(len(y)), "matches": int(len(set(groups))), "folds": folds.get_n_splits(),
               "model": _metrics(y, oof), "baseline_alive_time": _metrics(y, oof_b),
               "top_features": [{"feature": k, "log_loss_increase": round(float(v), 4)} for k, v in top]}
    return oof, metrics


def calibrate_oof(p: np.ndarray, y: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Isotonic calibration, cross-fitted by match so no match calibrates its own predictions."""
    from sklearn.isotonic import IsotonicRegression
    from sklearn.model_selection import GroupKFold

    out = np.zeros(len(p))
    for tr, te in GroupKFold(n_splits=min(N_FOLDS, len(set(groups)))).split(p, y, groups):
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(p[tr], y[tr])
        out[te] = iso.predict(p[te])
    return out


def wp_lookup(d: pl.DataFrame, wp_t: np.ndarray) -> pl.DataFrame:
    return d.select("demo_id", "round_num", "t_s").with_columns(pl.Series("wp_t", wp_t.round(4)))


def _event_frames(t: dict[str, pl.DataFrame]) -> list[pl.DataFrame]:
    """Kills, deaths, utility pops and plants as (demo, round, t_s, steamid, team, side, action, detail)."""
    k = t["kills"].filter(~pl.col("is_post_round") & ~pl.col("is_teamkill") & (pl.col("t_s") >= 0))
    kills = k.select("demo_id", "round_num", "t_s", pl.col("attacker_steamid").alias("steamid"),
                     pl.col("attacker_team").alias("team"), pl.col("attacker_side").alias("side"),
                     pl.lit("kill").alias("action"), pl.col("weapon").alias("detail"))
    deaths = k.select("demo_id", "round_num", "t_s", pl.col("victim_steamid").alias("steamid"),
                      pl.col("victim_team").alias("team"), pl.col("victim_side").alias("side"),
                      pl.lit("death").alias("action"), pl.col("weapon").alias("detail"))
    u = t["utility"].filter(~pl.col("is_post_round") & pl.col("type").is_in(UTILITY) & pl.col("pop_t_s").is_not_null()
                            & (pl.col("pop_t_s") >= 0))
    util = u.select("demo_id", "round_num", pl.col("pop_t_s").alias("t_s"), pl.col("thrower_steamid").alias("steamid"),
                    pl.col("thrower_team").alias("team"), pl.col("thrower_side").alias("side"),
                    pl.lit("utility").alias("action"), pl.col("type").alias("detail"))
    pl_ = t["plants"].select("demo_id", "round_num", "t_s", "steamid", "team", pl.lit("T").alias("side"),
                             pl.lit("plant").alias("action"), pl.col("site").alias("detail"))
    return [f.with_columns(pl.col("steamid").cast(pl.Utf8), pl.col("t_s").cast(pl.Float64))
            for f in (kills, deaths, util, pl_)]


def _drift_keys(frame: pl.DataFrame, t: dict[str, pl.DataFrame], second: str) -> pl.DataFrame:
    """Add (map, planted, bucket) for the state at integer second ``second``."""
    plants = t["plants"].group_by("demo_id", "round_num").agg(pl.col("t_s").min().alias("_plant"))
    maps = t["matches"].select("demo_id", "map")
    planted = pl.col("_plant").is_not_null() & (pl.col(second) >= pl.col("_plant"))
    return (frame.join(plants, on=["demo_id", "round_num"], how="left").join(maps, on="demo_id", how="left")
            .with_columns(planted.alias("_planted"),
                          pl.when(planted).then(((pl.col(second) - pl.col("_plant")) // 5).cast(pl.Int64))
                            .otherwise((pl.col(second) // DRIFT_BUCKET_S).cast(pl.Int64)).alias("_bucket"))
            .drop("_plant"))


def drift_baseline(t: dict[str, pl.DataFrame], wp: pl.DataFrame, after: int = 2) -> pl.DataFrame:
    """Mean change of T win probability over ``after`` seconds in windows where nothing happens.

    The game clock alone moves win probability (towards CT before a plant, towards T after it).
    Averaging the change over quiet windows (no kill, grenade pop or plant) by map, plant state and
    time bucket gives the drift an action window would have seen anyway.
    """
    w = wp.with_columns(pl.col("t_s").cast(pl.Int64).alias("_s")).drop("t_s")
    nxt = w.rename({"wp_t": "_wp_next"}).with_columns(pl.col("_s") - after)
    win = w.join(nxt, on=["demo_id", "round_num", "_s"], how="inner")
    busy = pl.concat([f.select("demo_id", "round_num", pl.col("t_s").floor().cast(pl.Int64).alias("_e"))
                      for f in _event_frames(t)])
    busy = pl.concat([busy.with_columns((pl.col("_e") - k).alias("_s")) for k in range(after)]).select(
        "demo_id", "round_num", "_s").unique()
    quiet = win.join(busy, on=["demo_id", "round_num", "_s"], how="anti")
    quiet = _drift_keys(quiet, t, "_s").with_columns((pl.col("_wp_next") - pl.col("wp_t")).alias("_d"))
    return quiet.group_by("map", "_planted", "_bucket").agg(pl.col("_d").mean().alias("drift_T"), pl.len().alias("n"))


def action_values(t: dict[str, pl.DataFrame], wp: pl.DataFrame, before: int = 1, after: int = 2,
                  adjust_drift: bool = True) -> pl.DataFrame:
    """ΔWP for kills, deaths, utility pops, plants; positive = good for the acting player's team.

    WP before = state at floor(t) - before + 1 (last full second before the event),
    WP after = state at floor(t) + after; when the round ends inside that window the outcome
    (1 for a T win, 0 otherwise) is the state after. Events before freeze end are ignored.

    ``adjust_drift`` subtracts what the clock alone would have done over the same window
    (``drift_baseline``), so a player is not credited or charged for time passing: without it,
    most T players come out negative and most CT players positive.
    """
    w = wp.with_columns(pl.col("t_s").cast(pl.Int64).alias("_s")).drop("t_s")
    last = w.group_by("demo_id", "round_num").agg(pl.col("_s").max().alias("_last"))
    outcome = t["rounds"].select("demo_id", "round_num", (pl.col("winner_side") == "T").cast(pl.Float64).alias("_out"))
    drift = drift_baseline(t, wp, after) if adjust_drift else None

    def attach(ev: pl.DataFrame) -> pl.DataFrame:
        ev = ev.with_columns(pl.col("t_s").floor().cast(pl.Int64).alias("_s"))
        pre = w.rename({"wp_t": "wp_before"}).with_columns(pl.col("_s") + (before - 1))
        post = w.rename({"wp_t": "wp_after"}).with_columns(pl.col("_s") - after)
        ev = ev.join(pre, on=["demo_id", "round_num", "_s"], how="inner")
        ev = ev.join(post, on=["demo_id", "round_num", "_s"], how="left")
        ev = ev.join(last, on=["demo_id", "round_num"], how="left").join(outcome, on=["demo_id", "round_num"], how="left")
        ev = ev.with_columns(pl.when(pl.col("wp_after").is_null() & (pl.col("_s") + after > pl.col("_last")))
                             .then(pl.col("_out")).otherwise(pl.col("wp_after")).alias("wp_after"))
        ev = ev.filter(pl.col("wp_after").is_not_null())
        sign = pl.when(pl.col("side") == "T").then(1.0).otherwise(-1.0)
        change = pl.col("wp_after") - pl.col("wp_before")
        if drift is None:
            return ev.with_columns((change * sign).alias("dwp")).drop("_s", "_last", "_out")
        ev = _drift_keys(ev, t, "_s").join(drift.select("map", "_planted", "_bucket", "drift_T"),
                                           on=["map", "_planted", "_bucket"], how="left")
        ev = ev.with_columns(((change - pl.col("drift_T").fill_null(0.0)) * sign).alias("dwp"))
        return ev.drop("_s", "_last", "_out", "map", "_planted", "_bucket", "drift_T")

    ev = pl.concat([attach(f) for f in _event_frames(t)], how="diagonal_relaxed")
    # a death is the victim's own ΔWP from their team's view (negative of the kill swing)
    return ev.filter(pl.col("dwp").is_not_nan())


def player_wpa(ev: pl.DataFrame, rounds_played: pl.DataFrame) -> pl.DataFrame:
    """Per player (and team, when ``rounds_played`` has one) and side: WPA per round, split into
    kills (+ deaths) and utility. Keying by team keeps a player who changed teams on a map from
    carrying one team's actions into the other team's profile."""
    keys = ["steamid", "team", "side"] if "team" in rounds_played.columns and "team" in ev.columns else ["steamid", "side"]
    g = ev.filter(pl.col("action") != "plant").group_by(*keys).agg(
        pl.col("dwp").filter(pl.col("action").is_in(["kill", "death"])).sum().alias("wpa_duels"),
        pl.col("dwp").filter(pl.col("action") == "utility").sum().alias("wpa_utility"),
        pl.col("dwp").sum().alias("wpa_total"),
    )
    g = g.join(rounds_played, on=keys, how="left")
    return g.with_columns(
        *[(pl.col(c) / pl.col("rounds")).round(4).alias(f"{c}_per_round") for c in ("wpa_duels", "wpa_utility", "wpa_total")])


def round_timelines(d: pl.DataFrame, wp_t: np.ndarray, demo_ids: set[str]) -> dict[str, dict]:
    """WP_T per second for the given demos: {demo_id: {round_num: [wp, ...]}}."""
    s = d.select("demo_id", "round_num", "t_s").with_columns(pl.Series("wp", wp_t)).filter(pl.col("demo_id").is_in(list(demo_ids)))
    out: dict[str, dict] = {}
    for (demo, rnd), g in s.group_by(["demo_id", "round_num"], maintain_order=True):
        out.setdefault(demo, {})[str(rnd)] = [round(float(v), 2) for v in g.sort("t_s")["wp"]]
    return out


def is_finite(x: float) -> bool:
    return x is not None and not math.isnan(x)


def recipe_wp(plans: pl.DataFrame, wp: pl.DataFrame, before_s: float = 5.0, after_s: float = 10.0,
              rounds: pl.DataFrame | None = None) -> dict[str, dict]:
    """For each execute recipe: mean T win probability 5 s before the commit, 10 s after, and the change.

    Rounds that end within 10 s of the commit take the outcome (from ``rounds``) as the state after;
    without ``rounds`` they fall back to the last sampled state."""
    hit = plans.filter(pl.col("recipe_id").is_not_null() & pl.col("commit_s").is_not_null()).select(
        "demo_id", "round_num", "recipe_id", "commit_s")
    w = wp.with_columns(pl.col("t_s").cast(pl.Int64).alias("_s")).drop("t_s")
    hit = hit.with_columns((pl.col("commit_s") - before_s).floor().cast(pl.Int64).clip(0, None).alias("_b"),
                           (pl.col("commit_s") + after_s).floor().cast(pl.Int64).alias("_a"))
    hit = hit.join(w.rename({"_s": "_b", "wp_t": "wp_before"}), on=["demo_id", "round_num", "_b"], how="inner")
    hit = hit.join(w.rename({"_s": "_a", "wp_t": "wp_after"}), on=["demo_id", "round_num", "_a"], how="left")
    last = w.group_by("demo_id", "round_num").agg(pl.col("wp_t").sort_by("_s").last().alias("wp_last"))
    hit = hit.join(last, on=["demo_id", "round_num"], how="left")
    if rounds is not None and {"winner_side"} <= set(rounds.columns):
        out = rounds.select("demo_id", "round_num", (pl.col("winner_side") == "T").cast(pl.Float64).alias("_out"))
        hit = hit.join(out, on=["demo_id", "round_num"], how="left").with_columns(
            pl.col("wp_after").fill_null(pl.col("_out")))
    hit = hit.with_columns(pl.col("wp_after").fill_null(pl.col("wp_last")))
    g = hit.group_by("recipe_id").agg(pl.len().alias("n"), pl.col("wp_before").mean(), pl.col("wp_after").mean())
    return {rid: {"n": int(n), "before": round(float(b), 3), "after": round(float(a), 3), "delta": round(float(a - b), 3)}
            for rid, n, b, a in g.iter_rows()}


def run(t: dict[str, pl.DataFrame]) -> dict | None:
    """Fit once over all maps; returns states, out-of-fold WP, events and metrics (None without scikit-learn)."""
    try:
        import sklearn  # noqa: F401
    except ImportError:
        print("win probability skipped: scikit-learn is not installed (uv pip install scikit-learn)")
        return None
    need = {"positions": {"health", "lane", "alive", "t_s", "side"}, "rounds": {"winner_side", "dur_s"},
            "economy": {"equipment_value", "n_players"}, "plants": {"t_s", "site"}, "kills": {"t_s"},
            "utility": {"pop_t_s", "type"}, "matches": {"map"}}
    missing = [f"{k}.{c}" for k, cols in need.items() for c in cols if k not in t or c not in t[k].columns]
    if missing:
        print(f"win probability skipped: missing {', '.join(missing[:4])}")
        return None
    d = states(t)
    if d["demo_id"].n_unique() < N_FOLDS or d["t_win"].n_unique() < 2:
        print("win probability skipped: not enough matches")
        return None
    artifacts = []
    oof, metrics = fit_oof(d, model_artifacts=artifacts)
    wp = wp_lookup(d, oof)
    return {"states": d, "oof": oof, "wp": wp, "events": action_values(t, wp), "metrics": metrics, "model_artifacts": artifacts}
