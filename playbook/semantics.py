"""Step 3: round semantics — turn raw per-demo tables into labelled rounds.

team_rounds   one row per (round, team): side, result, economy, opening duel,
              plant, utility usage, execute timing, lane "shapes" at 15/30/45s.
player_rounds one row per (round, player): weapon, where they were at 15/30s,
              how far from teammates, kills/deaths, opening involvement, site-entry
              order, utility thrown. These are the inputs for role/playstyle profiles.

Everything here is a pure function of the tables from parse.py, so it can be rerun
on stored parquet without touching demos.

Definitions (keep in sync with DESIGN.md):
- opening duel: the first kill of the round between the two teams, before round end.
- early utility: smokes+flashes+molotovs that pop in the first 15s (default
  map-control utility such as the T-spawn window smoke on Mirage).
- execute window: after those first 15s, the 10s window in which a team's
  smokes+flashes+molotovs *pop* most densely; its start is the "execute time", its
  dominant landing lane the "execute lane". Mainly meaningful on T side.
- shape@N: lanes of the team's living players N seconds after freeze end, e.g.
  "A2 M2 B1" (S = T spawn, C = CT spawn). A coarse setup fingerprint.
- site_entry_rank: on T side, order in which players first stood on a bombsite
  region (1 = first in). Null if the player never reached a site.
"""

from __future__ import annotations

from collections import Counter

import polars as pl

from playbook.config import LANE_ORDER, LANE_SHORT, MapMeta, load_map

EXEC_TYPES = ("smoke", "flashbang", "molotov")
EXEC_WINDOW_S = 10.0
EARLY_UTIL_S = 15.0
SHAPE_TIMES = (15, 30, 45)
SITE_REGIONS = ("A_SITE", "B_SITE")
KEYS = ["demo_id", "round_num"]


def lane_shape(lanes: list[str]) -> str | None:
    if not lanes:
        return None
    counts = Counter(lanes)
    order = LANE_ORDER + sorted(set(counts) - set(LANE_ORDER))
    return " ".join(f"{LANE_SHORT.get(lane, '?')}{counts[lane]}" for lane in order if counts.get(lane))


def densest_window(times: list[float], lanes: list[str], width: float = EXEC_WINDOW_S) -> tuple[int, float | None, str | None]:
    """(count, window start, dominant lane) of the densest `width`-second window."""
    pairs = sorted(zip(times, lanes))
    best: tuple[int, float | None, str | None] = (0, None, None)
    j = 0
    for i in range(len(pairs)):
        while pairs[i][0] - pairs[j][0] > width:
            j += 1
        n = i - j + 1
        if n > best[0]:
            lane = Counter(l for _, l in pairs[j : i + 1] if l not in (None, "OTHER")).most_common(1)
            best = (n, pairs[j][0], lane[0][0] if lane else None)
    return best


