"""Content identity across differently named recordings of the same match.

Winner signatures exclude demo IDs, source match IDs and absolute ticks:
GOTV and archive recordings may start at different ticks or swap team order.
Insufficient or inconsistent histories remain separate rather than guessing from
the final score alone. Parsed files are never changed or removed.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

import polars as pl

from playbook.config import RAW_DIR, canonical_team, load_team_aliases


def match_signature(match: dict, rounds: pl.DataFrame,
                    aliases: dict[str, str] | None = None) -> tuple | None:
    """Map + canonical team pair + ordered winners (or score/round timings).

    ``rounds`` contains just this demo. A winner is a team, never a CT/T side;
    this makes the signature independent of halftime and team_a/team_b order.
    Legacy tables without all winners use team-aligned scores and durations
    rounded to 0.1 seconds (or end ticks rounded to seconds). Known partial
    winners are retained so contradictory histories cannot collapse together.
    """
    aliases = load_team_aliases() if aliases is None else aliases
    teams = [canonical_team(match.get(k), aliases) for k in ("team_a", "team_b")]
    n = match.get("n_rounds")
    if (not match.get("map") or not all(teams) or teams[0] == teams[1]
            or not n or rounds.height != n or "round_num" not in rounds.columns):
        return None
    rows = list(rounds.sort("round_num").iter_rows(named=True))
    if [r["round_num"] for r in rows] != list(range(1, n + 1)):
        return None
    pair = tuple(sorted(teams))
    base = (match["map"], pair)
    winners = []
    for row in rows:
        winner = canonical_team(row.get("winner_team"), aliases)
        if winner is None and row.get("winner_side") in ("CT", "T"):
            winner = canonical_team(row.get(f"{row['winner_side'].lower()}_team"), aliases)
        if winner is not None and winner not in pair:
            return None
        winners.append(winner)
    scores = {team: match.get(key) for team, key in zip(teams, ("score_a", "score_b"))}
    if all(winners):
        # Old/inconsistent score metadata must not silently merge another match.
        counts = Counter(winners)
        if any(scores[t] is not None and scores[t] != counts[t] for t in pair):
            return None
        return (*base, "winners", tuple(winners))

    if any(scores[t] is None or scores[t] < 0 for t in pair) or sum(scores.values()) != n:
        return None
    timing = []
    rate = match.get("tick_rate")
    mode = "durations" if all(r.get("dur_s") is not None for r in rows) else "end_ticks"
    for row in rows:
        value = row.get("dur_s") if mode == "durations" else row.get("end_tick")
        if value is None or not math.isfinite(value) or value < 0:
            return None
        if mode == "end_ticks":
            if not rate or not math.isfinite(rate) or rate <= 0:
                return None
            value /= rate
        timing.append(round(value, 1 if mode == "durations" else 0))
    return (*base, mode, tuple(scores[t] for t in pair), n, tuple(timing), tuple(winners))


def hltv_demo_ids(raw_dir: Path = RAW_DIR) -> set[str]:
    """Use actual HLTV paths, not numeric IDs (archive copies also have those).

    Existing match tables only store basenames. Resolve source preference with
    the same identity function used by parsing, including multipart recordings.
    When raw files are unavailable, the caller falls back to demo_id ordering.
    """
    from playbook.parse import demo_identity

    return {demo_identity(p)["demo_id"] for p in (raw_dir / "hltv").rglob("*")
            if p.is_file() and p.suffix.lower() == ".dem"}


TEAM_COLUMNS = ("team", "team_a", "team_b", "winner", "winner_team", "ct_team", "t_team",
                "attacker_team", "victim_team", "thrower_team", "assister_team", "opponent")


def apply_aliases(tables: dict[str, pl.DataFrame], aliases: dict[str, str] | None = None) -> dict[str, pl.DataFrame]:
    """Re-apply config/team_aliases.csv to every team-name column at export time, so alias
    edits take effect without re-parsing demos (parse applies the aliases known at that time)."""
    aliases = load_team_aliases() if aliases is None else aliases
    out = {}
    for name, df in tables.items():
        cols = [c for c in TEAM_COLUMNS if c in df.columns and df.schema[c] == pl.Utf8]
        if cols:
            uniq = set()
            for c in cols:
                uniq.update(v for v in df[c].unique().to_list() if v is not None)
            mapping = {v: canonical_team(v, aliases) for v in uniq}
            mapping = {k: v for k, v in mapping.items() if v != k}
            if mapping:
                df = df.with_columns(pl.col(c).replace(mapping) for c in cols)
        out[name] = df
    return out


def deduplicate_tables(tables: dict[str, pl.DataFrame], *,
                       preferred_ids: set[str] | None = None,
                       aliases: dict[str, str] | None = None
                       ) -> tuple[dict[str, pl.DataFrame], list[dict]]:
    """Filter every demo-keyed table before aggregation; return an audit trail.

    Keep an HLTV recording first, then the lexicographically first demo_id.
    Missing signatures are never treated as duplicates. Non-demo tables pass
    through unchanged and no input DataFrame is mutated.
    """
    aliases = load_team_aliases() if aliases is None else aliases
    tables = apply_aliases(tables, aliases)
    preferred_ids = set() if preferred_ids is None else preferred_ids
    rounds = tables.get("rounds", pl.DataFrame())
    by_demo = (rounds.partition_by("demo_id", as_dict=True)
               if "demo_id" in rounds.columns else {})
    seen = {}
    duplicates = []
    matches = sorted(tables["matches"].iter_rows(named=True),
                     key=lambda m: (m["demo_id"] not in preferred_ids, m["demo_id"]))
    for match in matches:
        demo_id = match["demo_id"]
        signature = match_signature(match, by_demo.get((demo_id,), pl.DataFrame()), aliases)
        if signature is None:
            continue
        if signature in seen:
            duplicates.append({"map": match["map"], "demo_id": demo_id,
                               "kept_demo_id": seen[signature]})
        else:
            seen[signature] = demo_id
    dropped = {d["demo_id"] for d in duplicates}
    if not dropped:
        return dict(tables), duplicates
    return {name: df.filter(~pl.col("demo_id").is_in(sorted(dropped)))
            if "demo_id" in df.columns else df for name, df in tables.items()}, duplicates


def _pretty_event(slug: str) -> str:
    words = re.split(r"[-_]+", slug)
    keep_upper = {"iem", "pgl", "esl", "blast", "cct", "esea", "fissure", "ewc", "hltv", "cac", "bc", "cs", "epl", "mr15", "wcg"}
    out = []
    for w in words:
        if w.lower() in keep_upper:
            out.append(w.upper())
        elif w.isdigit():
            out.append(w)
        else:
            out.append(w.capitalize())
    return " ".join(out)


def demo_event_slug(path: Path, raw_dir: Path = RAW_DIR) -> str | None:
    """Shared source-path event identity for display names and date lookup."""
    rel = path.relative_to(raw_dir).parts
    if rel[0] == "cs2povarchive" and len(rel) >= 3:
        return rel[1]
    if rel[0] == "hltv" and len(rel) >= 3:
        team1 = path.stem.split("-vs-")[0]
        marker = f"-{team1}-vs-"
        if marker in rel[1]:
            return rel[1].split(marker)[0]
    return None


def demo_events(raw_dir: Path = RAW_DIR) -> dict[str, str]:
    """Event name per demo_id, derived from the archive/dataset directory."""
    from playbook.parse import demo_identity

    out: dict[str, str] = {}
    for path in sorted(raw_dir.rglob("*.dem")):
        slug = demo_event_slug(path, raw_dir)
        if slug:
            out.setdefault(demo_identity(path)["demo_id"], _pretty_event(slug))
    return out
