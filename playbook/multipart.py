"""Ordered recordings of one map, normalized to a single tick timeline.

awpy 3.1 accepts multiple files but rejects overlapping/live-round boundaries.
Decode sources separately so backup restores can be resolved before validation.
No part column escapes into the stored tables.
"""
from __future__ import annotations

import re
from pathlib import Path

import polars as pl
from awpy import Demo

PART_RE = re.compile(r"-p(\d+)$")
DUPLICATE_RE = re.compile(r"\(\d+\)$")
TICK_COLUMNS = ("start_tick", "freeze_end_tick", "end_tick", "official_end_tick")


def game_stem(path: Path) -> str:
    return PART_RE.sub("", path.stem)


def ordered_paths(paths: list[Path]) -> list[Path]:
    """Require one game and consecutive numbered parts, starting at p1."""
    paths = [Path(p) for p in paths]
    if not paths:
        raise ValueError("No demo paths")
    if len({(p.resolve().parent, game_stem(p)) for p in paths}) != 1:
        raise ValueError("Multipart paths must belong to one game in one directory")
    numbered = [PART_RE.search(p.stem) for p in paths]
    if any(numbered):
        if not all(numbered):
            raise ValueError("Cannot mix a standalone demo and numbered parts")
        paths.sort(key=lambda p: int(PART_RE.search(p.stem)[1]))
        numbers = [int(PART_RE.search(p.stem)[1]) for p in paths]
        if numbers != list(range(1, len(paths) + 1)):
            raise ValueError("Multipart files need consecutive parts starting at p1")
    elif len(paths) != 1:
        raise ValueError("Repeated standalone demo paths")
    return paths


def _offset_ticks(frame: pl.DataFrame, offset: int) -> pl.DataFrame:
    return frame.with_columns(
        (pl.col(c).cast(pl.Int64) + offset).alias(c)
        for c in frame.columns if c == "tick" or c.endswith("_tick")
    )


def _stitch_rounds(parts: list[pl.DataFrame]):
    """Return (global rounds, retained local rounds per part, tick offsets).

    A later complete overlap replaces the earlier suffix. Boundary fragments
    require a complete copy somewhere in the final history; they are never merged.
    Restores within a single recording remain an error (GPT-01).
    """
    from playbook.parse import SIDE, _validate_rounds

    owners: dict[int, int] = {}
    complete_parts = []
    required_rounds = set()
    fragments = set()
    offsets = []
    next_tick = 0
    for part, raw in enumerate(parts):
        raw = raw.filter(~pl.col("is_knife_round"))
        offsets.append(next_tick)
        last_tick = raw["official_end_tick"].max()
        next_tick += max(int(last_tick or 0), 0) + 1
        nums = raw["round_num"].to_list()
        if any(n is None or n < 1 for n in nums) or nums != sorted(set(nums)):
            raise ValueError(f"Part {part + 1}: incomplete or restored round history")
        complete = pl.all_horizontal(pl.col(c).is_not_null() for c in TICK_COLUMNS)
        # A malformed winner is not a recoverable boundary fragment.
        if raw.filter(pl.col("winner_side").is_not_null() & ~pl.col("winner_side").is_in(list(SIDE))).height:
            raise ValueError(f"Part {part + 1}: round has no recognized winner")
        valid = raw.filter(complete & pl.col("winner_side").is_in(list(SIDE)))
        fragment_nums = set(nums) - set(valid["round_num"])
        if fragment_nums - set(nums[:1] + nums[-1:]):
            raise ValueError(f"Part {part + 1}: incomplete interior round")
        fragments.update(fragment_nums)
        if valid.height:
            _validate_rounds(valid, first_round=valid["round_num"][0])
            required_rounds.update(valid["round_num"])
            first = valid["round_num"][0]
            # Roll back the old suffix; never splice old post-restore outcomes back in.
            if owners and first <= max(owners):
                owners = {n: p for n, p in owners.items() if n < first}
            owners.update({n: part for n in valid["round_num"]})
        complete_parts.append(valid)
    if required_rounds - owners.keys():
        raise ValueError("Restore does not cover earlier round suffix")
    if fragments - owners.keys():
        raise ValueError(f"Incomplete rounds have no complete copy: {sorted(fragments - owners.keys())}")
    kept = [r.filter(pl.col("round_num").is_in([n for n, p in owners.items() if p == i]))
            for i, r in enumerate(complete_parts)]
    rounds = pl.concat([_offset_ticks(r, offset) for r, offset in zip(kept, offsets)], how="diagonal_relaxed")
    _validate_rounds(rounds)
    return rounds, kept, offsets


