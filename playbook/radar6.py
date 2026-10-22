"""Six descriptive player axes, map/side peer percentiles. See DESIGN.md."""
from __future__ import annotations

from collections import defaultdict
import math

import numpy as np
import polars as pl

KEYS = ["demo_id", "round_num"]
AXES = ("entry", "trade", "lurk_distance", "space_gain", "utility_impact", "clutch_wpa")
MIN_ROUNDS = 50
MOLOTOV_RADIUS = 120.0  # same world-unit radius as the replay overlay


def _finite(value):
    return value is not None and math.isfinite(float(value))


def _round(value):
    return round(float(value), 4) if _finite(value) else None


def percentile(value: float | None, peers: list[float]) -> float | None:
    """Midrank empirical percentile; a tied/constant population is centred at 50."""
    if value is None or not peers:
        return None
    return round(100 * (sum(v < value for v in peers) + .5 * sum(v == value for v in peers)) / len(peers), 1)


def player_radar(sub: dict[str, pl.DataFrame], wp: pl.DataFrame | None = None) -> dict:
    pr = sub["player_rounds"].unique(subset=[*KEYS, "steamid"])
    if pr.is_empty():
        return {}
    rounds = {k: g for k, g in pr.group_by(KEYS)}
    end = sub["rounds"].select(*KEYS, "dur_s")
    pos = sub["positions"].join(end, on=KEYS).filter(
        pl.col("alive") & (pl.col("t_s") >= 0) & (pl.col("t_s") <= pl.col("dur_s"))
        & pl.col("x").is_finite() & pl.col("y").is_finite())
    # Each player's last living point minus first living point, measured toward enemy spawn.
    spawn = {s: (g["x"].mean(), g["y"].mean()) for (s,), g in pos.filter(
        pl.col("t_s") == 0).group_by("side")}
    stats = defaultdict(lambda: defaultdict(float))
    samples = defaultdict(lambda: defaultdict(list))
    for (demo, rnd, sid, side), g in pos.sort("t_s").group_by(*KEYS, "steamid", "side", maintain_order=True):
        enemy = spawn.get("CT" if side == "T" else "T")
        if enemy:
            x0, y0 = g.select("x", "y").row(0)
            x1, y1 = g.select("x", "y").row(-1)
            stats[(sid, side)]["advance"] += math.hypot(x0 - enemy[0], y0 - enemy[1]) - math.hypot(x1 - enemy[0], y1 - enemy[1])
            stats[(sid, side)]["advance_rounds"] += 1
    # Leave-one-out alive teammate centroid, equally weighted living seconds before plant.
    plants = sub["plants"].group_by(KEYS).agg(plant_s=pl.col("t_s").min())
    lp = pos.filter((pl.col("side") == "T") & (pl.col("t_s") > 15)).join(plants, on=KEYS, how="left").filter(
        pl.col("plant_s").is_null() | (pl.col("t_s") < pl.col("plant_s")))
    cent = lp.group_by(*KEYS, "team", "t_s").agg(sx=pl.col("x").sum(), sy=pl.col("y").sum(), n=pl.len())
    lp = lp.join(cent, on=[*KEYS, "team", "t_s"]).filter(pl.col("n") > 1).with_columns(
        dist=(pl.col("x") - (pl.col("sx") - pl.col("x")) / (pl.col("n") - 1)).abs()
             + (pl.col("y") - (pl.col("sy") - pl.col("y")) / (pl.col("n") - 1)).abs())
    for (sid,), g in lp.group_by("steamid"):
        samples[(sid, "T")]["lurk_distance"] = g["dist"].to_list()
    wp_rounds = {k: dict(g.select("t_s", "wp_t").iter_rows()) for k, g in wp.group_by(KEYS)} if wp is not None else {}
    pos_rounds = {k: g for k, g in pos.group_by(KEYS)}
    kill_rounds = {k: g.sort("t_s", "tick") if "tick" in g.columns else g.sort("t_s")
                   for k, g in sub["kills"].filter(~pl.col("is_post_round") & (pl.col("t_s") >= 0)).group_by(KEYS)}
    util_rounds = {k: g for k, g in sub["utility"].filter(~pl.col("is_post_round")).group_by(KEYS)}
    for key, roster in rounds.items():
        people = {r["steamid"]: r for r in roster.iter_rows(named=True)}
        kills = kill_rounds[key].to_dicts() if key in kill_rounds else []
        enemy_kills = [k for k in kills if k.get("attacker_side") in ("T", "CT")
                       and k.get("victim_side") in ("T", "CT") and k["attacker_side"] != k["victim_side"]]
        if enemy_kills:
            for sid in {enemy_kills[0]["attacker_steamid"], enemy_kills[0]["victim_steamid"]}:
                if sid in people:
                    stats[(sid, people[sid]["side"])]["openings"] += 1
        for death in enemy_kills:
            victim = death["victim_steamid"]
            side = death["victim_side"]
            teammates = [sid for sid, r in people.items() if r["side"] == side and sid != victim]
            for sid in teammates:
                stats[(sid, side)]["teammate_deaths"] += 1
            stats[(victim, side)]["deaths"] += 1
            revenge = next((k for k in enemy_kills if 0 < k["t_s"] - death["t_s"] <= 4
                            and k["victim_steamid"] == death["attacker_steamid"]
                            and k["attacker_steamid"] in teammates), None)
            if revenge:
                stats[(victim, side)]["traded_deaths"] += 1
                stats[(revenge["attacker_steamid"], side)]["traded_teammate_deaths"] += 1
        for kill in enemy_kills:
            sid = kill.get("assister_steamid")
            if kill.get("assist_flash") and sid in people and people[sid]["side"] == kill["attacker_side"]:
                stats[(sid, people[sid]["side"])]["flash_assists"] += 1
        frames = pos_rounds.get(key)
        if frames is None:
            continue
        by_second = {t: g for (t,), g in frames.group_by("t_s")}
        # A side can enter 1vN once: sample the first observed state with exactly one alive.
        seen = set()
        for t in sorted(by_second):
            g = by_second[t]
            for side in ("T", "CT"):
                own = g.filter(pl.col("side") == side)
                enemies = g.filter(pl.col("side") != side)
                if side in seen or own.height != 1 or enemies.is_empty():
                    continue
                seen.add(side)
                p = wp_rounds.get(key, {}).get(t)
                sid = own["steamid"][0]
                if p is not None and sid in people:
                    probability = p if side == "T" else 1 - p
                    samples[(sid, side)]["clutch_wpa"].append(float(people[sid]["won"]) - probability)
        if key not in util_rounds:
            continue
        tracks = {sid: g for (sid,), g in frames.group_by("steamid")}
        for util in util_rounds[key].iter_rows(named=True):
            sid, pop = util["thrower_steamid"], util.get("pop_t_s")
            if util["type"] not in ("molotov", "incendiary") or sid not in people or not _finite(pop):
                continue
            if not all(_finite(util.get(c)) for c in ("land_x", "land_y", "land_z")):
                continue
            initial = by_second.get(int(math.floor(pop + .5)))
            if initial is None:
                continue
            for enemy in initial.filter(pl.col("side") != people[sid]["side"]).iter_rows(named=True):
                # Avoid counting a player on another floor as inside the fire.
                if abs(enemy["z"] - util["land_z"]) > 120 or math.hypot(enemy["x"] - util["land_x"], enemy["y"] - util["land_y"]) > MOLOTOV_RADIUS:
                    continue
                later = tracks[enemy["steamid"]].filter((pl.col("t_s") > pop) & (pl.col("t_s") <= pop + 3.5))
                if any(math.hypot(x - enemy["x"], y - enemy["y"]) > 150 for x, y in later.select("x", "y").iter_rows()):
                    stats[(sid, people[sid]["side"])]["molotov_displacements"] += 1
    result = {}
    for (sid, side), g in pr.group_by("steamid", "side"):
        n = g.height
        s, observations = stats[(sid, side)], samples[(sid, side)]
        saved = s["traded_deaths"] / s["deaths"] if s["deaths"] else None
        traded = s["traded_teammate_deaths"] / s["teammate_deaths"] if s["teammate_deaths"] else None
        components = [v for v in (saved, traded) if v is not None]
        raw = {"entry": s["openings"] / n, "trade": float(np.mean(components)) if components else None,
               "lurk_distance": float(np.mean(observations["lurk_distance"])) if observations["lurk_distance"] else None,
               "space_gain": s["advance"] / n if s["advance_rounds"] else None,
               "utility_impact": (s["flash_assists"] + s["molotov_displacements"]) / n,
               "clutch_wpa": float(np.mean(observations["clutch_wpa"])) if observations["clutch_wpa"] else None}
        result[(str(sid), side)] = {"rounds": n, "eligible": n >= MIN_ROUNDS,
            **{axis: {"raw": _round(raw[axis]), "percentile": None} for axis in AXES},
            "trade_components": {"own_deaths_traded_rate": _round(saved), "teammate_deaths_traded_rate": _round(traded)},
            "utility_counts": {"flash_assists": int(s["flash_assists"]), "molotov_displacements": int(s["molotov_displacements"])},
            "clutch_situations": len(observations["clutch_wpa"]),
            "clutch_wpa_sum": _round(sum(observations["clutch_wpa"])) if observations["clutch_wpa"] else None}
    for (_, side), profile in result.items():
        for axis in AXES:
            peers = [p[axis]["raw"] for (_, s), p in result.items() if s == side and p["eligible"] and p[axis]["raw"] is not None]
            profile[axis]["reference_players"] = len(peers)
            if profile["eligible"]:
                profile[axis]["percentile"] = percentile(profile[axis]["raw"], peers)
    return result
