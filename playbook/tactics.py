"""Step 5 (M2): tactic identification across all demos of one map.

Input: the parsed tables of one map (many demos). Output: per-round labels and two
map-level libraries. Everything is a pure function of the tables, so it reruns on
stored parquet. Definitions (keep in sync with DESIGN.md, "Tactic identification"):

Landing spots     utility of one side and type that lands in the same place, whatever
                  the throw position (for example the Mirage CT smoke on A). Clustering is
                  density seeded: the grenade with the most unassigned neighbours within
                  the radius becomes a centre and takes them; repeat. A spot needs
                  SPOT_MIN_THROWS throws from SPOT_MIN_MATCHES matches.
T plans           one row per T round.
  commit_s        first second with >= 2 living T players on the target's bombsite core
                  (the BombsiteA/BombsiteB callout, named the same on every map), or the
                  plant if that came first. target = plant site, else the first site hit.
  tempo           fast (commit <= 40 s), mid, late (commit >= 75 s), or no_hit.
  attempt         the target, or for no_hit rounds the lane of the densest execute
                  utility (>= 3 grenades in 10 s): failed executes still count for a site.
  execute         utility popping from 15 s before to 5 s after the commit, except what
                  lands on the other site's lane.
  split           attackers from two directions: their last positions before stepping onto
                  the site region (entries 15 s before to 10 s after the commit) are >= 400
                  units apart, or their bearings from the site centre 6 s before the commit
                  form two groups >= 50 degrees apart. Null for no_hit rounds.
  lurk            a living T player on the other site's lane, or >= 2200 units from the
                  target (not in T spawn), at the commit or 10 s before it.
  fake            >= 2 smokes/molotovs, or >= 3 grenades, landing near the other site
                  (within 1500 units of it and closer to it than to the target) between
                  30 s and 5 s before the commit (after the first 15 s).
Execute recipes   gun rounds hitting the same site with similar sets of smoke and molotov
                  spots, grouped by average-linkage clustering on Jaccard distance. Core
                  spots are those used in at least half of a recipe's rounds; each links to
                  the lineups (throw positions) that hit it.
CT setups         one row per CT round: lane shape at 20 s, forward players at 15 s (on
                  callouts the T side holds at 15 s in >= 60% of samples), stacks (>= 3 on
                  one site at 20 s), and rotations after the T commit.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import polars as pl

from playbook.config import MapMeta
from playbook.semantics import lane_shape, round_plants

KEYS = ["demo_id", "round_num"]
GUN_BUYS = ("full", "force")

SPOT_TYPES = ("smoke", "molotov", "flashbang", "he")
SPOT_RADIUS = {"smoke": 160.0, "molotov": 160.0, "flashbang": 260.0, "he": 260.0}
SPOT_MIN_THROWS = 4
SPOT_MIN_MATCHES = 2

SITE_CORE = {"A": "BombsiteA", "B": "BombsiteB"}
OTHER_SITE = {"A": "B", "B": "A"}
COMMIT_MIN_PLAYERS = 2
TEMPO_FAST_S = 40   # commit <= 40 s
TEMPO_LATE_S = 75   # commit >= 75 s (40 s or less on the clock)
EXEC_BEFORE_S = 15
EXEC_AFTER_S = 5
EARLY_UTIL_S = 15
FAKE_FROM_S, FAKE_TO_S = 30, 5
SPLIT_LOOKBACK_S = 6
SPLIT_MIN_ANGLE = 50.0
SPLIT_MIN_DIST, SPLIT_MAX_DIST = 400.0, 2500.0
SPLIT_ENTRY_WINDOW = (15, 10)  # entries from 15 s before to 10 s after the commit
SPLIT_ENTRY_DIST = 400.0
LURK_MIN_DIST = 2200.0
LURK_LOOKBACK_S = 10
FAKE_RADIUS = 1500.0
ATTEMPT_MIN_UTIL = 3

RECIPE_TYPES = ("smoke", "molotov")
RECIPE_MAX_DIST = 0.6
RECIPE_MIN_ROUNDS = 4
RECIPE_CORE_SHARE = 0.5
RECIPE_OPTION_SHARE = 0.2

CT_SHAPE_S = 20
CT_FORWARD_S = 15
T_TERRITORY_SHARE = 0.6
T_TERRITORY_MIN_SAMPLES = 20
STACK_MIN = 3        # a site lane is stacked at max(STACK_MIN, map median on that lane + 2)
ROTATE_BEFORE_S = 5
ROTATE_AFTER_S = 15


# ---------------------------------------------------------------------------- spots


def _neighbours(pts: np.ndarray, radius: float, chunk: int = 512) -> list[np.ndarray]:
    r2 = radius * radius
    out: list[np.ndarray] = []
    for s in range(0, len(pts), chunk):
        # Subtract first: squared norms lose small distances at large offsets.
        d2 = np.zeros((len(pts[s:s + chunk]), len(pts)))
        for axis in range(pts.shape[1]):
            delta = pts[s:s + chunk, axis, None] - pts[None, :, axis]
            d2 += delta * delta
        out.extend(np.nonzero(row <= r2)[0] for row in d2)
    return out


def density_clusters(pts: np.ndarray, radius: float, min_size: int,
                     levels: np.ndarray | None = None) -> np.ndarray:
    """Labels (-1 = noise). Seeds use neighbour count, then coordinates; levels never mix."""
    labels = np.full(len(pts), -1, dtype=np.int64)
    if len(pts) == 0:
        return labels
    neigh = _neighbours(pts.astype(np.float64), radius)
    if levels is not None:
        neigh = [ns[levels[ns] == levels[i]] for i, ns in enumerate(neigh)]
    order = sorted(range(len(pts)), key=lambda i: (-len(neigh[i]), tuple(pts[i]), i))
    k = 0
    for i in order:
        if labels[i] != -1:
            continue
        members = neigh[i][labels[neigh[i]] == -1]
        if len(members) >= min_size:
            labels[members] = k
            k += 1
    return labels


def landing_spots(util: pl.DataFrame, mm: MapMeta) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(spots, assignment). assignment maps (demo_id, nade_id) -> spot_id."""
    u = util.filter(
        ~pl.col("is_post_round") & pl.col("thrower_side").is_not_null()
        & pl.col("type").is_in(SPOT_TYPES)
        & pl.all_horizontal(pl.col(c).is_finite() for c in ("land_x", "land_y", "land_z"))
    ).sort("demo_id", "nade_id")
    spots: list[dict] = []
    assign: list[dict] = []
    for side in ("T", "CT"):
        for typ in SPOT_TYPES:
            g = u.filter((pl.col("thrower_side") == side) & (pl.col("type") == typ))
            if g.is_empty():
                continue
            pts = g.select("land_x", "land_y", "land_z").to_numpy()
            levels = (pts[:, 2] < mm.radar["lower_level_max_z"]).astype(int) if "lower_level_max_z" in mm.radar else np.zeros(len(pts), dtype=int)
            labels = density_clusters(pts, SPOT_RADIUS[typ], SPOT_MIN_THROWS, levels)
            g = g.with_columns(label=pl.Series(labels))
            found = []
            for lab, m in g.filter(pl.col("label") >= 0).group_by("label"):
                if m["demo_id"].n_unique() < SPOT_MIN_MATCHES:
                    continue
                found.append(m)
            found.sort(key=lambda m: (-m.height, float(m["land_x"].mean()), float(m["land_y"].mean()), float(m["land_z"].mean())))
            for m in found:
                place = Counter(p for p in m["land_place"].to_list() if p).most_common(1)
                place = place[0][0] if place else None
                x, y, z = (float(m[c].mean()) for c in ("land_x", "land_y", "land_z"))
                rx, ry = mm.to_radar(x, y)
                spots.append({
                    "side": side, "type": typ, "place": place, "region": mm.region(place), "lane": mm.lane(place),
                    "x": x, "y": y, "z": z, "radar_x": rx, "radar_y": ry,
                    "n_throws": m.height, "n_matches": m["demo_id"].n_unique(),
                    "median_pop_t_s": float(m["pop_t_s"].median()) if m["pop_t_s"].drop_nulls().len() else None,
                    "_members": m.select("demo_id", "nade_id"),
                })
    spots.sort(key=lambda s: (s["side"], SPOT_TYPES.index(s["type"]), -s["n_throws"]))
    seen: Counter = Counter()
    for i, s in enumerate(spots):
        s["spot_id"] = f"{mm.name}-{s['side'].lower()}-{s['type']}-s{i:03d}"
        seen[(s["side"], s["type"], s["place"])] += 1
        n = seen[(s["side"], s["type"], s["place"])]
        s["label"] = f"{s['place']}" + (f" #{n}" if n > 1 else "")
        assign.extend({"demo_id": d, "nade_id": n_, "spot_id": s["spot_id"]}
                      for d, n_ in s.pop("_members").iter_rows())
    spot_df = pl.DataFrame(spots, schema={
        "side": pl.Utf8, "type": pl.Utf8, "place": pl.Utf8, "region": pl.Utf8, "lane": pl.Utf8,
        "x": pl.Float64, "y": pl.Float64, "z": pl.Float64, "radar_x": pl.Float64, "radar_y": pl.Float64,
        "n_throws": pl.Int64, "n_matches": pl.Int64, "median_pop_t_s": pl.Float64, "spot_id": pl.Utf8, "label": pl.Utf8,
    })
    assign_df = pl.DataFrame(assign, schema={"demo_id": pl.Utf8, "nade_id": pl.UInt32, "spot_id": pl.Utf8})
    return spot_df, assign_df


