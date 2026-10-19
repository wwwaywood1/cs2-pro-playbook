"""Check a map's callout config and its translations against the callouts seen in demos.

    python scripts/check_map_config.py de_nuke de_dust2      # specific maps
    python scripts/check_map_config.py --all                 # every map with an input table

Inputs (all relative to the repo root):
    delegation/inputs/<map>_callouts.csv   callouts seen in real demos (scripts/make_map_briefs.py)
    config/maps/<map>.toml                 [regions] and [callouts] to check
    web/src/i18n/zh.json, en.json          callout.<map>.<Callout> translations

Exit code 0 when every check passes. Uses only the standard library (Python 3.11+).
"""

from __future__ import annotations

import csv
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANES = {"T_SPAWN", "A", "MID", "B", "CT_SPAWN"}
FIXED = {"TSpawn": "T_SPAWN", "CTSpawn": "CT_SPAWN", "BombsiteA": "A", "BombsiteB": "B"}

# Radar transforms from awpy-data release 2000933 (map_data.json). Must not be edited.
RADAR = {
    "de_ancient": (-2953.0, 2164.0, 5.0),
    "de_anubis": (-2796.0, 3328.0, 5.22),
    "de_dust2": (-2476.0, 3239.0, 4.4),
    "de_inferno": (-2087.0, 3870.0, 4.9),
    "de_mirage": (-3230.0, 1713.0, 5.0),
    "de_nuke": (-3453.0, 2887.0, 7.0),
    "de_overpass": (-4831.0, 1781.0, 5.2),
    "de_train": (-2308.0, 2078.0, 4.082077),
    "de_vertigo": (-3168.0, 1762.0, 4.0),
}


def check(map_name: str) -> list[str]:
    errors: list[str] = []
    table = ROOT / "delegation" / "inputs" / f"{map_name}_callouts.csv"
    cfg_path = ROOT / "config" / "maps" / f"{map_name}.toml"
    if not table.exists():
        return [f"missing input table {table.relative_to(ROOT)}"]
    with open(table, newline="", encoding="utf-8") as fh:
        expected = [row["callout"] for row in csv.DictReader(fh)]

    try:
        with open(cfg_path, "rb") as fh:
            cfg = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"{cfg_path.relative_to(ROOT)}: cannot load ({exc})"]

    if cfg.get("map") != map_name:
        errors.append(f"map = {cfg.get('map')!r}, expected {map_name!r}")
    radar = cfg.get("radar", {})
    if map_name in RADAR and (radar.get("pos_x"), radar.get("pos_y"), radar.get("scale")) != RADAR[map_name]:
        errors.append(f"[radar] was changed; it must stay pos_x/pos_y/scale = {RADAR[map_name]}")

    regions: dict = cfg.get("regions", {})
    callouts: dict = cfg.get("callouts", {})
    for region, lane in regions.items():
        if lane not in LANES:
            errors.append(f"[regions] {region} = {lane!r} is not one of {sorted(LANES)}")
    missing = [c for c in expected if c not in callouts]
    extra = [c for c in callouts if c not in expected]
    if missing:
        errors.append(f"[callouts] missing {len(missing)}: {', '.join(missing)}")
    if extra:
        errors.append(f"[callouts] not in the demo table (typo or invented): {', '.join(extra)}")
    for name, region in callouts.items():
        if region not in regions:
            errors.append(f"[callouts] {name} = {region!r} is not defined in [regions]")
    for name, lane in FIXED.items():
        if name in callouts and regions.get(callouts[name]) != lane:
            errors.append(f"{name} must end up in lane {lane} (now {regions.get(callouts[name])!r})")

    for lang in ("zh", "en"):
        path = ROOT / "web" / "src" / "i18n" / f"{lang}.json"
        try:
            labels = json.loads(path.read_text(encoding="utf-8")).get("callout", {}).get(map_name, {})
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: cannot load ({exc})")
            continue
        lost = [c for c in expected if not str(labels.get(c, "")).strip()]
        stray = [c for c in labels if c not in expected]
        if lost:
            errors.append(f"{lang}.json callout.{map_name}: missing or empty {len(lost)}: {', '.join(lost)}")
        if stray:
            errors.append(f"{lang}.json callout.{map_name}: not in the demo table: {', '.join(stray)}")
    return errors


def main() -> None:
    args = sys.argv[1:]
    if args == ["--all"] or not args:
        args = sorted(p.name.removesuffix("_callouts.csv") for p in (ROOT / "delegation" / "inputs").glob("*_callouts.csv"))
    failed = 0
    for map_name in args:
        errors = check(map_name)
        print(f"{'OK  ' if not errors else 'FAIL'} {map_name}")
        for e in errors:
            print(f"     - {e}")
        failed += bool(errors)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
