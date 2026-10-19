"""Grenade attribution and callout lookup.

GOTV demos often omit the grenade thrower (awpy returns ``thrower_steamid = null``
for every trajectory in the test demo). We recover it by matching each trajectory's
first sample to the ``weapon_fire`` event that threw it: same grenade class, fired
0-32 ticks before the projectile appears, nearest in 2D. The matched throw also gives
the thrower's feet position and view angles at release, which is exactly what a
lineup library needs.
"""

from __future__ import annotations

import numpy as np
import polars as pl

WEAPON_TYPE = {
    "weapon_smokegrenade": "smoke",
    "weapon_flashbang": "flashbang",
    "weapon_hegrenade": "he",
    "weapon_molotov": "molotov",
    "weapon_incgrenade": "molotov",
    "weapon_decoy": "decoy",
}

MATCH_WINDOW_TICKS = 32  # projectile appears within ~0.5s of the throw
MATCH_MAX_DIST = 250.0  # Hammer units between thrower feet and first projectile sample


def trajectory_summary(grenades: pl.DataFrame) -> pl.DataFrame:
    """One row per thrown grenade: first and last sample of its flight."""
    return (
        grenades.sort("tick")
        .group_by("entity_id", "entity_serial", "type", maintain_order=True)
        .agg(
            t0=pl.col("tick").first(),
            t1=pl.col("tick").last(),
            x0=pl.col("x").first(),
            y0=pl.col("y").first(),
            z0=pl.col("z").first(),
            x1=pl.col("x").last(),
            y1=pl.col("y").last(),
            z1=pl.col("z").last(),
            awpy_thrower=pl.col("thrower_steamid").drop_nulls().first(),
        )
        .sort("t0")
        .with_row_index("nade_id")
    )


def attribute_grenades(
    grenades: pl.DataFrame, shots: pl.DataFrame, smokes: pl.DataFrame
) -> pl.DataFrame:
    """Every grenade with its thrower, release position/angles and landing point."""
    traj = trajectory_summary(grenades)
    throws = (
        shots.filter(pl.col("weapon").is_in(list(WEAPON_TYPE)))
        .with_columns(type=pl.col("weapon").replace_strict(WEAPON_TYPE))
        .with_row_index("throw_id")
        .select("throw_id", "type", "tick", "steamid", "name", "side", "x", "y", "z", "pitch", "yaw")
    )

    cand = (
        traj.select("nade_id", "type", "t0", "x0", "y0")
        .join(throws, on="type", how="inner")
        .filter((pl.col("tick") <= pl.col("t0")) & (pl.col("tick") >= pl.col("t0") - MATCH_WINDOW_TICKS))
        .with_columns(dist=((pl.col("x") - pl.col("x0")) ** 2 + (pl.col("y") - pl.col("y0")) ** 2).sqrt())
        .filter(pl.col("dist") <= MATCH_MAX_DIST)
        .sort("dist")
    )
    # Greedy one-to-one assignment, closest pairs first.
    used_nades: set[int] = set()
    used_throws: set[int] = set()
    pairs: list[tuple[int, int, float]] = []
    for nade_id, throw_id, dist in cand.select("nade_id", "throw_id", "dist").iter_rows():
        if nade_id in used_nades or throw_id in used_throws:
            continue
        used_nades.add(nade_id)
        used_throws.add(throw_id)
        pairs.append((nade_id, throw_id, dist))
    match = pl.DataFrame(
        pairs, schema={"nade_id": pl.UInt32, "throw_id": pl.UInt32, "match_dist": pl.Float64}, orient="row"
    )

    smoke_pop = smokes.select(
        "entity_id",
        "entity_serial",
        pop_tick_smoke=pl.col("start_tick"),
        smoke_x=pl.col("x"),
        smoke_y=pl.col("y"),
        smoke_z=pl.col("z"),
    )

    out = (
        traj.join(match, on="nade_id", how="left")
        .join(throws.drop("type"), on="throw_id", how="left")
        .join(smoke_pop, on=["entity_id", "entity_serial"], how="left")
        .select(
            "nade_id",
            "type",
            throw_tick=pl.coalesce("tick", "t0"),
            pop_tick=pl.coalesce("pop_tick_smoke", "t1"),
            thrower_steamid=pl.coalesce("steamid", "awpy_thrower"),
            thrower_name=pl.col("name"),
            awpy_side=pl.col("side"),
            throw_x=pl.coalesce("x", "x0"),
            throw_y=pl.coalesce("y", "y0"),
            throw_z=pl.coalesce("z", "z0"),
            pitch=pl.col("pitch"),
            yaw=pl.col("yaw"),
            land_x=pl.coalesce("smoke_x", "x1"),
            land_y=pl.coalesce("smoke_y", "y1"),
            land_z=pl.coalesce("smoke_z", "z1"),
            matched=pl.col("throw_id").is_not_null(),
            match_dist=pl.col("match_dist"),
        )
    )
    return out


class PlaceIndex:
    """Nearest-neighbour callout lookup for arbitrary world points.

    Built from player positions that carry ``m_szLastPlaceName``. Z is weighted up
    so a point on an upper floor doesn't snap to the floor below.
    """

    def __init__(self, x: np.ndarray, y: np.ndarray, z: np.ndarray, places: list[str], z_weight: float = 2.0):
        keep = np.array([bool(p) for p in places])
        pts = np.stack([x, y, z * z_weight], axis=1)[keep]
        labels = np.array(places, dtype=object)[keep]
        # Thin to a 16-unit grid; plenty of resolution for callouts.
        key = np.round(pts / 16.0).astype(np.int64)
        _, first = np.unique(key, axis=0, return_index=True)
        self.pts = pts[first].astype(np.float64)
        self.labels = labels[first]
        self.z_weight = z_weight
        # 2D copy for points with no nearby floor (e.g. a flashbang popping mid-air).
        self.pts2d = self.pts.copy()
        self.pts2d[:, 2] = 0.0

    @classmethod
    def from_frame(cls, df: pl.DataFrame, place_col: str = "place") -> "PlaceIndex":
        return cls(
            df["x"].to_numpy(), df["y"].to_numpy(), df["z"].to_numpy(), df[place_col].fill_null("").to_list()
        )

    def _nearest(self, q: np.ndarray, pts: np.ndarray, max_dist: float) -> list[str | None]:
        out: list[str | None] = []
        p2 = (pts**2).sum(1)
        for start in range(0, len(q), 512):
            block = q[start : start + 512]
            # |a-b|^2 = |a|^2 + |b|^2 - 2ab, without materialising (block x points x 3)
            d2 = (block**2).sum(1)[:, None] + p2[None, :] - 2.0 * block @ pts.T
            idx = d2.argmin(1)
            best = np.sqrt(np.maximum(d2[np.arange(len(block)), idx], 0.0))
            out.extend(self.labels[i] if b <= max_dist else None for i, b in zip(idx, best))
        return out

    def query(self, x, y, z, max_dist: float = 500.0, fallback_2d: float = 300.0) -> list[str | None]:
        """Callout for each point; points far from any floor fall back to a 2D lookup."""
        x, y, z = (np.asarray(v, float) for v in (x, y, z))
        if len(x) == 0:
            return []
        out = self._nearest(np.stack([x, y, z * self.z_weight], axis=1), self.pts, max_dist)
        missing = [i for i, v in enumerate(out) if v is None]
        if missing and fallback_2d > 0:
            q2 = np.stack([x[missing], y[missing], np.zeros(len(missing))], axis=1)
            for i, v in zip(missing, self._nearest(q2, self.pts2d, fallback_2d)):
                out[i] = v
        return out