# --------------------------------------------------------------------------- T plans


def site_centres(plants: pl.DataFrame, positions: pl.DataFrame) -> dict[str, tuple[float, float, float]]:
    """Mean plant position per site; the mean player position on the site core as a fallback."""
    out = {}
    for site, core in SITE_CORE.items():
        p = plants.filter(pl.col("site") == site)
        if p.height < 3:
            p = positions.filter(pl.col("place") == core)
        if p.height:
            out[site] = (float(p["x"].mean()), float(p["y"].mean()), float(p["z"].mean()))
    return out


def _bearing_groups(angles_deg: list[float], min_gap: float = SPLIT_MIN_ANGLE) -> int:
    """Number of groups when bearings are split at circular gaps >= min_gap."""
    if len(angles_deg) < 2:
        return len(angles_deg)
    a = sorted(x % 360.0 for x in angles_deg)
    gaps = [b - a_ for a_, b in zip(a, a[1:])] + [a[0] + 360.0 - a[-1]]
    return max(1, sum(g >= min_gap for g in gaps))


def _tempo(commit_s: float | None) -> str:
    if commit_s is None:
        return "no_hit"
    if commit_s <= TEMPO_FAST_S:
        return "fast"
    if commit_s < TEMPO_LATE_S:
        return "mid"
    return "late"


