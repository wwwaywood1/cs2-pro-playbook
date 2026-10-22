"""Per-player summaries on top of the cleaned heatmap frames.

These are the structured base that tactic analysis and teaching material build on:
where a player plays in each phase, the spots he holds, where he fights, and where his
utility lands (linked to the landing spots and lineups of the lineup library).
Spatial summaries use playbook.heatmap.clean_frames: gun rounds of his team only,
living time only, no spawn walk-out, no post-round. Combat rates use all played
rounds for the same map/team/player/side and do not require spatial coordinates.

zones     callouts by share of living seconds, per phase (top ZONES_TOP, >= ZONES_MIN_SHARE)
main_lane the lane he spends most of each phase in, with its share
holds     clusters of "holding" seconds (moving < 40 u/s) within HOLD_RADIUS units:
          seconds per round, share of his holding time, rounds held there, typical time
fights    all-round combat rates/opening duels; spatial callouts remain gun-round only
utility   grenades per round by type; landing spots he uses most (with the lineups he
          throws them from)
"""

from __future__ import annotations

import math
from collections import Counter

import polars as pl

from playbook.config import MapMeta
from playbook.metrics import combat_totals
from playbook.tactics import density_clusters

ZONES_TOP = 5
ZONES_MIN_SHARE = 0.05
HOLD_RADIUS = 150.0
HOLD_MIN_SHARE = 0.03
HOLD_TOP = 4
HOLD_MIN_SECONDS_PR = 0.5
FIGHT_TOP = 5
UTIL_TOP = 8
PHASES = ("early", "mid", "post")
KEYS = ["demo_id", "round_num"]


def _r(x, nd=3):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def _zones(p: pl.DataFrame) -> tuple[dict, dict]:
    zones, main_lane = {}, {}
    for ph in PHASES:
        d = p.filter(pl.col("phase") == ph)
        if d.is_empty():
            continue
        n = d.height
        top = d.group_by("place", "region", "lane").agg(s=pl.len()).sort("s", "place", descending=[True, False])
        zones[ph] = [{"place": pl_, "region": rg, "lane": ln, "share": _r(s / n)}
                     for pl_, rg, ln, s in top.iter_rows() if s / n >= ZONES_MIN_SHARE][:ZONES_TOP]
        lane = d.group_by("lane").agg(s=pl.len()).sort("s", "lane", descending=[True, False]).row(0)
        main_lane[ph] = {"lane": lane[0], "share": _r(lane[1] / n)}
    return zones, main_lane


def _holds(p: pl.DataFrame, rounds: int) -> list[dict]:
    h = p.filter(pl.col("holding")).sort(*KEYS, "t_s")
    if h.height < 5:
        return []
    labels = density_clusters(h.select("x", "y", "z").to_numpy(), HOLD_RADIUS,
                              max(4, math.ceil(HOLD_MIN_SHARE * h.height)), h["level"].to_numpy())
    h = h.with_columns(_cl=pl.Series(labels)).filter(pl.col("_cl") >= 0)
    out = []
    for (_,), g in h.group_by("_cl", maintain_order=True):
        per_round_held = g.group_by(KEYS).agg(s=pl.len())
        out.append({
            "place": Counter(g["place"].to_list()).most_common(1)[0][0],
            "lane": Counter(g["lane"].to_list()).most_common(1)[0][0],
            "x": _r(g["x"].mean(), 1), "y": _r(g["y"].mean(), 1), "z": _r(g["z"].mean(), 1),
            "radar_x": _r(g["radar_x"].mean(), 1), "radar_y": _r(g["radar_y"].mean(), 1),
            "level": int(Counter(g["level"].to_list()).most_common(1)[0][0]),
            "seconds_per_round": _r(g.height / rounds, 2),
            "share_of_holding": _r(g.height / max(1, int(p["holding"].sum()))),
            "rounds_held": int((per_round_held["s"] >= 2).sum()),
            "median_t_s": _r(g["t_s"].median(), 0),
            "phases": {ph: _r((g["phase"] == ph).mean()) for ph in PHASES},
        })
    out = [o for o in out if (o["seconds_per_round"] or 0) >= HOLD_MIN_SECONDS_PR]
    out.sort(key=lambda o: (-o["seconds_per_round"], o["place"] or "", o["level"], o["radar_x"], o["radar_y"]))
    return out[:HOLD_TOP]