def round_plants(t: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """One first live plant per round, also when re-exporting older parsed tables."""
    bounds = t.get("rounds", t.get("team_rounds"))
    plants = t.get("plants")
    exact_bounds = False
    if plants is not None and all(c in plants.columns for c in (*KEYS, "t_s", "site")):
        if "tick" in plants.columns and bounds is not None and all(
                c in bounds.columns for c in ("freeze_end_tick", "end_tick")):
            plants = plants.join(bounds.select(*KEYS, "freeze_end_tick", "end_tick"), on=KEYS, validate="m:1").filter(
                pl.col("tick").is_between(pl.col("freeze_end_tick"), pl.col("end_tick")))
            exact_bounds = True
        p = plants.select(*KEYS, plant_site="site", plant_t_s="t_s",
                          _order="tick" if "tick" in plants.columns else "t_s")
    else:
        tr = t["team_rounds"].filter(pl.col("side") == "T")
        if "plant_site" not in tr.columns:
            tr = tr.with_columns(plant_site=pl.lit(None, dtype=pl.String))
        p = tr.select(*KEYS, "plant_site", "plant_t_s", _order="plant_t_s")
    p = p.filter(pl.col("plant_t_s").is_finite() & (pl.col("plant_t_s") >= 0))
    if not exact_bounds and bounds is not None and "dur_s" in bounds.columns:
        # dur_s is rounded to 0.1 s; plant_t_s to 0.01 s. Prefer tick bounds above.
        p = p.join(bounds.select(*KEYS, "dur_s").unique(), on=KEYS, validate="m:1").filter(
            pl.col("plant_t_s") <= pl.col("dur_s") + 0.05).drop("dur_s")
    return p.sort(*KEYS, "_order", "plant_site").group_by(KEYS, maintain_order=True).agg(
        pl.col("plant_site").first(), pl.col("plant_t_s").first())


def build_team_rounds(t: dict[str, pl.DataFrame]) -> pl.DataFrame:
    r = t["rounds"]
    common = ["demo_id", "round_num", "half", "dur_s", "reason", "winner_team"]
    base = pl.concat(
        [
            r.select(*common, team="ct_team", opponent="t_team", side=pl.lit("CT"),
                     score_for="score_ct_before", score_against="score_t_before"),
            r.select(*common, team="t_team", opponent="ct_team", side=pl.lit("T"),
                     score_for="score_t_before", score_against="score_ct_before"),
        ]
    ).with_columns(won=pl.col("team") == pl.col("winner_team")).drop("winner_team")

    eco = t["economy"].select(*KEYS, "team", "buy_type", "equipment_value")
    base = base.join(eco, on=[*KEYS, "team"], how="left").join(
        eco.rename({"team": "opponent", "buy_type": "opp_buy_type", "equipment_value": "opp_equipment_value"}),
        on=[*KEYS, "opponent"], how="left",
    )

    # kills / deaths / opening duel; deaths before freeze end (round restarts, pauses) don't count
    k_all = t["kills"].filter(~pl.col("is_post_round") & (pl.col("t_s") >= 0))
    k = k_all.filter(~pl.col("is_teamkill").fill_null(True))
    kills_for = k.group_by(*KEYS, team="attacker_team").agg(kills=pl.len())
    deaths = k_all.group_by(*KEYS, team="victim_team").agg(deaths=pl.len())
    opening = k.filter(pl.col("is_opening")).select(
        *KEYS, opening_team="attacker_team", first_kill_s="t_s",
        opening_kill_place="victim_place", opening_attacker_place="attacker_place",
    )
    base = (
        base.join(kills_for, on=[*KEYS, "team"], how="left")
        .join(deaths, on=[*KEYS, "team"], how="left")
        .join(opening, on=KEYS, how="left")
        .with_columns(
            pl.col("kills").fill_null(0),
            pl.col("deaths").fill_null(0),
            opening_won=pl.col("opening_team") == pl.col("team"),
        )
        .drop("opening_team")
    )

    # bomb plant (first plant of the round)
    plants = round_plants(t)
    base = base.join(plants, on=KEYS, how="left").with_columns(planted=pl.col("plant_site").is_not_null())

    # utility usage + execute window
    u = t["utility"].filter(~pl.col("is_post_round") & pl.col("thrower_team").is_not_null())
    util_counts = u.group_by(*KEYS, team="thrower_team").agg(
        n_smokes=(pl.col("type") == "smoke").sum(),
        n_flashes=(pl.col("type") == "flashbang").sum(),
        n_molotovs=(pl.col("type") == "molotov").sum(),
        n_he=(pl.col("type") == "he").sum(),
        n_early_util=(pl.col("type").is_in(EXEC_TYPES) & (pl.col("pop_t_s") < EARLY_UTIL_S)).sum(),
    )
    exec_rows = []
    ex = u.filter(pl.col("type").is_in(EXEC_TYPES) & (pl.col("pop_t_s") >= EARLY_UTIL_S))
    for (demo_id, rnd, team), grp in ex.group_by("demo_id", "round_num", "thrower_team"):
        n, start, lane = densest_window(grp["pop_t_s"].to_list(), grp["land_lane"].to_list())
        exec_rows.append({"demo_id": demo_id, "round_num": rnd, "team": team,
                          "exec_n_util": n, "exec_start_s": start, "exec_lane": lane})
    exec_df = pl.DataFrame(
        exec_rows,
        schema={"demo_id": pl.Utf8, "round_num": pl.Int32, "team": pl.Utf8,
                "exec_n_util": pl.Int64, "exec_start_s": pl.Float64, "exec_lane": pl.Utf8},
    )
    base = (
        base.join(util_counts, on=[*KEYS, "team"], how="left")
        .join(exec_df, on=[*KEYS, "team"], how="left")
        .with_columns(
            pl.col(c).fill_null(0) for c in ("n_smokes", "n_flashes", "n_molotovs", "n_he", "n_early_util", "exec_n_util")
        )
    )

    # lane shapes of living players at fixed times
    pos = t["positions"].filter(pl.col("alive") & pl.col("t_s").is_in(SHAPE_TIMES))
    shapes = (
        pos.group_by(*KEYS, "team", "t_s")
        .agg(lanes=pl.col("lane"))
        .with_columns(shape=pl.col("lanes").map_elements(lambda l: lane_shape(list(l)), return_dtype=pl.Utf8))
        .pivot(on="t_s", index=[*KEYS, "team"], values="shape")
    )
    shapes = shapes.rename({str(s): f"shape_{s}s" for s in SHAPE_TIMES if str(s) in shapes.columns})
    for s in SHAPE_TIMES:
        if f"shape_{s}s" not in shapes.columns:
            shapes = shapes.with_columns(pl.lit(None, dtype=pl.Utf8).alias(f"shape_{s}s"))
    base = base.join(shapes, on=[*KEYS, "team"], how="left")

    # AWP on the team at freeze end
    awp = t["loadouts"].group_by(*KEYS, "team").agg(has_awp=(pl.col("primary_weapon") == "awp").any())
    base = base.join(awp, on=[*KEYS, "team"], how="left")

    return base.sort(*KEYS, "side").select(
        "demo_id", "round_num", "half", "team", "opponent", "side", "won", "reason", "dur_s",
        "score_for", "score_against", "buy_type", "equipment_value", "opp_buy_type", "opp_equipment_value",
        "kills", "deaths", "first_kill_s", "opening_won", "opening_kill_place", "opening_attacker_place",
        "planted", "plant_site", "plant_t_s",
        "n_smokes", "n_flashes", "n_molotovs", "n_he", "n_early_util", "exec_n_util", "exec_start_s", "exec_lane",
        "shape_15s", "shape_30s", "shape_45s", "has_awp",
    )


def build_player_rounds(t: dict[str, pl.DataFrame], team_rounds: pl.DataFrame) -> pl.DataFrame:
    lo = t["loadouts"].filter(pl.col("steamid").is_not_null() & pl.col("team").is_not_null()).select(
        *KEYS, "steamid", "name", "team", "side", "primary_weapon")
    pos = t["positions"]

    def at(sec: int, cols: list[str]) -> pl.DataFrame:
        return pos.filter(pl.col("t_s") == sec).select(
            *KEYS, "steamid", *[pl.col(c).alias(f"{c}_{sec}s") for c in cols]
        )

    p15 = at(15, ["lane", "place", "alive"])
    p30 = at(30, ["lane", "region", "place", "alive"])

    # mean 2D distance to living teammates at 30s (high on T side = lurk tendency)
    a30 = pos.filter((pl.col("t_s") == 30) & pl.col("alive")).select(*KEYS, "team", "steamid", "x", "y")
    dist30 = (
        a30.join(a30, on=[*KEYS, "team"], suffix="_m")
        .filter(pl.col("steamid") != pl.col("steamid_m"))
        .group_by(*KEYS, "steamid")
        .agg(dist_to_team_30s=((pl.col("x") - pl.col("x_m")) ** 2 + (pl.col("y") - pl.col("y_m")) ** 2).sqrt().mean())
    )

    # order of first arrival on a bombsite (T side only)
    entry = (
        pos.filter(pl.col("alive") & (pl.col("side") == "T") & pl.col("region").is_in(SITE_REGIONS))
        .group_by(*KEYS, "team", "steamid")
        .agg(site_entry_s=pl.col("t_s").min())
        .with_columns(site_entry_rank=pl.col("site_entry_s").rank("min").over(*KEYS, "team").cast(pl.Int32))
        .drop("team")
    )

    k = t["kills"].filter(~pl.col("is_post_round") & (pl.col("t_s") >= 0))
    kills = k.filter(~pl.col("is_teamkill").fill_null(True)).group_by(*KEYS, steamid="attacker_steamid").agg(
        kills=pl.len(), hs_kills=pl.col("headshot").sum(), opening_kill=pl.col("is_opening").any(),
        trade_kills=pl.col("is_trade").sum(),
    )
    deaths = k.group_by(*KEYS, steamid="victim_steamid").agg(
        died=pl.lit(True), death_t_s=pl.col("t_s").min(), opening_death=pl.col("is_opening").any(),
        death_traded=pl.col("victim_traded").any(),
    )
    util = (
        t["utility"].filter(~pl.col("is_post_round"))
        .group_by(*KEYS, steamid="thrower_steamid")
        .agg(
            util_thrown=pl.len(),
            smokes=(pl.col("type") == "smoke").sum(),
            flashes=(pl.col("type") == "flashbang").sum(),
            molotovs=(pl.col("type") == "molotov").sum(),
            he=(pl.col("type") == "he").sum(),
        )
    )
    won = team_rounds.select(*KEYS, "team", "won", "buy_type")

    out = (
        lo.join(p15, on=[*KEYS, "steamid"], how="left")
        .join(p30, on=[*KEYS, "steamid"], how="left")
        .join(dist30, on=[*KEYS, "steamid"], how="left")
        .join(entry, on=[*KEYS, "steamid"], how="left")
        .join(kills, on=[*KEYS, "steamid"], how="left")
        .join(deaths, on=[*KEYS, "steamid"], how="left")
        .join(util, on=[*KEYS, "steamid"], how="left")
        .join(won, on=[*KEYS, "team"], how="left")
        .with_columns(
            pl.col("kills", "hs_kills", "trade_kills", "util_thrown", "smokes", "flashes", "molotovs", "he").fill_null(0),
            pl.col("opening_kill", "opening_death", "died", "death_traded").fill_null(False),
            is_awp=pl.col("primary_weapon") == "awp",
        )
    )
    return out.sort(*KEYS, "team", "steamid")


def _region(col: str, mm: MapMeta) -> pl.Expr:
    return pl.col(col).replace_strict(mm.callout_region, default="OTHER", return_dtype=pl.Utf8)


def _lane(region_col: str, mm: MapMeta) -> pl.Expr:
    return pl.col(region_col).replace_strict(mm.region_lane, default="OTHER", return_dtype=pl.Utf8)


def relabel(tables: dict[str, pl.DataFrame], mm: MapMeta | None = None) -> dict[str, pl.DataFrame]:
    """Recompute every region/lane column (and plant sites) from the stored callouts with the
    current map config. Run after editing config/maps/*.toml; the demo is not needed."""
    mm = mm or load_map(tables["matches"]["map"][0])
    out = dict(tables)
    out["positions"] = tables["positions"].with_columns(region=_region("place", mm)).with_columns(lane=_lane("region", mm))
    out["kills"] = tables["kills"].with_columns(
        attacker_region=_region("attacker_place", mm), victim_region=_region("victim_place", mm)
    )
    out["utility"] = tables["utility"].with_columns(land_region=_region("land_place", mm)).with_columns(
        land_lane=_lane("land_region", mm)
    )
    site_of = {c: mm.region_lane[r] for c, r in mm.callout_region.items() if mm.region_lane.get(r) in ("A", "B")}
    site_of.update({"BombsiteA": "A", "BombsiteB": "B"})
    out["plants"] = tables["plants"].with_columns(
        site=pl.col("place").replace_strict(site_of, default=None, return_dtype=pl.Utf8)
    )
    return out


def add_semantics(tables: dict[str, pl.DataFrame]) -> dict[str, pl.DataFrame]:
    tr = build_team_rounds(tables)
    return {**tables, "team_rounds": tr, "player_rounds": build_player_rounds(tables, tr)}