def t_plans(sub: dict[str, pl.DataFrame], mm: MapMeta, spot_assign: pl.DataFrame,
            centres: dict[str, tuple[float, float, float]]) -> pl.DataFrame:
    tr = sub["team_rounds"].filter(pl.col("side") == "T").drop("plant_site", "plant_t_s").join(
        round_plants(sub), on=KEYS, how="left", validate="m:1")
    pos = sub["positions"]

    # first second with >= 2 living T players on each site core
    core = (
        pos.filter((pl.col("side") == "T") & pl.col("alive") & (pl.col("t_s") >= 0)
                   & pl.col("place").is_in(list(SITE_CORE.values())))
        .group_by(*KEYS, "t_s", "place").agg(n=pl.col("steamid").n_unique())
        .filter(pl.col("n") >= COMMIT_MIN_PLAYERS)
        .group_by(*KEYS, "place").agg(core_s=pl.col("t_s").min())
        .with_columns(site=pl.col("place").str.slice(-1))
    )
    core_s = {(d, r, s): t for d, r, s, t in core.select(*KEYS, "site", "core_s").iter_rows()}

    rows = []
    for row in tr.select(*KEYS, "team", "opponent", "won", "buy_type", "plant_site", "plant_t_s",
                         "shape_30s", "exec_n_util", "exec_lane").iter_rows(named=True):
        k = (row["demo_id"], row["round_num"])
        hits = {s: core_s[(*k, s)] for s in SITE_CORE if (*k, s) in core_s}
        target = row["plant_site"] or (min(hits, key=hits.get) if hits else None)
        commit = None
        if target:
            cands = [v for v in (hits.get(target), row["plant_t_s"] if row["plant_site"] == target else None) if v is not None]
            commit = float(min(cands)) if cands else None
        attempt = target if commit is not None else (
            row["exec_lane"] if row["exec_lane"] in SITE_CORE and (row["exec_n_util"] or 0) >= ATTEMPT_MIN_UTIL else None)
        rows.append({**{k_: v for k_, v in row.items() if k_ not in ("exec_n_util", "exec_lane")},
                     "target": target if commit is not None else None, "commit_s": commit,
                     "attempt": attempt, "tempo": _tempo(commit), "gun": row["buy_type"] in GUN_BUYS})
    plans = pl.DataFrame(rows, schema_overrides={"commit_s": pl.Float64, "target": pl.Utf8, "attempt": pl.Utf8,
                                                 "plant_t_s": pl.Float64})
    cx = {s_: c[0] for s_, c in centres.items()}
    cy = {s_: c[1] for s_, c in centres.items()}

    # utility around the commit
    u = (
        sub["utility"].filter(~pl.col("is_post_round") & (pl.col("thrower_side") == "T") & pl.col("type").is_in(SPOT_TYPES))
        .join(spot_assign, on=["demo_id", "nade_id"], how="left")
        .join(plans.select(*KEYS, "target", "commit_s").filter(pl.col("commit_s").is_not_null()), on=KEYS)
        .with_columns(other_lane=pl.col("target").replace_strict(OTHER_SITE, default=None))
    )
    ex = u.filter(
        (pl.col("pop_t_s") >= pl.col("commit_s") - EXEC_BEFORE_S) & (pl.col("pop_t_s") <= pl.col("commit_s") + EXEC_AFTER_S)
        & (pl.col("land_lane") != pl.col("other_lane"))
    )
    exec_agg = ex.group_by(KEYS).agg(
        exec_n_util=pl.len(),
        exec_smokes=(pl.col("type") == "smoke").sum(),
        exec_molotovs=(pl.col("type") == "molotov").sum(),
        exec_flashes=(pl.col("type") == "flashbang").sum(),
        exec_he=(pl.col("type") == "he").sum(),
        exec_spots=pl.col("spot_id").filter(pl.col("type").is_in(RECIPE_TYPES) & pl.col("spot_id").is_not_null()).unique().sort(),
    )
    # fake: utility landing near the other site (closer to it than to the target, within FAKE_RADIUS)
    d_other = ((pl.col("land_x") - pl.col("other_lane").replace_strict(cx, default=None, return_dtype=pl.Float64)) ** 2
               + (pl.col("land_y") - pl.col("other_lane").replace_strict(cy, default=None, return_dtype=pl.Float64)) ** 2).sqrt()
    d_target = ((pl.col("land_x") - pl.col("target").replace_strict(cx, default=None, return_dtype=pl.Float64)) ** 2
                + (pl.col("land_y") - pl.col("target").replace_strict(cy, default=None, return_dtype=pl.Float64)) ** 2).sqrt()
    fake = u.with_columns(d_other=d_other, d_target=d_target).filter(
        (pl.col("pop_t_s") >= pl.col("commit_s") - FAKE_FROM_S) & (pl.col("pop_t_s") <= pl.col("commit_s") - FAKE_TO_S)
        & (pl.col("pop_t_s") >= EARLY_UTIL_S) & (pl.col("d_other") <= FAKE_RADIUS) & (pl.col("d_other") < pl.col("d_target"))
    ).group_by(KEYS).agg(
        fake_sm=pl.col("type").is_in(RECIPE_TYPES).sum(), fake_all=pl.len(), fake_from=pl.col("other_lane").first()
    ).with_columns(
        fake_from=pl.when((pl.col("fake_sm") >= 2) | (pl.col("fake_all") >= 3)).then("fake_from")
    ).select(*KEYS, "fake_from")

    # split / lurk from positions around the commit
    committed = plans.filter(pl.col("commit_s").is_not_null()).select(
        *KEYS, "target", t_split=(pl.col("commit_s").floor().cast(pl.Int32) - SPLIT_LOOKBACK_S).clip(lower_bound=0),
        t_commit=pl.col("commit_s").floor().cast(pl.Int32),
        t_lurk=(pl.col("commit_s").floor().cast(pl.Int32) - LURK_LOOKBACK_S).clip(lower_bound=0),
    )
    tpos = pos.filter((pl.col("side") == "T") & pl.col("alive")).select(
        *KEYS, "t_s", "steamid", "name", "x", "y", "region", "lane", "place")

    def _with_dist(df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns(
            dx=pl.col("x") - pl.col("target").replace_strict(cx, default=None, return_dtype=pl.Float64),
            dy=pl.col("y") - pl.col("target").replace_strict(cy, default=None, return_dtype=pl.Float64),
        ).with_columns(dist=(pl.col("dx") ** 2 + pl.col("dy") ** 2).sqrt())

    # (a) bearings seen from the site centre, SPLIT_LOOKBACK_S before the commit
    at_split = _with_dist(committed.join(tpos, left_on=[*KEYS, "t_split"], right_on=[*KEYS, "t_s"]))
    bearings = (
        at_split.filter((pl.col("dist") >= SPLIT_MIN_DIST) & (pl.col("dist") <= SPLIT_MAX_DIST))
        .with_columns(bearing=pl.arctan2("dy", "dx").degrees())
        .group_by(KEYS).agg(bearings=pl.col("bearing"))
        .with_columns(n_directions=pl.col("bearings").map_elements(lambda b: _bearing_groups(list(b)), return_dtype=pl.Int64))
        .select(*KEYS, "n_directions")
    )
    # (b) where the attackers stepped onto the site region: spread of their last outside positions
    win = committed.join(tpos, on=KEYS).with_columns(site_region=pl.col("target") + "_SITE").filter(
        pl.col("t_s") <= pl.col("t_commit") + SPLIT_ENTRY_WINDOW[1])
    first_in = win.filter(pl.col("region") == pl.col("site_region")).group_by(*KEYS, "steamid").agg(t_in=pl.col("t_s").min())
    first_in = first_in.join(committed.select(*KEYS, "t_commit"), on=KEYS).filter(
        pl.col("t_in") >= pl.col("t_commit") - SPLIT_ENTRY_WINDOW[0])
    entry = (
        win.join(first_in.select(*KEYS, "steamid", "t_in"), on=[*KEYS, "steamid"])
        .filter((pl.col("t_s") < pl.col("t_in")) & (pl.col("region") != pl.col("site_region")))
        .sort("t_s").group_by(*KEYS, "steamid").agg(ex=pl.col("x").last(), ey=pl.col("y").last())
    )
    spread = (
        entry.join(entry, on=KEYS, suffix="_b").filter(pl.col("steamid") < pl.col("steamid_b"))
        .group_by(KEYS).agg(entry_spread=((pl.col("ex") - pl.col("ex_b")) ** 2 + (pl.col("ey") - pl.col("ey_b")) ** 2).sqrt().max())
    )
    n_entries = entry.group_by(KEYS).agg(n_entries=pl.len())

    # lurk: at the commit or LURK_LOOKBACK_S before it, a living T on the other site's lane or far away
    lurk_pos = pl.concat([
        committed.join(tpos, left_on=[*KEYS, "t_commit"], right_on=[*KEYS, "t_s"]),
        committed.join(tpos, left_on=[*KEYS, "t_lurk"], right_on=[*KEYS, "t_s"]),
    ])
    lurk = (
        _with_dist(lurk_pos).with_columns(other_lane=pl.col("target").replace_strict(OTHER_SITE, default=None))
        .filter((pl.col("lane") == pl.col("other_lane")) | ((pl.col("dist") >= LURK_MIN_DIST) & (pl.col("lane") != "T_SPAWN")))
        .sort("dist", "steamid", "place", descending=[True, False, False])
        .group_by(KEYS, maintain_order=True)
        .agg(lurker_steamid=pl.col("steamid").first(), lurker_name=pl.col("name").first(), lurker_place=pl.col("place").first())
    )
    mid20 = pos.filter((pl.col("side") == "T") & pl.col("alive") & (pl.col("t_s") == 20)).group_by(KEYS).agg(
        mid_players_20s=(pl.col("lane") == "MID").sum()
    )

    plans = (
        plans.join(exec_agg, on=KEYS, how="left")
        .join(fake, on=KEYS, how="left")
        .join(bearings, on=KEYS, how="left")
        .join(spread, on=KEYS, how="left")
        .join(n_entries, on=KEYS, how="left")
        .join(lurk, on=KEYS, how="left")
        .join(mid20, on=KEYS, how="left")
        .with_columns(
            pl.col("exec_n_util", "exec_smokes", "exec_molotovs", "exec_flashes", "exec_he").fill_null(0),
            pl.col("exec_spots").fill_null([]),
            split=pl.when(pl.col("commit_s").is_null()).then(None).otherwise(
                (pl.col("n_directions").fill_null(0) >= 2) | (pl.col("entry_spread").fill_null(0) >= SPLIT_ENTRY_DIST)),
            lurk=pl.when(pl.col("commit_s").is_null()).then(None).otherwise(pl.col("lurker_steamid").is_not_null()),
        )
        .rename({"shape_30s": "setup_30s"})
        .sort(KEYS)
    )
    return plans


# --------------------------------------------------------------------------- recipes


def jaccard_matrix(sets: list[frozenset]) -> np.ndarray:
    vocab = sorted(set().union(*sets)) if sets else []
    idx = {v: i for i, v in enumerate(vocab)}
    m = np.zeros((len(sets), len(vocab)), dtype=np.float64)
    for r, s in enumerate(sets):
        for v in s:
            m[r, idx[v]] = 1.0
    inter = m @ m.T
    sizes = m.sum(1)
    union = sizes[:, None] + sizes[None, :] - inter
    with np.errstate(invalid="ignore", divide="ignore"):
        d = 1.0 - np.where(union > 0, inter / union, 1.0)
    return d


def average_linkage(dist: np.ndarray, cut: float) -> np.ndarray:
    """Agglomerative clustering, average linkage, merging while the closest pair is <= cut."""
    n = len(dist)
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    c = dist.astype(np.float64).copy()
    np.fill_diagonal(c, np.inf)
    size = np.ones(n)
    owner = np.arange(n)
    while True:
        flat = int(np.argmin(c))
        i, j = divmod(flat, n)
        if not np.isfinite(c[i, j]) or c[i, j] > cut:
            break
        merged = (c[i] * size[i] + c[j] * size[j]) / (size[i] + size[j])
        c[i, :] = merged
        c[:, i] = merged
        c[i, i] = np.inf
        c[j, :] = np.inf
        c[:, j] = np.inf
        size[i] += size[j]
        owner[owner == j] = i
    _, labels = np.unique(owner, return_inverse=True)
    return labels


def execute_recipes(plans: pl.DataFrame, spots: pl.DataFrame, spot_lineups: dict[str, list[dict]],
                    mm: MapMeta, utility: pl.DataFrame | None = None) -> tuple[list[dict], pl.DataFrame]:
    """(recipes, plan -> recipe_id). Gun rounds with a target and >= 2 smoke/molotov spots."""
    spot_info = {r["spot_id"]: r for r in spots.iter_rows(named=True)}

    def _spot_entry(sid: str, share: float) -> dict:
        return {"spot_id": sid, "type": spot_info[sid]["type"], "label": spot_info[sid]["label"],
                "place": spot_info[sid]["place"], "share": round(share, 3), "lineups": spot_lineups.get(sid, [])[:3]}

    recipes: list[dict] = []
    assign: list[dict] = []
    for site in ("A", "B"):
        cand = plans.filter(pl.col("gun") & (pl.col("target") == site) & (pl.col("exec_spots").list.len() >= 2)).sort(KEYS)
        if cand.height < RECIPE_MIN_ROUNDS:
            continue
        sets = [frozenset(s) for s in cand["exec_spots"].to_list()]
        labels = average_linkage(jaccard_matrix(sets), RECIPE_MAX_DIST)
        cand = cand.with_columns(_cl=pl.Series(labels))

        def _freq(m: pl.DataFrame) -> Counter:
            return Counter(s for lst in m["exec_spots"].to_list() for s in lst)

        def _smoke_core(m: pl.DataFrame) -> frozenset:
            f = _freq(m)
            return frozenset(s for s, n in f.items()
                             if spot_info[s]["type"] == "smoke" and n / m.height >= RECIPE_CORE_SHARE)

        # Clusters that share the same smoke core are one recipe whose molotovs vary.
        merged: dict = {}
        for lab in np.unique(labels):
            m = cand.filter(pl.col("_cl") == int(lab))
            key = _smoke_core(m) or ("cluster", int(lab))
            merged[key] = pl.concat([merged[key], m]) if key in merged else m
        groups = []
        for m in merged.values():
            if m.height < RECIPE_MIN_ROUNDS:
                continue
            freq = _freq(m)
            core = [s for s, n in freq.items() if n / m.height >= RECIPE_CORE_SHARE]
            has_smoke = any(spot_info[s]["type"] == "smoke" for s in core)
            if len(core) < 2 and not has_smoke:
                continue
            groups.append((m.sort(KEYS), freq, core))
        groups.sort(key=lambda g: (-g[0].height, sorted(g[2])))
        for m, freq, core in groups:
            rid = f"{mm.name}-{site.lower()}-r{len([r for r in recipes if r['site'] == site]) + 1:02d}"
            core.sort(key=lambda s: (RECIPE_TYPES.index(spot_info[s]["type"]), -freq[s], s))
            n = m.height
            won = int(m["won"].sum())
            teams = Counter(m["team"].to_list())
            tempos = Counter(m["tempo"].to_list())
            # Attribute only execute-window throws in this recipe's rounds and T team.
            participants: dict[str, dict] = {}
            visible = [s for s, c in freq.items() if s in core or c / n >= RECIPE_OPTION_SHARE]
            if utility is not None and not utility.is_empty():
                used = utility.join(m.select(*KEYS, "team", "commit_s", "target"), on=KEYS).filter(
                    (pl.col("thrower_side") == "T") & ~pl.col("is_post_round")
                    & (pl.col("thrower_team") == pl.col("team"))
                    & pl.col("spot_id").is_in(visible)
                    & (pl.col("pop_t_s") >= pl.col("commit_s") - EXEC_BEFORE_S)
                    & (pl.col("pop_t_s") <= pl.col("commit_s") + EXEC_AFTER_S)
                    & (pl.col("land_lane") != pl.col("target").replace_strict(OTHER_SITE, default=None))
                )
                for sid, group in used.group_by("spot_id"):
                    names = Counter(v for v in group["thrower_name"].to_list() if v)
                    participants[sid[0]] = {
                        "thrower": min(names, key=lambda name: (-names[name], name)) if names else None,
                        "median": float(group["pop_t_s"].median()),
                    }
            ordered = sorted(participants, key=lambda sid: (participants[sid]["median"], sid))
            entries = {sid: {**_spot_entry(sid, freq[sid] / n),
                             "thrower": participants.get(sid, {}).get("thrower"),
                             "order": ordered.index(sid) + 1 if sid in participants else None}
                       for sid in visible}
            recipes.append({
                "id": rid,
                "site": site,
                "core": [entries[s] for s in core],
                "options": [entries[s] for s, c in freq.most_common()
                            if s not in core and c / n >= RECIPE_OPTION_SHARE],
                "n_rounds": n,
                "n_matches": m["demo_id"].n_unique(),
                "teams": [{"team": t, "rounds": c} for t, c in teams.most_common()],
                "won": won,
                "win_rate": round(won / n, 3),
                "plant_rate": round(float(m["plant_site"].is_not_null().mean()), 3),
                "median_commit_s": float(m["commit_s"].median()),
                "tempo": [{"value": t, "rounds": c} for t, c in tempos.most_common()],
                "avg_flashes": round(float(m["exec_flashes"].mean()), 2),
                "split_rate": round(float(m["split"].mean()), 3),
                "examples": [{"demo_id": d, "round_num": r, "team": t}
                             for d, r, t in m.select(*KEYS, "team").head(3).iter_rows()],
            })
            assign.extend({"demo_id": d, "round_num": r, "recipe_id": rid} for d, r in m.select(*KEYS).iter_rows())
    return recipes, pl.DataFrame(assign, schema={"demo_id": pl.Utf8, "round_num": pl.Int32, "recipe_id": pl.Utf8})


# ------------------------------------------------------------------------- CT setups


def t_territory(positions: pl.DataFrame, t_s: int = CT_FORWARD_S) -> set[str]:
    """Callouts the T side holds at t_s in >= T_TERRITORY_SHARE of the player samples there."""
    p = positions.filter(pl.col("alive") & (pl.col("t_s") == t_s) & pl.col("place").is_not_null())
    g = p.group_by("place").agg(n=pl.len(), t=(pl.col("side") == "T").sum())
    g = g.filter((pl.col("n") >= T_TERRITORY_MIN_SAMPLES) & (pl.col("t") / pl.col("n") >= T_TERRITORY_SHARE))
    return set(g["place"].to_list())


def ct_setups(sub: dict[str, pl.DataFrame], plans: pl.DataFrame, territory: set[str]) -> pl.DataFrame:
    tr = sub["team_rounds"].filter(pl.col("side") == "CT").select(*KEYS, "team", "opponent", "won", "buy_type", "planted", "plant_site")
    pos = sub["positions"].filter((pl.col("side") == "CT") & pl.col("alive"))

    lanes20 = pos.filter(pl.col("t_s") == CT_SHAPE_S).group_by(KEYS).agg(lanes=pl.col("lane"))
    stack_at = {}
    for site in ("A", "B"):
        counts = [sum(1 for x in l if x == site) for l in lanes20["lanes"].to_list()]
        median = sorted(counts)[len(counts) // 2] if counts else 0
        stack_at[site] = max(STACK_MIN, median + 2)
    shape = lanes20.with_columns(
        shape_20s=pl.col("lanes").map_elements(lambda l: lane_shape(list(l)), return_dtype=pl.Utf8),
        stack_site=pl.col("lanes").map_elements(
            lambda l: next((s for s, n in sorted(Counter(l).items()) if s in stack_at and n >= stack_at[s]), None),
            return_dtype=pl.Utf8),
    ).drop("lanes")
    fwd = pos.filter((pl.col("t_s") == CT_FORWARD_S) & pl.col("place").is_in(list(territory))).group_by(KEYS).agg(
        n_forward=pl.len(), forward_steamids=pl.col("steamid"), forward_places=pl.col("place"),
    )

    # rotations relative to the T commit
    tp = plans.filter(pl.col("commit_s").is_not_null()).select(
        *KEYS, t_target="target", t_commit_s="commit_s",
        t0=pl.col("commit_s").floor().cast(pl.Int32) - ROTATE_BEFORE_S,
    )
    before = tp.join(pos.select(*KEYS, "t_s", "steamid", "lane"), left_on=[*KEYS, "t0"], right_on=[*KEYS, "t_s"])
    before = before.with_columns(other=pl.col("t_target").replace_strict(OTHER_SITE, default=None))
    far = before.filter(pl.col("lane") == pl.col("other")).select(*KEYS, "steamid", "t_target", "t0")
    win = pos.select(*KEYS, "t_s", "steamid", "lane").join(far, on=[*KEYS, "steamid"]).filter(
        (pl.col("t_s") > pl.col("t0")) & (pl.col("t_s") <= pl.col("t0") + ROTATE_BEFORE_S + ROTATE_AFTER_S)
        & (pl.col("lane") == pl.col("t_target"))
    )
    arrived = win.group_by(*KEYS, "steamid").agg(arrive=pl.col("t_s").min(), t0=pl.col("t0").first())
    rot = far.group_by(KEYS).agg(n_far=pl.len()).join(
        arrived.group_by(KEYS).agg(n_rotated=pl.len(), rotate_delay_s=(pl.col("arrive") - pl.col("t0") - ROTATE_BEFORE_S).mean()),
        on=KEYS, how="left",
    ).with_columns(pl.col("n_rotated").fill_null(0))
    on_target_before = before.filter(pl.col("lane") == pl.col("t_target")).group_by(KEYS).agg(n_on_target_before=pl.len())
    on_target_20 = pos.filter(pl.col("t_s") == CT_SHAPE_S).join(tp.select(*KEYS, "t_target"), on=KEYS).filter(
        pl.col("lane") == pl.col("t_target")).group_by(KEYS).agg(n_on_target_20s=pl.len())

    out = (
        tr.join(shape, on=KEYS, how="left")
        .join(fwd, on=KEYS, how="left")
        .join(tp.select(*KEYS, "t_target", "t_commit_s"), on=KEYS, how="left")
        .join(rot, on=KEYS, how="left")
        .join(on_target_before, on=KEYS, how="left")
        .join(on_target_20, on=KEYS, how="left")
        .with_columns(
            pl.col("n_forward").fill_null(0),
            pl.col("forward_steamids").fill_null([]),
            pl.col("forward_places").fill_null([]),
            gun=pl.col("buy_type").is_in(GUN_BUYS),
        )
        .with_columns(
            pl.when(pl.col("t_target").is_not_null()).then(pl.col(c).fill_null(0)).alias(c)
            for c in ("n_far", "n_rotated", "n_on_target_before", "n_on_target_20s")
        )
        .with_columns(pre_rotated=pl.col("n_on_target_before").cast(pl.Int64) - pl.col("n_on_target_20s").cast(pl.Int64))
        .sort(KEYS)
    )
    return out


# --------------------------------------------------------------------------- driver


def analyse_map(sub: dict[str, pl.DataFrame], mm: MapMeta, nade_lineup: pl.DataFrame | None = None) -> dict:
    """Everything M2 computes for one map. nade_lineup maps (demo_id, nade_id) -> lineup_id."""
    spots, spot_assign = landing_spots(sub["utility"], mm)
    spot_lineups: dict[str, list[dict]] = {}
    if nade_lineup is not None and not spot_assign.is_empty():
        j = spot_assign.join(nade_lineup, on=["demo_id", "nade_id"]).group_by("spot_id", "lineup_id").agg(n=pl.len())
        for sid, g in j.sort("n", "lineup_id", descending=[True, False]).group_by("spot_id", maintain_order=True):
            spot_lineups[sid[0]] = [{"lineup_id": l, "n_throws": n} for l, n in g.select("lineup_id", "n").iter_rows()]
    centres = site_centres(sub["plants"], sub["positions"])
    plans = t_plans(sub, mm, spot_assign, centres)
    recipe_utility = sub["utility"].join(spot_assign, on=["demo_id", "nade_id"], how="inner")
    recipes, recipe_assign = execute_recipes(plans, spots, spot_lineups, mm, recipe_utility)
    plans = plans.join(recipe_assign, on=KEYS, how="left")
    territory = t_territory(sub["positions"])
    ct = ct_setups(sub, plans, territory)
    return {
        "spots": spots, "spot_assign": spot_assign, "spot_lineups": spot_lineups, "centres": centres,
        "plans": plans, "recipes": recipes, "territory": sorted(territory), "ct": ct,
    }


# ------------------------------------------------------------------------ site JSON

SITE_SPOTS_PER_KIND = 12  # besides recipe spots, the most used spots per side and type


def name_spots(spots: pl.DataFrame, names: list[dict]) -> dict[str, dict]:
    """spot_id -> {"en", "zh"} from config/spots/<map>.toml (nearest entry of the same side
    and type within its radius)."""
    out: dict[str, dict] = {}
    for r in spots.iter_rows(named=True):
        best = None
        for n in names:
            if n.get("side") != r["side"] or n.get("type") != r["type"]:
                continue
            d = ((n["x"] - r["x"]) ** 2 + (n["y"] - r["y"]) ** 2) ** 0.5
            if d <= n.get("radius", 200) and (best is None or d < best[0]):
                best = (d, n)
        if best:
            out[r["spot_id"]] = {"en": best[1].get("en"), "zh": best[1].get("zh")}
    return out


def _rate(num: int, den: int):
    return round(num / den, 3) if den else None


def _ranked(df: pl.DataFrame, col: str, k: int = 6) -> list[dict]:
    d = df.filter(pl.col(col).is_not_null())
    if d.is_empty():
        return []
    g = d.group_by(col).agg(rounds=pl.len(), won=pl.col("won").sum()).sort("rounds", col, descending=[True, False]).head(k)
    return [{"value": v, "rounds": n, "share": _rate(n, df.height), "won": int(w), "win_rate": _rate(int(w), n)}
            for v, n, w in g.iter_rows()]


def t_summary(plans: pl.DataFrame) -> dict:
    """Gun-round T plans of one team (or all teams) as site numbers."""
    g = plans.filter(pl.col("gun"))
    hit = g.filter(pl.col("commit_s").is_not_null())
    return {
        "gun_rounds": g.height,
        "tempo": _ranked(g, "tempo", 4),
        "target": _ranked(g.with_columns(pl.col("target").fill_null("none")), "target", 3),
        "attempt": _ranked(g.with_columns(pl.col("attempt").fill_null("none")), "attempt", 3),
        "avg_commit_s": round(float(hit["commit_s"].mean()), 1) if hit.height else None,
        "split_rate": _rate(int(hit["split"].sum()), hit.height),
        "lurk_rate": _rate(int(hit["lurk"].sum()), hit.height),
        "fake_rate": _rate(int(hit["fake_from"].is_not_null().sum()), hit.height),
        "recipes": _ranked(g, "recipe_id", 8),
        "lurkers": [{"steamid": str(s), "name": n, "rounds": c} for s, n, c in
                    hit.filter(pl.col("lurk")).group_by("lurker_steamid").agg(name=pl.col("lurker_name").mode().sort().first(), c=pl.len())
                    .sort("c", "name", "lurker_steamid", descending=[True, False, False]).head(3).iter_rows()],
    }


def ct_summary(ct: pl.DataFrame, names: dict[int, str] | None = None) -> dict:
    g = ct.filter(pl.col("gun"))
    hit = g.filter(pl.col("t_target").is_not_null())
    fwd = g.select(*KEYS, "forward_steamids").explode("forward_steamids").drop_nulls("forward_steamids")
    fwd_players = fwd.group_by("forward_steamids").agg(c=pl.col("round_num").len()).sort("c", "forward_steamids", descending=[True, False]).head(5)
    return {
        "gun_rounds": g.height,
        "setups_20s": _ranked(g, "shape_20s", 6),
        "forward_rate": _rate(int((g["n_forward"] > 0).sum()), g.height),
        "forward_players": [{"steamid": str(s), "name": (names or {}).get(s), "rounds": c, "share": _rate(c, g.height)}
                            for s, c in fwd_players.iter_rows()],
        "stack_rate": _rate(int(g["stack_site"].is_not_null().sum()), g.height),
        "stacks": _ranked(g, "stack_site", 2),
        "rotation": {
            "rounds": hit.height,
            "avg_far_players": round(float(hit["n_far"].mean()), 2) if hit.height else None,
            "avg_rotated": round(float(hit["n_rotated"].mean()), 2) if hit.height else None,
            "avg_delay_s": round(float(hit["rotate_delay_s"].drop_nulls().mean()), 1) if hit["rotate_delay_s"].drop_nulls().len() else None,
            "avg_pre_rotated": round(float(hit["pre_rotated"].mean()), 2) if hit.height else None,
        },
    }


def site_spots(res: dict, names: dict[str, dict], mm: MapMeta) -> list[dict]:
    """Spots used by recipes plus the most used ones per side and type, for the site."""
    used = {c["spot_id"] for r in res["recipes"] for c in r["core"] + r["options"]}
    sp = res["spots"]
    top = set()
    for (side, typ), g in sp.group_by("side", "type", maintain_order=True):
        top |= set(g.sort("n_throws", "spot_id", descending=[True, False]).head(SITE_SPOTS_PER_KIND)["spot_id"].to_list())
    keep = sp.filter(pl.col("spot_id").is_in(list(used | top))).sort("side", "type", "spot_id")
    return [{
        "spot_id": r["spot_id"], "side": r["side"], "type": r["type"], "place": r["place"], "label": r["label"],
        "name": names.get(r["spot_id"]), "region": r["region"], "lane": r["lane"],
        "x": round(r["x"], 1), "y": round(r["y"], 1), "z": round(r["z"], 1),
        "radar_x": round(r["radar_x"], 1), "radar_y": round(r["radar_y"], 1),
        "level": int(r["z"] < mm.radar["lower_level_max_z"]) if "lower_level_max_z" in mm.radar else 0,
        "n_throws": r["n_throws"], "n_matches": r["n_matches"],
        "median_pop_t_s": round(r["median_pop_t_s"], 1) if r["median_pop_t_s"] is not None else None,
        "lineups": res["spot_lineups"].get(r["spot_id"], [])[:3],
        "in_recipes": r["spot_id"] in used,
    } for r in keep.iter_rows(named=True)]


DEFINITIONS = {
    "commit": "first second with >= 2 living T players on the site core (BombsiteA/B callout), or the plant",
    "tempo": {"fast": "commit <= 40 s", "mid": "40-75 s", "late": "commit >= 75 s", "no_hit": "no commit"},
    "attempt": "target, or for no_hit rounds the lane of the densest execute utility (>= 3 grenades in 10 s)",
    "split": "entry points onto the site >= 400 units apart, or bearings from the site centre >= 50 degrees apart",
    "lurk": "a living T on the other site's lane or >= 2200 units from the target, at the commit or 10 s before",
    "fake": ">= 2 smokes/molotovs or >= 3 grenades landing near the other site 30-5 s before the commit",
    "recipe": "gun rounds hitting one site with similar smoke+molotov spot sets (average linkage, Jaccard <= 0.6); "
              "core = spots in >= 50% of its rounds, options = 20-50%",
    "ct_setup": "lanes of living CT players at 20 s",
    "forward": "CT standing at 15 s on a callout the T side holds in >= 60% of samples",
    "stack": "a site lane with >= max(3, map median + 2) CT players at 20 s",
    "rotation": "CT players on the other site's lane 5 s before the commit who reach the target lane within 20 s",
}