def _fights(k: pl.DataFrame, d: pl.DataFrame, played: pl.DataFrame) -> dict:
    by = (
        pl.concat([k.select("place", kills=pl.lit(1), deaths=pl.lit(0)), d.select("place", kills=pl.lit(0), deaths=pl.lit(1))])
        .filter(pl.col("place").is_not_null())
        .group_by("place").agg(pl.col("kills").sum(), pl.col("deaths").sum())
        .with_columns(n=pl.col("kills") + pl.col("deaths")).sort("n", "place", descending=[True, False])
    )
    combat = combat_totals(played)
    n = combat["rounds"]
    return {
        "rounds": n, "kills": combat["kills"], "kills_pr": combat["kpr"],
        "deaths_pr": _r(played["died"].sum() / n) if n else None,
        "opening_kills": int(played["opening_kill"].fill_null(False).sum()),
        "opening_deaths": int(played["opening_death"].fill_null(False).sum()),
        "places_gun_rounds_only": True,
        "places": [{"place": p, "kills": int(a), "deaths": int(b)} for p, a, b, _ in by.head(FIGHT_TOP).iter_rows()],
    }


def make_summarizer(mm: MapMeta, spots: pl.DataFrame | None = None, spot_assign: pl.DataFrame | None = None,
                    nade_lineup: pl.DataFrame | None = None):
    """Returns summarize(frames, team, steamid, side, rounds) for build_heatmaps."""
    spot_info = {r["spot_id"]: r for r in spots.iter_rows(named=True)} if spots is not None else {}

    def summarize(frames: dict[str, pl.DataFrame], team: str, steamid: int, side: str, rounds: int) -> dict:
        def mine(name: str) -> pl.DataFrame:
            f = frames[name]
            return f.filter((pl.col("team") == team) & (pl.col("steamid") == steamid) & (pl.col("side") == side))

        p = mine("presence")
        zones, main_lane = _zones(p)
        u = mine("utility")
        util = {"per_round": {t: _r((u["layer"] == t).sum() / rounds) for t in ("smoke", "flash", "molotov", "he")},
                "spots": []}
        if spot_assign is not None and not u.is_empty():
            j = u.join(spot_assign, on=["demo_id", "nade_id"], how="left")
            if nade_lineup is not None:
                j = j.join(nade_lineup, on=["demo_id", "nade_id"], how="left")
            else:
                j = j.with_columns(lineup_id=pl.lit(None, dtype=pl.Utf8))
            for (sid,), g in j.filter(pl.col("spot_id").is_not_null()).group_by("spot_id", maintain_order=True):
                s = spot_info.get(sid, {})
                lineups = sorted(Counter(x for x in g["lineup_id"].to_list() if x).items(), key=lambda kv: (-kv[1], kv[0]))[:2]
                util["spots"].append({
                    "spot_id": sid, "type": s.get("type"), "place": s.get("place"), "label": s.get("label"),
                    "radar_x": _r(s.get("radar_x"), 1), "radar_y": _r(s.get("radar_y"), 1),
                    "level": int(s.get("z", 0) < mm.radar["lower_level_max_z"]) if "lower_level_max_z" in mm.radar else 0,
                    "n": g.height, "per_round": _r(g.height / rounds),
                    "median_t_s": _r(g["throw_t_s"].median(), 0),
                    "lineups": [{"lineup_id": lid, "n": n} for lid, n in lineups],
                })
            util["spots"].sort(key=lambda x: (-x["n"], x["spot_id"]))
            util["spots"] = util["spots"][:UTIL_TOP]
            util["unclustered"] = int(j["spot_id"].is_null().sum())
        return {
            "rounds": rounds,
            "zones": zones,
            "main_lane": main_lane,
            "holds": _holds(p, rounds),
            "fights": _fights(mine("kills"), mine("deaths"), mine("player_rounds")),
            "utility": util,
        }

    return summarize


def team_setup(entry: dict) -> dict:
    """Per side and phase: which roster players are mainly on which lane, e.g.
    {'CT': {'early': {'A': ['x', 'y'], 'MID': ['z'], 'B': [...]}}}."""
    out: dict = {}
    names = {r["steamid"]: r["name"] for r in entry["roster"]}
    for sid, by_side in entry["summary"].items():
        for side, s in by_side.items():
            for ph, ml in s["main_lane"].items():
                out.setdefault(side, {}).setdefault(ph, {}).setdefault(ml["lane"], []).append(names.get(sid))
    return out
