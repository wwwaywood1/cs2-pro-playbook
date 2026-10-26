"""scripts/make_map_briefs.py --parsed: callout tables from data/parsed without re-parsing."""
import importlib.util
from pathlib import Path

import polars as pl

spec = importlib.util.spec_from_file_location(
    "make_map_briefs", Path(__file__).resolve().parents[1] / "scripts" / "make_map_briefs.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_callout_table_from_parsed_tables(tmp_path):
    for name in ("matches", "positions", "plants"):
        (tmp_path / name).mkdir()
    pl.DataFrame({"demo_id": ["d1", "d2"], "map": ["de_nuke", "de_mirage"]}).write_parquet(tmp_path / "matches" / "d1.parquet")
    pl.DataFrame({"demo_id": ["d1"] * 4, "round_num": [1, 1, 2, 2], "side": ["T", "CT", "T", "T"],
                  "t_s": [5, 10, 30, 31], "x": [0.0, 10.0, 20.0, 22.0], "y": [0.0, 1.0, 2.0, 2.0],
                  "z": [0.0] * 4, "place": ["Crane", "Crane", "Lobby", "Lobby"],
                  "alive": [True, True, True, False]}).write_parquet(tmp_path / "positions" / "d1.parquet")
    pl.DataFrame({"demo_id": ["d1"], "round_num": [2], "tick": [100], "site": ["A"]}).write_parquet(
        tmp_path / "plants" / "d1.parquet")
    data = mod.collect_parsed(["de_nuke", "de_ancient"], parsed=tmp_path)
    assert set(data) == {"de_nuke"}
    t = mod.table("de_nuke", data["de_nuke"])
    rows = {r["callout"]: r for r in t.iter_rows(named=True)}
    assert rows["Crane"]["samples"] == 2 and rows["Crane"]["ct_first_20s"] == 1
    assert rows["Lobby"]["samples"] == 1 and rows["Lobby"]["t_when_a_plant"] == 1
