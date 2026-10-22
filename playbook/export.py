"""Step 4 (MVP): aggregate parsed tables into the static JSON the website reads.

Output layout (schema documented in DESIGN.md, section "Site data contract"):

    data/site/index.json                      maps, teams, generation time
    data/site/<map>/meta.json                 radar transform, region/lane mapping
    data/site/<map>/teams.json                one summary row per team
    data/site/<map>/teams/<team-slug>.json    full team profile
    data/site/<map>/players.json              player profiles with role hints
    data/site/<map>/lineups.json              lineup library (clustered grenades)
    data/site/heatmap_teams.json              heatmap entry: team -> maps, fixed player colours
    data/site/<map>/heatmaps/                 baseline.json, teams/<slug>.json (players, grids, summaries)

Everything is computed from data, not written by hand. Numbers carry their sample
size; anything from fewer than MIN_MATCHES_RELIABLE matches is flagged low_sample.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from playbook.config import PARSED_DIR, SITE_DIR, MapMeta, load_map, team_slug
from playbook.heatmap import build_heatmaps, roster_order
from playbook.config import ROOT, load_spot_names
from playbook.tactics import DEFINITIONS, analyse_map, ct_summary, name_spots, site_spots, t_summary
from playbook.insights import attach_summaries, team_insights
from playbook.zones import make_summarizer, team_setup
from playbook.store import read_all
from playbook.semantics import round_plants
from playbook.dedupe import deduplicate_tables, demo_events, hltv_demo_ids
from playbook import winprob

SCHEMA_VERSION = 1
MIN_MATCHES_RELIABLE = 5
GUN_BUYS = ("full", "force")  # setups / executes are summarised on gun rounds only
LINEUP_TYPES = ("smoke", "flashbang", "molotov", "he")
LINEUP_MIN_THROWS = 2
LINEUP_THROW_RADIUS = 48.0  # same lineup if thrown within this distance ...
LINEUP_LAND_RADIUS = 120.0  # ... and landing within this distance
MOVING_SPEED = 100.0
ACTIVE_POOL = {"de_mirage", "de_inferno", "de_nuke", "de_dust2", "de_ancient", "de_anubis", "de_cache"}  # Overpass left
AWP_ANY = 0.4        # role hint thresholds, see _add_role_hints and DESIGN.md › Role hints
AWP_TEAM_TOP = 0.15


def _r(x, nd: int = 3):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), nd)


def _rate(won: int, n: int):
    return _r(won / n) if n else None


def _top_counts(df: pl.DataFrame, col: str, k: int = 6) -> list[dict]:
    """Most common values of `col` with rounds / won / win rate."""
    if df.is_empty():
        return []
    g = (
        df.filter(pl.col(col).is_not_null())
        .group_by(col)
        .agg(rounds=pl.len(), won=pl.col("won").sum())
        .sort("rounds", col, descending=[True, False])
        .head(k)
    )
    total = df.height
    return [
        {"value": v, "rounds": n, "share": _rate(n, total), "won": w, "win_rate": _rate(w, n)}
        for v, n, w in g.iter_rows()
    ]


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def _write_compact(path: Path, obj) -> None:
    """Large numeric files (heatmaps): no indentation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


# --------------------------------------------------------------------------- teams


