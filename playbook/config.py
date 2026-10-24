"""Project paths and the small config files under ``config/``."""

from __future__ import annotations

import csv
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PARSED_DIR = DATA_DIR / "parsed"
SITE_DIR = DATA_DIR / "site"

# Lane order used when printing a "shape" such as "A2 M2 B1".
LANE_ORDER = ["T_SPAWN", "A", "MID", "B", "CT_SPAWN"]
LANE_SHORT = {"T_SPAWN": "S", "A": "A", "MID": "M", "B": "B", "CT_SPAWN": "C", "OTHER": "?"}


def load_targets(path: Path | None = None) -> dict:
    with open(path or CONFIG_DIR / "targets.toml", "rb") as fh:
        return tomllib.load(fh)


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().lower()


def load_team_aliases(path: Path | None = None) -> dict[str, str]:
    """alias (lower-cased) -> canonical team name."""
    path = path or CONFIG_DIR / "team_aliases.csv"
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        return {_norm(row["alias"]): row["canonical"].strip() for row in csv.DictReader(fh) if row.get("alias")}


def canonical_team(name: str | None, aliases: dict[str, str]) -> str | None:
    if name is None or not str(name).strip():
        return None
    return aliases.get(_norm(name), str(name).strip())


def load_player_aliases(path: Path | None = None) -> dict[int, int]:
    """Verified alternate Steam ID -> canonical Steam ID; names/notes are audit metadata."""
    path = path or CONFIG_DIR / "player_aliases.csv"
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        return {int(row["alias_steamid"]): int(row["canonical_steamid"])
                for row in csv.DictReader(fh) if row.get("alias_steamid")}


def team_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@dataclass
class MapMeta:
    name: str
    display_name: str
    radar: dict[str, float]
    callout_region: dict[str, str] = field(default_factory=dict)
    region_lane: dict[str, str] = field(default_factory=dict)

    def region(self, callout: str | None) -> str:
        if not callout:
            return "OTHER"
        return self.callout_region.get(callout, "OTHER")

    def lane(self, callout: str | None) -> str:
        return self.region_lane.get(self.region(callout), "OTHER")

    def to_radar(self, x: float, y: float) -> tuple[float, float]:
        """World coordinates -> pixel on the 1024x1024 radar image."""
        return (x - self.radar["pos_x"]) / self.radar["scale"], (self.radar["pos_y"] - y) / self.radar["scale"]


def load_map(map_name: str) -> MapMeta:
    """Load ``config/maps/<map>.toml``. Unknown maps get an empty mapping (everything is OTHER)."""
    path = CONFIG_DIR / "maps" / f"{map_name}.toml"
    if not path.exists():
        return MapMeta(name=map_name, display_name=map_name, radar={"pos_x": 0.0, "pos_y": 0.0, "scale": 1.0})
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)
    return MapMeta(
        name=raw.get("map", map_name),
        display_name=raw.get("display_name", map_name),
        radar=raw.get("radar", {"pos_x": 0.0, "pos_y": 0.0, "scale": 1.0}),
        callout_region=raw.get("callouts", {}),
        region_lane=raw.get("regions", {}),
    )


def load_spot_names(map_name: str) -> list[dict]:
    """``config/spots/<map>.toml``: human names for landing spots, matched by position
    (side, type and within ``radius`` units), so names survive re-clustering."""
    path = CONFIG_DIR / "spots" / f"{map_name}.toml"
    if not path.exists():
        return []
    with open(path, "rb") as fh:
        return tomllib.load(fh).get("spot", [])
