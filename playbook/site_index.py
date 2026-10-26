"""Small derived indexes for the website, written after the main site export.

    from playbook.site_index import write_site_indexes
    write_site_indexes(SITE_DIR)          # last step of export.export_site

Only reads JSON that the export already wrote under ``out_dir`` (index.json,
heatmap_teams.json and, per active map, tactics.json, lineups.json, players.json and
heatmaps/teams/*.json) and writes two kinds of compact JSON files:

``out_dir/search_index.json``: everything the Ctrl+K palette searches, in one file.
Labels are localised in the browser, so the file holds identifiers and both name
languages. Tables are ``{"columns": [...], "rows": [[...], ...]}``; a ``map``, ``team`` or
``event`` cell is an index into the ``maps``, ``teams`` or ``events`` list::

    maps     map, display_name                 active maps (n_matches > 0), index order
    teams    slug, team, maps                  hub teams (heatmap_teams.json order); maps = [map index]
    events   [event name, ...]
    matches  team, map, demo_id, opponent, date, date_precision, event, hltv_match_id
             one row per team and match, i.e. both perspectives (hub match deep links)
    recipes  id, map, site, spots              spots = [[type, place, label, name_zh, name_en]] in order
    lineups  id, map, side, type, throw_place, land_place, n_throws, name
             one row per (side, type, throw callout, landing callout) group with at least
             MIN_SEARCH_THROWS throws; id = its most-thrown lineup, name = [zh, en] or null
    players  steamid, name, teams              teams = [[map index, team name]]

``out_dir/<map>/lineup_index.json``: ``{lineup_id: row}`` for every lineup that tactics.json
or a team heatmap references, so the tactics page and the hub utility layer no longer
download the full lineups.json::

    side, type, throw_place, land_place, n_throws
    throw   [radar_x, radar_y]                 start of the throw-to-landing line
    land    [radar_x, radar_y]
    setpos  [x, y, z, pitch, yaw]              practice-script position; tactics references only
    name    {"zh": ..., "en": ...}             community landing name, when configured

Missing or malformed inputs are skipped, never fatal: a map without lineups.json gets no
lineup_index.json and the frontend falls back to an empty index.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MIN_SEARCH_THROWS = 3  # a lineup group thrown twice in the whole sample is noise in search

MATCH_COLUMNS = ["team", "map", "demo_id", "opponent", "date", "date_precision", "event", "hltv_match_id"]
RECIPE_COLUMNS = ["id", "map", "site", "spots"]
LINEUP_COLUMNS = ["id", "map", "side", "type", "throw_place", "land_place", "n_throws", "name"]
PLAYER_COLUMNS = ["steamid", "name", "teams"]


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _name(value: Any) -> dict[str, str] | None:
    """A {zh, en} name, kept only when at least one language is filled in."""
    if not isinstance(value, dict):
        return None
    out = {lang: _text(value.get(lang)) for lang in ("zh", "en")}
    return {k: v for k, v in out.items() if v} or None


def _name_pair(value: Any) -> list[str | None] | None:
    name = _name(value)
    return [name.get("zh"), name.get("en")] if name else None


def _number(value: Any) -> bool:
    """A finite JSON number (json.loads accepts NaN and Infinity)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _active_maps(index: Any) -> list[dict]:
    maps = index.get("maps") if isinstance(index, dict) else None
    return [m for m in maps or [] if isinstance(m, dict) and isinstance(m.get("map"), str)
            and _number(m.get("n_matches")) and m["n_matches"] > 0]


def _dicts(value: Any) -> list[dict]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


# ----------------------------------------------------------------------------- lineup index

def _lineup_ids(refs: Any) -> set[str]:
    return {ref["lineup_id"] for ref in _dicts(refs) if isinstance(ref.get("lineup_id"), str)}


def _tactics_lineups(tactics: Any) -> set[str]:
    if not isinstance(tactics, dict):
        return set()
    ids: set[str] = set()
    for spot in _dicts(tactics.get("spots")):
        ids |= _lineup_ids(spot.get("lineups"))
    for recipe in _dicts(tactics.get("recipes")):
        for ref in _dicts(recipe.get("core")) + _dicts(recipe.get("options")):
            ids |= _lineup_ids(ref.get("lineups"))
    return ids


def _heatmap_lineups(map_dir: Path) -> set[str]:
    ids: set[str] = set()
    for path in sorted((map_dir / "heatmaps" / "teams").glob("*.json")):
        heatmap = _read(path)
        summary = heatmap.get("summary") if isinstance(heatmap, dict) else None
        for sides in (summary.values() if isinstance(summary, dict) else []):
            for side in (sides.values() if isinstance(sides, dict) else []):
                utility = side.get("utility") if isinstance(side, dict) else None
                for spot in _dicts(utility.get("spots") if isinstance(utility, dict) else None):
                    ids |= _lineup_ids(spot.get("lineups"))
    return ids


def lineup_index_row(lineup: dict, practice: bool = True) -> dict | None:
    """The subset of one lineups.json row that the tactics radar, the recipe practice
    script and the hub utility trajectory read (web/src/types.ts › LineupRef)."""
    throw, land = lineup.get("throw"), lineup.get("land")
    if not isinstance(throw, dict) or not isinstance(land, dict):
        return None
    start = [throw.get("radar_x"), throw.get("radar_y")]
    end = [land.get("radar_x"), land.get("radar_y")]
    if not all(_number(v) for v in start + end):
        return None
    row: dict[str, Any] = {
        "side": lineup.get("side"), "type": lineup.get("type"),
        "throw_place": lineup.get("throw_place"), "land_place": lineup.get("land_place"),
        "n_throws": lineup.get("n_throws"), "throw": start, "land": end,
    }
    setpos = [throw.get(key) for key in ("x", "y", "z", "pitch", "yaw")]
    if practice and all(_number(v) for v in setpos):
        row["setpos"] = setpos
    name = _name(lineup.get("name"))
    if name:
        row["name"] = name
    return row


