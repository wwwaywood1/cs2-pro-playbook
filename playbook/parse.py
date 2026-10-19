"""Step 2: one .dem file -> normalized tables (polars DataFrames).

Every table carries ``demo_id`` and ``round_num`` so many demos can be stacked.
Knife rounds are dropped. Teams are identified by canonical clan name (see
``config/team_aliases.csv``); sides are taken *per round* from the players'
team number at freeze end, never from awpy's "last observed side".

Tables produced
---------------
matches     one row per demo (map, teams, final score, build)
players     steamid -> name, team
rounds      round timing, winner, score before the round, which team is CT / T
economy     buy type and equipment value per (round, team)
loadouts    each player's gear at freeze end
positions   every player every second of live round time, with callout/region/lane
kills       kills with round time, both players' teams/sides/callouts, opening flag
plants      bomb plants with site (A/B) and round time
utility     every grenade: thrower, release position + view angles, landing point
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path

import awpy
import polars as pl
from awpy import Demo

from playbook.config import MapMeta, canonical_team, load_map, load_team_aliases
from playbook.utility import PlaceIndex, attribute_grenades

SIDE = {"terrorist": "T", "counter-terrorist": "CT"}
TEAM_NUM_SIDE = {2: "T", 3: "CT"}
SAMPLE_SECONDS = 1


def demo_identity(path: Path) -> dict:
    """``<hltv_match_id>_<team1>-vs-<team2>-<map>.dem`` (fetch.py naming) -> ids."""
    stem = path.stem
    m = re.match(r"^(\d+)_(.+)$", stem)
    return {"demo_id": stem, "hltv_match_id": int(m[1]) if m else None}


def half_of(round_num: int, max_rounds: int = 24, ot_max_rounds: int = 6) -> int:
    """1/2 for regulation halves, 3, 4, ... for overtime halves."""
    if round_num <= max_rounds:
        return 1 if round_num <= max_rounds // 2 else 2
    return 3 + (round_num - max_rounds - 1) // max(ot_max_rounds // 2, 1)


def _assign_round(df: pl.DataFrame, tick_col: str, bounds: pl.DataFrame) -> pl.DataFrame:
    """Attach round_num / freeze_end / end ticks to rows by tick (rows outside any round are dropped)."""
    return (
        df.with_columns(pl.col(tick_col).cast(pl.Int64))
        .sort(tick_col)
        .join_asof(bounds, left_on=tick_col, right_on="start_tick", strategy="backward")
        .filter(pl.col("round_num").is_not_null() & (pl.col(tick_col) <= pl.col("official_end_tick")))
    )


def _site_from_place(place: str | None, mm: MapMeta) -> str | None:
    # Every map names its sites BombsiteA / BombsiteB, so this works before a map config exists.
    if place in ("BombsiteA", "BombsiteB"):
        return place[-1]
    lane = mm.lane(place)
    return lane if lane in ("A", "B") else None


def parse_demo(path: Path, aliases: dict[str, str] | None = None, verbose: bool = True) -> dict[str, pl.DataFrame]:
    t_start = time.time()
    path = Path(path)
    aliases = load_team_aliases() if aliases is None else aliases
    ident = demo_identity(path)
    demo_id = ident["demo_id"]

    demo = Demo(path)
    demo.load("rounds", "kills", "bomb", "grenades", "smokes", "players", "round_economy", "shots")
    header = demo.header
    map_name = header["map_name"]
    mm = load_map(map_name)
    rate = demo.tick_rate
    step = int(round(rate * SAMPLE_SECONDS))
    convars = demo.convars
    max_rounds = int(convars.get("mp_maxrounds", 24))
    ot_max = int(convars.get("mp_overtime_maxrounds", 6))

    rounds = (
        demo.rounds.filter(~pl.col("is_knife_round") & pl.col("freeze_end_tick").is_not_null())
        .sort("round_num")
        .with_columns(pl.col(c).cast(pl.Int64) for c in ("start_tick", "freeze_end_tick", "end_tick", "official_end_tick"))
    )
    bounds = rounds.select("round_num", "start_tick", "freeze_end_tick", "end_tick", "official_end_tick").sort("start_tick")

    # ---- every tick: position + callout (fast; parallel pawn decode) -------------
    tk = (
        demo.ticks(["X", "Y", "Z", "health", "team_num", "m_szLastPlaceName"], players_only=True)
        .rename({"X": "x", "Y": "y", "Z": "z", "m_szLastPlaceName": "place"})
        .filter(pl.col("team_num").is_in([2, 3]))
        .with_columns(pl.col("tick").cast(pl.Int64))
    )
    pidx = PlaceIndex.from_frame(tk.filter(pl.col("place") != ""))

    # ---- teams --------------------------------------------------------------------
    roster = demo.players.filter(pl.col("side").is_in(list(SIDE)))
    names = dict(roster.select("steamid", "name").iter_rows())
    team_of: dict[int, str] = {}
    for sid, clan in roster.select("steamid", "team_clan_name").iter_rows():
        team = canonical_team(clan, aliases)
        if team:
            team_of[sid] = team
    # Fallback for demos without clan names: label by the side a player starts on.
    first_fe = rounds["freeze_end_tick"][0]
    start_side = dict(tk.filter(pl.col("tick") == first_fe).select("steamid", "team_num").iter_rows())
    for sid, num in start_side.items():
        if sid not in team_of:
            team_of[sid] = f"{TEAM_NUM_SIDE.get(num, '?')}-start team"
            names.setdefault(sid, str(sid))

    # ---- positions sampled once per second of live round time -------------------
    samples = [
        (r["round_num"], r["freeze_end_tick"] + k * step, k * SAMPLE_SECONDS)
        for r in rounds.iter_rows(named=True)
        for k in range(int((r["end_tick"] - r["freeze_end_tick"]) // step) + 1)
    ]
    sample_df = pl.DataFrame(samples, schema={"round_num": pl.Int32, "tick": pl.Int64, "t_s": pl.Int32}, orient="row")
    positions = (
        sample_df.join(tk, on="tick", how="inner")
        .with_columns(
            side=pl.col("team_num").replace_strict(TEAM_NUM_SIDE, default=None, return_dtype=pl.Utf8),
            team=pl.col("steamid").replace_strict(team_of, default=None, return_dtype=pl.Utf8),
            name=pl.col("steamid").replace_strict(names, default=None, return_dtype=pl.Utf8),
            region=pl.col("place").replace_strict(mm.callout_region, default="OTHER", return_dtype=pl.Utf8),
            alive=pl.col("health") > 0,
        )
        .with_columns(lane=pl.col("region").replace_strict(mm.region_lane, default="OTHER", return_dtype=pl.Utf8))
        .select(
            pl.lit(demo_id).alias("demo_id"), "round_num", "t_s", "tick", "steamid", "name", "team", "side",
            "x", "y", "z", "place", "region", "lane", "health", "alive",
        )
        .sort("round_num", "t_s", "steamid")
    )

    # ---- which team is CT / T each round; winner; score before the round --------
    side_by_round = (
        positions.filter(pl.col("t_s") == 0)
        .group_by("round_num", "side")
        .agg(team=pl.col("team").mode().first())
    )
    ct_t = side_by_round.pivot(on="side", index="round_num", values="team").rename({"CT": "ct_team", "T": "t_team"})
    rounds_out = (
        rounds.join(ct_t, on="round_num", how="left")
        .with_columns(
            winner_side=pl.col("winner_side").replace_strict(SIDE, default=None, return_dtype=pl.Utf8),
            dur_s=((pl.col("end_tick") - pl.col("freeze_end_tick")) / rate).round(1),
        )
        .with_columns(
            winner_team=pl.when(pl.col("winner_side") == "CT").then("ct_team").when(pl.col("winner_side") == "T").then("t_team"),
            half=pl.col("round_num").map_elements(lambda r: half_of(r, max_rounds, ot_max), return_dtype=pl.Int32),
        )
    )
    score: dict[str, int] = {}
    ct_before, t_before = [], []
    for r in rounds_out.iter_rows(named=True):
        ct_before.append(score.get(r["ct_team"], 0))
        t_before.append(score.get(r["t_team"], 0))
        if r["winner_team"]:
            score[r["winner_team"]] = score.get(r["winner_team"], 0) + 1
    rounds_out = rounds_out.with_columns(
        score_ct_before=pl.Series(ct_before, dtype=pl.Int32), score_t_before=pl.Series(t_before, dtype=pl.Int32)
    ).select(
        pl.lit(demo_id).alias("demo_id"), "round_num", "half", "start_tick", "freeze_end_tick", "end_tick",
        "official_end_tick", "dur_s", "ct_team", "t_team", "winner_side", "winner_team",
        pl.col("reason_name").alias("reason"), "score_ct_before", "score_t_before",
    )

    # ---- economy & loadouts ----------------------------------------------------------
    sbr = side_by_round.with_columns(pl.col("round_num").cast(pl.Int32))
    economy = (
        demo.round_economy.with_columns(
            side=pl.col("side").replace_strict(SIDE, default=None, return_dtype=pl.Utf8),
            round_num=pl.col("round_num").cast(pl.Int32),
        )
        .join(sbr, on=["round_num", "side"], how="inner")
        .select(pl.lit(demo_id).alias("demo_id"), "round_num", "team", "side", "buy_type", "equipment_value", "n_players")
    )
    snap = demo.snapshots(ticks=[int(t) for t in rounds["freeze_end_tick"].to_list()])
    fe_round = dict(zip(rounds["freeze_end_tick"].to_list(), rounds["round_num"].to_list()))
    loadouts = (
        snap.with_columns(pl.col("tick").cast(pl.Int64))
        .filter(pl.col("side").is_in(list(SIDE)))
        .with_columns(
            round_num=pl.col("tick").replace_strict(fe_round, default=None, return_dtype=pl.Int32),
            side=pl.col("side").replace_strict(SIDE, return_dtype=pl.Utf8),
            team=pl.col("steamid").replace_strict(team_of, default=None, return_dtype=pl.Utf8),
            primary_weapon=pl.col("primary_weapon").str.replace("^weapon_", ""),
            secondary_weapon=pl.col("secondary_weapon").str.replace("^weapon_", ""),
        )
        .select(
            pl.lit(demo_id).alias("demo_id"), "round_num", "steamid", "name", "team", "side", "primary_weapon",
            "secondary_weapon", "armor", "has_helmet", "has_defuser", "has_bomb", "smoke_grenades", "flashbangs",
            "he_grenades", "fire_grenades", "money", "equipment_value",
        )
    )

    # ---- kills ------------------------------------------------------------------------
    kills = _assign_round(demo.kills, "tick", bounds)
    a_place = pidx.query(kills["attacker_x"].fill_null(0), kills["attacker_y"].fill_null(0), kills["attacker_z"].fill_null(0))
    v_place = pidx.query(kills["victim_x"], kills["victim_y"], kills["victim_z"])
    kills = (
        kills.with_columns(
            attacker_place=pl.Series(a_place, dtype=pl.Utf8),
            victim_place=pl.Series(v_place, dtype=pl.Utf8),
            t_s=((pl.col("tick") - pl.col("freeze_end_tick")) / rate).round(2),
            is_post_round=pl.col("tick") > pl.col("end_tick"),
            attacker_side=pl.col("attacker_side").replace_strict(SIDE, default=None, return_dtype=pl.Utf8),
            victim_side=pl.col("victim_side").replace_strict(SIDE, default=None, return_dtype=pl.Utf8),
            attacker_team=pl.col("attacker_steamid").replace_strict(team_of, default=None, return_dtype=pl.Utf8),
            victim_team=pl.col("victim_steamid").replace_strict(team_of, default=None, return_dtype=pl.Utf8),
        )
        .with_columns(
            attacker_place=pl.when(pl.col("attacker_steamid").is_null()).then(None).otherwise("attacker_place"),
            is_teamkill=pl.col("attacker_team") == pl.col("victim_team"),
        )
        .with_columns(
            attacker_region=pl.col("attacker_place").replace_strict(mm.callout_region, default="OTHER", return_dtype=pl.Utf8),
            victim_region=pl.col("victim_place").replace_strict(mm.callout_region, default="OTHER", return_dtype=pl.Utf8),
        )
    )
    duel = pl.col("attacker_team").is_not_null() & ~pl.col("is_teamkill").fill_null(True) & ~pl.col("is_post_round")
    kills = kills.with_columns(
        is_opening=duel & (pl.col("tick") == pl.col("tick").filter(duel).min().over("round_num"))
    ).select(
        pl.lit(demo_id).alias("demo_id"), "round_num", "tick", "t_s", "is_post_round", "is_opening",
        "attacker_steamid", "attacker_name", "attacker_team", "attacker_side", "attacker_place", "attacker_region",
        "attacker_x", "attacker_y", "attacker_z",
        "victim_steamid", "victim_name", "victim_team", "victim_side", "victim_place", "victim_region",
        "victim_x", "victim_y", "victim_z",
        "assister_steamid", "weapon", "headshot", "assist_flash", "thrusmoke", "is_trade", "victim_traded", "is_teamkill",
    )

    # ---- bomb plants (site from the planter's callout) ----------------------------------
    plants = _assign_round(demo.bomb.filter(pl.col("event") == "finish_plant"), "tick", bounds)
    plant_place = pidx.query(plants["x"], plants["y"], plants["z"]) if plants.height else []
    plants = plants.with_columns(place=pl.Series(plant_place, dtype=pl.Utf8)).with_columns(
        site=pl.col("place").map_elements(lambda p: _site_from_place(p, mm), return_dtype=pl.Utf8),
        t_s=((pl.col("tick") - pl.col("freeze_end_tick")) / rate).round(2),
        team=pl.col("steamid").replace_strict(team_of, default=None, return_dtype=pl.Utf8),
    ).select(pl.lit(demo_id).alias("demo_id"), "round_num", "tick", "t_s", "steamid", "name", "team", "site", "place", "x", "y", "z")

    # ---- utility ------------------------------------------------------------------------
    util = _assign_round(attribute_grenades(demo.grenades, demo.shots, demo.smokes), "throw_tick", bounds)
    if util.height:
        throw_place = pidx.query(util["throw_x"], util["throw_y"], util["throw_z"])
        land_place = pidx.query(util["land_x"], util["land_y"], util["land_z"])
    else:
        throw_place, land_place = [], []
    util = util.with_columns(
        throw_place=pl.Series(throw_place, dtype=pl.Utf8),
        land_place=pl.Series(land_place, dtype=pl.Utf8),
        throw_t_s=((pl.col("throw_tick") - pl.col("freeze_end_tick")) / rate).round(2),
        pop_t_s=((pl.col("pop_tick").cast(pl.Int64) - pl.col("freeze_end_tick")) / rate).round(2),
        is_post_round=pl.col("throw_tick") > pl.col("end_tick"),
        thrower_team=pl.col("thrower_steamid").replace_strict(team_of, default=None, return_dtype=pl.Utf8),
    ).with_columns(
        thrower_name=pl.coalesce("thrower_name", pl.col("thrower_steamid").replace_strict(names, default=None, return_dtype=pl.Utf8)),
        land_region=pl.col("land_place").replace_strict(mm.callout_region, default="OTHER", return_dtype=pl.Utf8),
        round_num=pl.col("round_num").cast(pl.Int32),
    ).with_columns(
        land_lane=pl.col("land_region").replace_strict(mm.region_lane, default="OTHER", return_dtype=pl.Utf8)
    ).join(
        sbr.rename({"side": "thrower_side", "team": "thrower_team"}), on=["round_num", "thrower_team"], how="left"
    )

    # Movement state at release (jump-throw / crouch / walk) for the lineup library.
    throw_ticks = sorted({int(t) for t in util.filter(pl.col("matched"))["throw_tick"].to_list()})
    if throw_ticks:
        mv = demo.snapshots(ticks=throw_ticks).select(
            pl.col("tick").cast(pl.Int64).alias("throw_tick"),
            pl.col("steamid").alias("thrower_steamid"),
            "is_jumping", "is_crouched", "is_walking", pl.col("velocity").alias("throw_speed"),
        )
        util = util.join(mv, on=["throw_tick", "thrower_steamid"], how="left")
    else:
        util = util.with_columns(is_jumping=None, is_crouched=None, is_walking=None, throw_speed=None)
    util = util.select(
        pl.lit(demo_id).alias("demo_id"), "round_num", "nade_id", "type", "throw_tick", "throw_t_s", "pop_tick", "pop_t_s",
        "is_post_round", "thrower_steamid", "thrower_name", "thrower_team", "thrower_side",
        "throw_x", "throw_y", "throw_z", "throw_place", "pitch", "yaw", "is_jumping", "is_crouched", "is_walking", "throw_speed",
        "land_x", "land_y", "land_z", "land_place", "land_region", "land_lane", "matched", "match_dist",
    )

    # ---- match + players -------------------------------------------------------------------
    teams = sorted({t for t in team_of.values()})
    final = {t: score.get(t, 0) for t in teams}
    team_a, team_b = (teams + [None, None])[:2]
    matches = pl.DataFrame(
        [{
            "demo_id": demo_id,
            "hltv_match_id": ident["hltv_match_id"],
            "map": map_name,
            "team_a": team_a,
            "team_b": team_b,
            "score_a": final.get(team_a, 0),
            "score_b": final.get(team_b, 0),
            "winner": max(final, key=final.get) if final else None,
            "n_rounds": rounds_out.height,
            "tick_rate": rate,
            "build_num": header.get("build_num"),
            "server_name": header.get("server_name"),
            "demo_file": path.name,
            "awpy_version": getattr(awpy, "__version__", None),
            "parsed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }]
    )
    players = pl.DataFrame(
        [{"demo_id": demo_id, "steamid": sid, "name": names.get(sid), "team": team} for sid, team in team_of.items()],
        schema={"demo_id": pl.Utf8, "steamid": pl.UInt64, "name": pl.Utf8, "team": pl.Utf8},
    )

    if verbose:
        n_unmatched = util.filter(~pl.col("matched")).height
        print(
            f"  {demo_id}: {map_name} {team_a} {final.get(team_a)}-{final.get(team_b)} {team_b} | "
            f"{rounds_out.height} rounds, {kills.height} kills, {plants.height} plants, "
            f"{util.height} grenades ({n_unmatched} without thrower) | {time.time() - t_start:.1f}s"
        )

    return {
        "matches": matches,
        "players": players,
        "rounds": rounds_out,
        "economy": economy,
        "loadouts": loadouts,
        "positions": positions,
        "kills": kills,
        "plants": plants,
        "utility": util,
    }


def list_callouts(path: Path) -> pl.DataFrame:
    """Every callout name in a demo with its median position (to write config/maps/<map>.toml)."""
    demo = Demo(path)
    tk = demo.ticks(["X", "Y", "Z", "m_szLastPlaceName"], players_only=True).filter(pl.col("m_szLastPlaceName") != "")
    return (
        tk.group_by(pl.col("m_szLastPlaceName").alias("callout"))
        .agg(samples=pl.len(), x=pl.col("X").median().round(0), y=pl.col("Y").median().round(0), z=pl.col("Z").median().round(0))
        .sort("x")
        .with_columns(pl.lit(demo.header["map_name"]).alias("map"))
    )