def _round_buy_types(economy: pl.DataFrame, max_rounds: int) -> pl.DataFrame:
    return economy.with_columns(
        buy_type=pl.when(pl.col("round_num").is_in([1, max_rounds // 2 + 1])).then(pl.lit("pistol"))
        .when(pl.col("equipment_value") < 5000).then(pl.lit("eco"))
        .when(pl.col("equipment_value") < 20000).then(pl.lit("force"))
        .otherwise(pl.lit("full"))
    )


class GameDemo:
    """Small adapter exposing the single-demo operations used by parse_demo.

    Tick-based rows are restricted to their retained local bounds before offsetting.
    Projectile handles and attribution are kept local until reduced to one grenade.
    """

    def __init__(self, paths: list[Path]):
        self.paths = ordered_paths(paths)
        self.parts = [Demo(p) for p in self.paths]
        self.header = self.parts[0].header
        self.tick_rate = self.parts[0].tick_rate
        self.convars = self.parts[0].convars
        for i, d in enumerate(self.parts):
            if any(d.header.get(k) != self.header.get(k) for k in ("map_name", "build_num")):
                raise ValueError(f"Part {i + 1}: incompatible map or build")
            if d.tick_rate != self.tick_rate:
                raise ValueError(f"Part {i + 1}: incompatible tick rate")
            for key, default in (("mp_maxrounds", 24), ("mp_overtime_maxrounds", 6)):
                if int(d.convars.get(key, default)) != int(self.convars.get(key, default)):
                    raise ValueError(f"Part {i + 1}: incompatible {key}")
        self.rounds, self.local_rounds, self.offsets = _stitch_rounds([d.rounds for d in self.parts])

    def load(self, *datasets):
        for d in self.parts:
            d.load(*datasets)

    def _bounds(self, i):
        return self.local_rounds[i].select(pl.col("start_tick").cast(pl.Int64), pl.col("official_end_tick").cast(pl.Int64))

    def _live(self, frame, i, tick="tick"):
        from playbook.parse import _live_ticks
        frame = frame.with_columns(pl.col(tick).cast(pl.Int64))
        if tick != "tick":
            return _live_ticks(frame.rename({tick: "tick"}), self._bounds(i)).rename({"tick": tick})
        return _live_ticks(frame, self._bounds(i))

    @property
    def players(self):
        # Keep clan evidence from all recordings; _resolve_teams rejects conflicts.
        return pl.concat([d.players for d in self.parts], how="diagonal_relaxed")

    def _events(self, name):
        return pl.concat([_offset_ticks(self._live(getattr(d, name), i), self.offsets[i])
                          for i, d in enumerate(self.parts)], how="diagonal_relaxed")

    @property
    def kills(self):
        return self._events("kills")

    @property
    def bomb(self):
        return self._events("bomb")

    @property
    def shots(self):
        return self._events("shots")

    @property
    def round_economy(self):
        economy = pl.concat([
            d.round_economy.filter(pl.col("round_num").is_in(self.local_rounds[i]["round_num"].implode()))
            for i, d in enumerate(self.parts)
        ], how="diagonal_relaxed")
        # awpy labels the first observed round in each standalone file as pistol.
        # Reclassify with the same 3.1 thresholds and the game's regulation halves.
        return _round_buy_types(economy, int(self.convars.get("mp_maxrounds", 24)))

    def ticks(self, props, players_only=True):
        return pl.concat([_offset_ticks(self._live(d.ticks(props, players_only=players_only), i), self.offsets[i])
                          for i, d in enumerate(self.parts) if self.local_rounds[i].height], how="diagonal_relaxed")

    def snapshots(self, *, ticks):
        frames = []
        for i, d in enumerate(self.parts):
            r = self.local_rounds[i]
            local = [t - self.offsets[i] for t in ticks
                     if r.filter((pl.col("start_tick") <= t - self.offsets[i])
                                 & (pl.col("official_end_tick") >= t - self.offsets[i])).height]
            if local:
                frames.append(_offset_ticks(d.snapshots(ticks=local), self.offsets[i]))
        return pl.concat(frames, how="diagonal_relaxed")

    def attributed_grenades(self):
        from playbook.utility import attribute_grenades
        frames = []
        for i, d in enumerate(self.parts):
            u = attribute_grenades(d.grenades, d.shots, d.smokes, tick_rate=self.tick_rate)
            frames.append(_offset_ticks(self._live(u, i, "throw_tick"), self.offsets[i]).drop("nade_id"))
        return pl.concat(frames, how="diagonal_relaxed").with_row_index("nade_id")