def _side_summary(d: pl.DataFrame, side: str) -> dict:
    n = d.height
    gun = d.filter(pl.col("buy_type").is_in(GUN_BUYS))
    out = {
        "rounds": n,
        "won": int(d["won"].sum()),
        "win_rate": _rate(int(d["won"].sum()), n),
        "gun_rounds": gun.height,
        "opening_win_rate": _rate(int(d["opening_won"].fill_null(False).sum()), d["opening_won"].drop_nulls().len()),
        "avg_first_kill_s": _r(d["first_kill_s"].mean(), 1),
        "avg_util_per_round": _r((d["n_smokes"] + d["n_flashes"] + d["n_molotovs"] + d["n_he"]).mean(), 2),
        "avg_early_util": _r(gun["n_early_util"].mean(), 2) if gun.height else None,
        "setups_15s": _top_counts(gun, "shape_15s"),
        "setups_30s": _top_counts(gun, "shape_30s"),
    }
    if side == "T":
        site = d.with_columns(site=pl.col("plant_site").fill_null("none"))
        out["plant_sites"] = _top_counts(site, "site", k=3)
        out["avg_plant_t_s"] = _r(d["plant_t_s"].mean(), 1)
        ex = gun.with_columns(
            exec_timing=pl.when(pl.col("exec_n_util") < 3).then(pl.lit("no_clear_execute"))
            .when(pl.col("exec_start_s") < 35).then(pl.lit("fast"))
            .when(pl.col("exec_start_s") < 65).then(pl.lit("default_then_execute"))
            .otherwise(pl.lit("late")),
            exec_lane=pl.when(pl.col("exec_n_util") >= 3).then("exec_lane"),
        )
        out["execute_timing"] = _top_counts(ex, "exec_timing", k=4)
        out["execute_lane"] = _top_counts(ex, "exec_lane", k=3)
        out["avg_execute_start_s"] = _r(ex.filter(pl.col("exec_n_util") >= 3)["exec_start_s"].mean(), 1)
    else:
        planted = d.filter(pl.col("planted"))
        out["plants_against"] = planted.height
        out["retakes_won"] = int(planted["won"].sum())
        out["retake_win_rate"] = _rate(int(planted["won"].sum()), planted.height)
        out["plants_against_by_site"] = _top_counts(planted, "plant_site", k=2)

        def stacked(shape: str | None) -> bool:
            if not shape:
                return False
            return any(p[0] in "AB" and int(p[1:]) >= 3 for p in shape.split())

        out["stack_rate_15s"] = _rate(sum(stacked(s) for s in gun["shape_15s"].to_list()), gun.height)
    return out


def team_profiles(sub: dict[str, pl.DataFrame], mm: MapMeta) -> list[dict]:
    tr = sub["team_rounds"]
    matches = sub["matches"]
    profiles = []
    for team in sorted(tr["team"].drop_nulls().unique().to_list()):
        d = tr.filter(pl.col("team") == team)
        demo_ids = d["demo_id"].unique().to_list()
        m = matches.filter(pl.col("demo_id").is_in(demo_ids))
        match_list = []
        for row in m.sort("demo_id").iter_rows(named=True):
            me_a = row["team_a"] == team
            match_list.append({
                "demo_id": row["demo_id"],
                "hltv_match_id": row["hltv_match_id"],
                "opponent": row["team_b"] if me_a else row["team_a"],
                "score_for": row["score_a"] if me_a else row["score_b"],
                "score_against": row["score_b"] if me_a else row["score_a"],
                "event": row.get("event"),
            })
        eco = (
            d.group_by("side", "buy_type").agg(rounds=pl.len(), won=pl.col("won").sum()).sort("side", "buy_type")
        )
        profiles.append({
            "team": team,
            "slug": team_slug(team),
            "map": mm.name,
            "n_matches": len(demo_ids),
            "low_sample": len(demo_ids) < MIN_MATCHES_RELIABLE,
            "matches": match_list,
            "sides": {s: _side_summary(d.filter(pl.col("side") == s), s) for s in ("T", "CT")},
            "economy": [
                {"side": s, "buy_type": b, "rounds": n, "won": w, "win_rate": _rate(w, n)}
                for s, b, n, w in eco.iter_rows()
            ],
        })
    return profiles


# ------------------------------------------------------------------------- players


def _lane_dist(values: list[str | None]) -> list[dict]:
    vals = [v for v in values if v]
    c = Counter(vals)
    return [{"value": k, "share": _rate(n, len(vals))} for k, n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:4]]