def build_lineup_index(map_dir: Path, lineups: Any, tactics: Any) -> dict[str, dict]:
    """{lineup_id: row} for every lineup referenced by tactics.json or a team heatmap."""
    practice = _tactics_lineups(tactics)
    wanted = practice | _heatmap_lineups(map_dir)
    out: dict[str, dict] = {}
    for lineup in _dicts(lineups):
        lineup_id = lineup.get("id")
        if isinstance(lineup_id, str) and lineup_id in wanted:
            row = lineup_index_row(lineup, practice=lineup_id in practice)
            if row is not None:
                out[lineup_id] = row
    return dict(sorted(out.items()))


# ----------------------------------------------------------------------------- search index

def _recipe_spots(recipe: dict) -> list[list]:
    refs = sorted(_dicts(recipe.get("core")) + _dicts(recipe.get("options")),
                  key=lambda ref: (not _number(ref.get("order")), ref.get("order") if _number(ref.get("order")) else 0))
    out = []
    for ref in refs:
        pair = _name_pair(ref.get("name")) or [None, None]
        out.append([ref.get("type"), ref.get("place"), ref.get("label"), *pair])
    return out


def _lineup_groups(lineups: Any) -> list[dict]:
    """One row per (side, type, throw callout, landing callout). The palette label is
    exactly those four fields, so near-duplicate lineups would only repeat it; each
    group links to its most-thrown lineup and is ranked by the group's total throws."""
    groups: dict[tuple, dict] = {}
    for lineup in _dicts(lineups):
        if not isinstance(lineup.get("id"), str):
            continue
        key = (lineup.get("side"), lineup.get("type"), lineup.get("throw_place"), lineup.get("land_place"))
        throws = lineup["n_throws"] if _number(lineup.get("n_throws")) else 0
        group = groups.setdefault(key, {"id": None, "top": -1, "n_throws": 0, "name": None})
        group["n_throws"] += throws
        if throws > group["top"]:
            group.update(id=lineup["id"], top=throws, name=_name_pair(lineup.get("name")))
    rows = [{**group, "key": key} for key, group in groups.items() if group["n_throws"] >= MIN_SEARCH_THROWS]
    return sorted(rows, key=lambda g: (-g["n_throws"], g["id"]))


def build_search_index(out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    index = _read(out_dir / "index.json")
    maps = _active_maps(index)
    map_ids = {m["map"]: i for i, m in enumerate(maps)}
    teams, matches, events = [], [], {}
    for team in _dicts(_read(out_dir / "heatmap_teams.json")):
        if not isinstance(team.get("slug"), str):
            continue
        entries = [m for m in _dicts(team.get("maps")) if m.get("map") in map_ids]
        team_i = len(teams)
        teams.append([team["slug"], _text(team.get("team")) or team["slug"], [map_ids[m["map"]] for m in entries]])
        for entry in entries:
            for match in _dicts(entry.get("results")):
                if not isinstance(match.get("demo_id"), str):
                    continue
                event = _text(match.get("event"))
                event_i = events.setdefault(event, len(events)) if event else None
                matches.append([team_i, map_ids[entry["map"]], match["demo_id"], _text(match.get("opponent")),
                                match.get("date"), match.get("date_precision"), event_i, match.get("hltv_match_id")])
    recipes, lineups, players = [], [], {}
    for entry in maps:
        map_i, map_dir = map_ids[entry["map"]], out_dir / entry["map"]
        tactics = _read(map_dir / "tactics.json")
        for recipe in _dicts(tactics.get("recipes") if isinstance(tactics, dict) else None):
            if isinstance(recipe.get("id"), str):
                recipes.append([recipe["id"], map_i, recipe.get("site"), _recipe_spots(recipe)])
        for group in _lineup_groups(_read(map_dir / "lineups.json")):
            lineups.append([group["id"], map_i, *group["key"], group["n_throws"], group["name"]])
        for player in _dicts(_read(map_dir / "players.json")):
            if player.get("steamid") in (None, ""):
                continue
            steamid = str(player["steamid"])
            row = players.setdefault(steamid, [steamid, _text(player.get("name")) or steamid, []])
            row[2].append([map_i, _text(player.get("team"))])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": index.get("generated_at") if isinstance(index, dict) else None,
        "maps": {"columns": ["map", "display_name"], "rows": [[m["map"], _text(m.get("display_name")) or m["map"]] for m in maps]},
        "teams": {"columns": ["slug", "team", "maps"], "rows": teams},
        "events": list(events),
        "matches": {"columns": MATCH_COLUMNS, "rows": matches},
        "recipes": {"columns": RECIPE_COLUMNS, "rows": recipes},
        "lineups": {"columns": LINEUP_COLUMNS, "rows": lineups},
        "players": {"columns": PLAYER_COLUMNS, "rows": sorted(players.values(), key=lambda p: (p[1].lower(), p[0]))},
    }


def write_site_indexes(out_dir: Path) -> None:
    """Write search_index.json and each active map's lineup_index.json under out_dir."""
    out_dir = Path(out_dir)
    for entry in _active_maps(_read(out_dir / "index.json")):
        map_dir = out_dir / entry["map"]
        lineups = _read(map_dir / "lineups.json")
        if isinstance(lineups, list):
            _write(map_dir / "lineup_index.json", build_lineup_index(map_dir, lineups, _read(map_dir / "tactics.json")))
    _write(out_dir / "search_index.json", build_search_index(out_dir))