def player_profiles(sub: dict[str, pl.DataFrame]) -> list[dict]:
    pr = sub["player_rounds"]
    out = []
    for sid, d in pr.group_by("steamid"):
        sid = sid[0]
        n = d.height
        t = d.filter(pl.col("side") == "T")
        ct = d.filter(pl.col("side") == "CT")
        t_reached = t.filter(pl.col("site_entry_rank").is_not_null())
        out.append({
            "steamid": str(sid),
            "name": d["name"].mode().sort().first(),
            "team": d["team"].mode().sort().first(),
            "n_matches": d["demo_id"].n_unique(),
            "rounds": {"total": n, "T": t.height, "CT": ct.height},
            "kpr": _rate(int(d["kills"].sum()), n),
            "dpr": _rate(int(d["died"].sum()), n),
            "hs_pct": _rate(int(d["hs_kills"].sum()), int(d["kills"].sum())),
            "opening_kills_pr": _rate(int(d["opening_kill"].sum()), n),
            "opening_deaths_pr": _rate(int(d["opening_death"].sum()), n),
            "opening_success": _rate(int(d["opening_kill"].sum()), int(d["opening_kill"].sum() + d["opening_death"].sum())),
            "traded_death_rate": _rate(int(d["death_traded"].sum()), int(d["died"].sum())),
            "awp_share": _rate(int(d["is_awp"].sum()), n),
            "util_pr": _rate(int(d["util_thrown"].sum()), n),
            "T": {
                "avg_dist_to_team_30s": _r(t["dist_to_team_30s"].mean(), 0),
                "first_into_site_rate": _rate(int((t_reached["site_entry_rank"] == 1).sum()), t_reached.height),
                "lanes_15s": _lane_dist(t["lane_15s"].to_list()),
                "places_30s": _lane_dist(t["place_30s"].to_list()),
            },
            "CT": {
                "lanes_15s": _lane_dist(ct["lane_15s"].to_list()),
                "places_30s": _lane_dist(ct["place_30s"].to_list()),
            },
        })
    out.sort(key=lambda p: p["steamid"])  # deterministic tie-breaks in the role hints
    _add_role_hints(out)
    return sorted(out, key=lambda p: (p["team"] or "", p["name"] or ""))


def _add_role_hints(players: list[dict]) -> None:
    """Heuristic role labels, each with the metric that triggered it.

    Relative to teammates on the same map, so a team always gets at most one of
    lurker / entry / support. These are hints for the UI, not ground truth; tune
    the thresholds once a labelled validation set exists (see DESIGN.md).
    """
    by_team: dict[str, list[dict]] = {}
    for p in players:
        p["role_hints"] = []
        by_team.setdefault(p["team"], []).append(p)

    def best(team: list[dict], key) -> dict | None:
        vals = [(key(p), p) for p in team if key(p) is not None]
        return max(vals, key=lambda x: x[0])[1] if vals else None

    for team in by_team.values():
        top_awp = max((p["awp_share"] or 0) for p in team) if team else 0
        for p in team:
            a = p["awp_share"] or 0
            # Tuned on the GPT-05 role table (validation/pro_roles.csv): the team's main AWP
            # user from 15% of rounds, or anyone from 40%: 49/50 AWPers, no false positives.
            if a >= AWP_ANY or (a == top_awp and a >= AWP_TEAM_TOP):
                p["role_hints"].append({"role": "awper", "metric": "awp_share", "value": p["awp_share"]})
            ct_lanes = p["CT"]["lanes_15s"]
            if ct_lanes and (ct_lanes[0]["share"] or 0) >= 0.6:
                lane = ct_lanes[0]["value"]
                role = {"A": "a_anchor", "B": "b_anchor", "MID": "mid_ct"}.get(lane)
                if role:
                    p["role_hints"].append({"role": role, "metric": "ct_lane_15s_share", "value": ct_lanes[0]["share"]})

        dists = sorted(d for p in team if (d := p["T"]["avg_dist_to_team_30s"]) is not None)
        median = dists[len(dists) // 2] if dists else None
        lurker = best(team, lambda p: p["T"]["avg_dist_to_team_30s"])
        if lurker and median and lurker["T"]["avg_dist_to_team_30s"] >= 1.25 * median:
            lurker["role_hints"].append({
                "role": "lurker", "metric": "t_avg_dist_to_team_30s",
                "value": lurker["T"]["avg_dist_to_team_30s"], "team_median": median,
            })
        entry = best(team, lambda p: p["T"]["first_into_site_rate"])
        if entry and (entry["T"]["first_into_site_rate"] or 0) >= 0.25:
            entry["role_hints"].append({"role": "entry", "metric": "t_first_into_site_rate", "value": entry["T"]["first_into_site_rate"]})
        support = best(team, lambda p: p["util_pr"])
        if support:
            support["role_hints"].append({"role": "support", "metric": "util_pr", "value": support["util_pr"]})


# ------------------------------------------------------------------------- lineups


def _technique(jump, crouch, walk, speed) -> str:
    if jump:
        return "jump"
    if speed is not None and speed >= MOVING_SPEED:
        return "run"
    if crouch:
        return "crouch"
    if walk:
        return "walk"
    return "stand"


def build_lineups(sub: dict[str, pl.DataFrame], mm: MapMeta) -> tuple[list[dict], pl.DataFrame]:
    """Exportable lineups and the complete (demo_id, nade_id) -> lineup_id mapping.

    Singleton clusters still participate in analysis; only their exported records
    and links are omitted.
    """
    u = sub["utility"].filter(
        pl.col("matched") & ~pl.col("is_post_round") & pl.col("thrower_side").is_not_null()
        & pl.col("type").is_in(LINEUP_TYPES)
    )
    won = sub["team_rounds"].select("demo_id", "round_num", pl.col("team").alias("thrower_team"), "won")
    u = u.join(won, on=["demo_id", "round_num", "thrower_team"], how="left").sort("throw_tick", "demo_id", "nade_id")
    rows = u.to_dicts()

    # Greedy clustering: same side + type, close release point and close landing point.
    clusters: list[dict] = []
    for r in rows:
        for c in clusters:
            if c["side"] != r["thrower_side"] or c["type"] != r["type"]:
                continue
            if math.dist((c["tx"], c["ty"]), (r["throw_x"], r["throw_y"])) > LINEUP_THROW_RADIUS:
                continue
            if math.dist((c["lx"], c["ly"]), (r["land_x"], r["land_y"])) > LINEUP_LAND_RADIUS:
                continue
            c["members"].append(r)
            k = len(c["members"])
            c["tx"] += (r["throw_x"] - c["tx"]) / k
            c["ty"] += (r["throw_y"] - c["ty"]) / k
            c["lx"] += (r["land_x"] - c["lx"]) / k
            c["ly"] += (r["land_y"] - c["ly"]) / k
            break
        else:
            clusters.append({"side": r["thrower_side"], "type": r["type"], "tx": r["throw_x"], "ty": r["throw_y"],
                             "lx": r["land_x"], "ly": r["land_y"], "members": [r]})

    out = []
    for c in clusters:
        ms = c["members"]
        rep = min(ms, key=lambda m: math.dist((m["throw_x"], m["throw_y"]), (c["tx"], c["ty"]))
                  + math.dist((m["land_x"], m["land_y"]), (c["lx"], c["ly"])))
        land_place = Counter(m["land_place"] for m in ms if m["land_place"]).most_common(1)
        throw_place = Counter(m["throw_place"] for m in ms if m["throw_place"]).most_common(1)
        n_won = sum(1 for m in ms if m["won"])
        tx, ty = mm.to_radar(rep["throw_x"], rep["throw_y"])
        lx, ly = mm.to_radar(rep["land_x"], rep["land_y"])
        pops = sorted(m["pop_t_s"] for m in ms if m["pop_t_s"] is not None)
        out.append({
            "side": c["side"],
            "type": c["type"],
            "throw_place": throw_place[0][0] if throw_place else None,
            "land_place": land_place[0][0] if land_place else None,
            "land_region": mm.region(land_place[0][0]) if land_place else None,
            "land_lane": mm.lane(land_place[0][0]) if land_place else None,
            "n_throws": len(ms),
            "n_matches": len({m["demo_id"] for m in ms}),
            "teams": sorted({m["thrower_team"] for m in ms if m["thrower_team"]}),
            "throwers": [n for n, _ in Counter(m["thrower_name"] for m in ms).most_common(3)],
            "round_win_rate": _rate(n_won, len(ms)),
            "median_pop_t_s": _r(pops[len(pops) // 2], 1) if pops else None,
            "technique": _technique(rep["is_jumping"], rep["is_crouched"], rep["is_walking"], rep["throw_speed"]),
            "jump_share": _rate(sum(1 for m in ms if m["is_jumping"]), len(ms)),
            "throw": {"x": _r(rep["throw_x"], 2), "y": _r(rep["throw_y"], 2), "z": _r(rep["throw_z"], 2),
                      "pitch": _r(rep["pitch"], 2), "yaw": _r(rep["yaw"], 2),
                      "radar_x": _r(tx, 1), "radar_y": _r(ty, 1)},
            "land": {"x": _r(rep["land_x"], 1), "y": _r(rep["land_y"], 1), "z": _r(rep["land_z"], 1),
                     "radar_x": _r(lx, 1), "radar_y": _r(ly, 1)},
            # Paste into the console on a practice server (sv_cheats 1) to stand on the release spot.
            "practice_cmd": f"setpos {rep['throw_x']:.2f} {rep['throw_y']:.2f} {rep['throw_z']:.2f};"
                            f"setang {rep['pitch']:.2f} {rep['yaw']:.2f} 0",
            "example": {"demo_id": rep["demo_id"], "round_num": rep["round_num"], "throw_tick": rep["throw_tick"]},
            "_members": [(m["demo_id"], m["nade_id"]) for m in ms],
        })
    out.sort(key=lambda l: (-l["n_throws"], -(l["n_matches"]), l["side"], l["type"]))
    pairs = []
    for i, l in enumerate(out):
        l["id"] = f"{mm.name}-{l['side'].lower()}-{l['type']}-{i:04d}"
        pairs.extend((d, n, l["id"]) for d, n in l.pop("_members"))
    nade_lineup = pl.DataFrame(pairs, schema={"demo_id": pl.Utf8, "nade_id": pl.UInt32, "lineup_id": pl.Utf8}, orient="row")
    return [l for l in out if l["n_throws"] >= LINEUP_MIN_THROWS], nade_lineup


def _filter_lineup_refs(spots: list[dict], lineup_ids: set[str]) -> None:
    """Keep only links to the exported library, preserving spot statistics."""
    for spot in spots:
        spot["lineups"] = [l for l in spot["lineups"] if l["lineup_id"] in lineup_ids]


def team_hub_map_stats(profile: dict) -> dict:
    """Keep map wins distinct from round wins and heatmap gun-round samples."""
    sides = profile["sides"]
    rounds = sum(sides[s]["rounds"] for s in ("T", "CT"))
    won = sum(sides[s]["won"] for s in ("T", "CT"))
    matches = profile["matches"]
    return {
        "map_win_rate": _rate(sum(m["score_for"] > m["score_against"] for m in matches), len(matches)),
        "round_win_rate": _rate(won, rounds),
        "win_rate_T": sides["T"]["win_rate"],
        "win_rate_CT": sides["CT"]["win_rate"],
        "all_rounds": rounds,
        "low_sample": profile["low_sample"],
        # Source IDs are ordering hints, not match dates; the UI labels this explicitly.
        "results": sorted(matches, key=lambda m: (m.get("hltv_match_id") or 0, m["demo_id"]), reverse=True)[:5],
    }


def export_player_quotes(source: Path, out_dir: Path) -> None:
    """Owner-supplied text only; a missing optional file exports an empty registry."""
    quotes = json.loads(source.read_text(encoding="utf-8")) if source.exists() else {}
    if not isinstance(quotes, dict) or any(
        not isinstance(value, dict) or any(not isinstance(value.get(key, ""), str) for key in ("name", "zh", "en"))
        for value in quotes.values()
    ):
        raise ValueError(f"{source}: expected steamid -> {{name, zh, en}} text entries")
    _write(out_dir / "player_quotes.json", quotes)


def export_asset_slots(public_dir: Path, out_dir: Path) -> None:
    """Only request supplied PNG slots, avoiding a 404 for every placeholder card."""
    _write(out_dir / "asset_slots.json", {
        "teams": sorted(p.stem for p in (public_dir / "logos" / "teams").glob("*.png") if p.is_file()),
        "players": sorted(p.stem for p in (public_dir / "players").glob("*.png") if p.is_file()),
    })


# ------------------------------------------------------------------------- tactics


def _add_team_tactics(mdir: Path, teams: list[dict], res: dict, names: dict) -> None:
    """Write each team profile with its M2 tactics block (T plans, CT setups)."""
    for p in teams:
        p["tactics"] = {
            "T": t_summary(res["plans"].filter(pl.col("team") == p["team"])),
            "CT": ct_summary(res["ct"].filter(pl.col("team") == p["team"]), names),
        }
        _write(mdir / "teams" / f"{p['slug']}.json", p)


WPA_MIN_ROUNDS = 50  # sample needed to rank a player's WPA among peers
SHOWCASE_TEAMS = {"Falcons"}  # teams that get per-round WP timelines (files stay small)


def team_round_sides(team_rounds: pl.DataFrame, demo: str) -> dict[str, dict[str, str]]:
    """Actual per-round sides, including overtime; never infer sides from round numbers."""
    sides: dict[str, dict[str, str]] = {}
    for team, rnd, side in team_rounds.filter(pl.col("demo_id") == demo).select("team", "round_num", "side").iter_rows():
        sides.setdefault(team_slug(team), {})[str(rnd)] = side
    return sides


def map_card_summary(team_rounds: pl.DataFrame, recipes: list[dict]) -> dict:
    rates = {}
    for side in ("T", "CT"):
        rows = team_rounds.filter(pl.col("side") == side)
        rates[f"win_rate_{side}"] = _rate(int(rows["won"].sum()), rows.height)
    top = min(recipes, key=lambda recipe: (-recipe["n_rounds"], recipe["id"])) if recipes else None
    return {**rates, "top_recipe": {
        "id": top["id"],
        "name": {lang: " + ".join((spot.get("name") or {}).get(lang) or spot["label"] for spot in top["core"])
                 for lang in ("zh", "en")},
    } if top else None}


def _add_winprob(mdir: Path, ids: list[str], teams: list[dict], players: list[dict], res: dict,
                 sub: dict[str, pl.DataFrame], wpr: dict) -> None:
    """Win probability added per player and side, recipe WP swing, showcase-team timelines."""
    ev = wpr["events"].filter(pl.col("demo_id").is_in(ids))
    played = sub["player_rounds"].with_columns(pl.col("steamid").cast(pl.Utf8)).group_by("steamid", "side").agg(
        pl.len().alias("rounds"))
    rows = {(sid, side): r for sid, side, *r in winprob.player_wpa(ev, played).select(
        "steamid", "side", "rounds", "wpa_total_per_round", "wpa_duels_per_round", "wpa_utility_per_round").iter_rows()}
    # percentile among players of this map and side with a reliable sample
    pool = {side: sorted(v[1] for (sid, sd), v in rows.items() if sd == side and v[0] and v[0] >= WPA_MIN_ROUNDS)
            for side in ("T", "CT")}
    for p in players:
        for side in ("T", "CT"):
            r = rows.get((str(p["steamid"]), side))
            if r and r[0]:
                ref = pool[side]
                pct = (sum(1 for v in ref if v <= r[1]) / len(ref)) if (ref and r[0] >= WPA_MIN_ROUNDS) else None
                p[side]["wpa"] = {"rounds": int(r[0]), "per_round": r[1], "duels": r[2], "utility": r[3],
                                  "rounds_per_match": round(r[1] * 24, 2),
                                  "percentile": round(pct, 2) if pct is not None else None,
                                  "peers": len(ref)}
    wp_map = wpr["wp"].filter(pl.col("demo_id").is_in(ids))
    swing = winprob.recipe_wp(res["plans"], wp_map)
    for r in res["recipes"]:
        if r["id"] in swing:
            r["wp"] = swing[r["id"]]
    show = sub["matches"].filter(pl.col("team_a").is_in(list(SHOWCASE_TEAMS)) | pl.col("team_b").is_in(list(SHOWCASE_TEAMS)))
    keep = set(show["demo_id"].to_list())
    lines = {}
    if keep:
        mask = wpr["states"]["demo_id"].is_in(list(keep)).to_numpy()
        lines = winprob.round_timelines(wpr["states"].filter(mask), wpr["oof"][mask], keep)
        for demo, by_round in lines.items():
            _write_compact(mdir / "winprob" / f"{demo}.json", {"demo_id": demo, "wp_t": by_round,
                           "team_sides": team_round_sides(sub["team_rounds"], demo)})

    for team in teams:
        for match in team["matches"]:
            match["winprob_available"] = match["demo_id"] in lines


def _add_player_tactics(mdir: Path, players: list[dict], res: dict, player_rounds: pl.DataFrame) -> None:
    """Lurk share (T, rounds with a commit) and forward share (CT) per player, rewritten
    into players.json; inputs for the role hints."""
    hit = res["plans"].filter(pl.col("gun") & pl.col("commit_s").is_not_null())
    lurks = dict(hit.filter(pl.col("lurk")).group_by("lurker_steamid").agg(n=pl.len()).iter_rows())
    played = player_rounds.filter(pl.col("buy_type").is_in(GUN_BUYS)).select(
        "demo_id", "round_num", "team", "side", "steamid").unique()
    hit_rounds = dict(played.filter(pl.col("side") == "T").join(
        hit.select("demo_id", "round_num", "team"), on=["demo_id", "round_num", "team"], how="semi"
    ).group_by("steamid").agg(n=pl.len()).iter_rows())
    ct = res["ct"].filter(pl.col("gun"))
    fwd = dict(ct.select("forward_steamids").explode("forward_steamids").drop_nulls()
               .group_by("forward_steamids").agg(n=pl.len()).iter_rows())
    ct_rounds = dict(played.filter(pl.col("side") == "CT").group_by("steamid").agg(n=pl.len()).iter_rows())
    for p in players:
        sid = int(p["steamid"])
        th, cr = hit_rounds.get(sid, 0), ct_rounds.get(sid, 0)
        p["T"]["lurk_share"] = _rate(lurks.get(sid, 0), th) if th else None
        p["CT"]["forward_share"] = _rate(fwd.get(sid, 0), cr) if cr else None
    _write(mdir / "players.json", players)


# --------------------------------------------------------------------------- driver


def export_site(parsed_dir: Path = PARSED_DIR, out_dir: Path = SITE_DIR) -> None:
    t = read_all(parsed_dir)
    t, duplicates = deduplicate_tables(t, preferred_ids=hltv_demo_ids())
    print(f"deduplicated {len(duplicates)} duplicate demos")
    # Old semantic tables may contain a post-round plant; keep every exported view
    # consistent with the cleaned plant used by heatmaps and tactics.
    plants = round_plants(t)
    t["team_rounds"] = t["team_rounds"].drop("plant_site", "plant_t_s", "planted").join(
        plants, on=["demo_id", "round_num"], how="left", validate="m:1"
    ).with_columns(planted=pl.col("plant_site").is_not_null())
    events = demo_events()
    t["matches"] = t["matches"].with_columns(
        pl.col("demo_id").replace_strict(events, default=None, return_dtype=pl.Utf8).alias("event"))
    matches = t["matches"]
    index = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "min_matches_reliable": MIN_MATCHES_RELIABLE,
        "data_source": "Professional CS2 match demos (provenance per demo in matches; see DESIGN.md, Data sources)",
        "maps": [],
    }
    order = roster_order(t["player_rounds"])  # stable player colours across maps
    wpr = winprob.run(t)
    if wpr:
        m = wpr["metrics"]
        print(f"win probability: accuracy {m['model']['accuracy']:.3f} (baseline {m['baseline_alive_time']['accuracy']:.3f}),"
              f" log loss {m['model']['log_loss']:.3f}, {m['matches']} matches")
        _write(out_dir / "winprob_metrics.json", m)
    export_player_quotes(ROOT / "config" / "player_quotes.json", out_dir)
    export_asset_slots(ROOT / "web" / "public", out_dir)
    team_maps: dict[str, list[dict]] = {}
    for map_name in sorted(m for m in matches["map"].unique().to_list() if m in ACTIVE_POOL):
        mm = load_map(map_name)
        ids = matches.filter(pl.col("map") == map_name)["demo_id"].to_list()
        sub = {k: v.filter(pl.col("demo_id").is_in(ids)) for k, v in t.items() if "demo_id" in v.columns}
        teams = team_profiles(sub, mm)
        players = player_profiles(sub)
        lineups, nade_lineup = build_lineups(sub, mm)
        lineup_ids = {l["id"] for l in lineups}
        mdir = out_dir / map_name
        _write(mdir / "meta.json", {
            "map": map_name, "display_name": mm.display_name, "radar": mm.radar,
            "radar_image": f"https://github.com/pnxenopoulos/awpy-data/releases (radars/{map_name}.png)",
            "regions": mm.region_lane, "callouts": mm.callout_region,
        })
        _write(mdir / "teams.json", [
            {"team": p["team"], "slug": p["slug"], "n_matches": p["n_matches"], "low_sample": p["low_sample"],
             "win_rate_T": p["sides"]["T"]["win_rate"], "win_rate_CT": p["sides"]["CT"]["win_rate"]}
            for p in teams
        ])
        _write(mdir / "lineups.json", lineups)
        res = analyse_map(sub, mm, nade_lineup)
        spot_names = name_spots(res["spots"], load_spot_names(map_name))
        for r in res["recipes"]:
            _filter_lineup_refs(r["core"], lineup_ids)
            _filter_lineup_refs(r["options"], lineup_ids)
            for c in r["core"] + r["options"]:
                c["name"] = spot_names.get(c["spot_id"])
        names = {sid: n for sid, n in sub["player_rounds"].group_by("steamid").agg(pl.col("name").mode().sort().first()).iter_rows()}
        spots = site_spots(res, spot_names, mm)
        _filter_lineup_refs(spots, lineup_ids)
        if wpr:
            _add_winprob(mdir, ids, teams, players, res, sub, wpr)
        _write(mdir / "tactics.json", {
            "map": map_name, "definitions": DEFINITIONS,
            "t_overview": t_summary(res["plans"]), "ct_overview": ct_summary(res["ct"], names),
            "recipes": res["recipes"], "spots": spots,
        })
        for p in teams:
            p["insights"] = team_insights(p["team"], res["plans"], res["ct"], res["recipes"], spot_names)
        attach_summaries(teams, ROOT / "config" / "insight_text" / f"{map_name}.json")
        _add_team_tactics(mdir, teams, res, names)
        _add_player_tactics(mdir, players, res, sub["player_rounds"])
        hm = build_heatmaps(sub, mm, order, make_summarizer(mm, res["spots"], res["spot_assign"], nade_lineup))
        profiles_by_slug = {p["slug"]: p for p in teams}
        _write_compact(mdir / "heatmaps" / "baseline.json", hm["baseline"])
        for slug, entry in hm["teams"].items():
            for by_side in entry["summary"].values():
                for summary in by_side.values():
                    _filter_lineup_refs(summary["utility"]["spots"], lineup_ids)
            entry["setup"] = team_setup(entry)
            _write_compact(mdir / "heatmaps" / "teams" / f"{slug}.json", entry)
            team_maps.setdefault(entry["team"], []).append({
                "map": map_name, "display_name": mm.display_name, "n_matches": entry["n_matches"],
                "rounds": entry["rounds"], "players": [r["steamid"] for r in entry["roster"]],
                **(team_hub_map_stats(profiles_by_slug[slug]) if slug in profiles_by_slug else {}),
            })
        index["maps"].append({
            "map": map_name, "display_name": mm.display_name, "n_matches": len(ids),
            "teams": [p["slug"] for p in teams], "n_players": len(players), "n_lineups": len(lineups),
            "heatmaps": True,
            **map_card_summary(sub["team_rounds"], res["recipes"]),
        })
        print(f"  {map_name}: {len(ids)} matches, {len(teams)} teams, {len(players)} players, {len(lineups)} lineups")
    _write(out_dir / "index.json", index)
    _write(out_dir / "heatmap_teams.json", heatmap_team_index(t["player_rounds"], order, team_maps))
    print(f"site data -> {out_dir}")


def heatmap_team_index(player_rounds: pl.DataFrame, order: dict[str, list[str]],
                       team_maps: dict[str, list[dict]]) -> list[dict]:
    """Entry point of the heatmap pages: team -> maps (arrow order: most played first) and
    the team's players with their fixed colours (0 red, 1 blue, 2 purple, 3 green, 4 orange)."""
    names = (
        player_rounds.filter(pl.col("steamid").is_not_null() & pl.col("team").is_not_null())
        .group_by("team", "steamid").agg(name=pl.col("name").mode().sort().first(), rounds=pl.len())
    )
    out = []
    for team, maps in team_maps.items():
        info = {str(sid): (n, r) for sid, n, r in names.filter(pl.col("team") == team).select("steamid", "name", "rounds").iter_rows()}
        roster = [{"steamid": sid, "name": info.get(sid, (None, 0))[0], "color": i, "rounds": info.get(sid, (None, 0))[1]}
                  for i, sid in enumerate(order.get(team, []))]
        maps = sorted(maps, key=lambda m: (-m["n_matches"], m["map"]))
        out.append({"team": team, "slug": team_slug(team), "n_matches": sum(m["n_matches"] for m in maps),
                    "maps": maps, "roster": roster})
    return sorted(out, key=lambda e: (-e["n_matches"], e["team"].lower()))
