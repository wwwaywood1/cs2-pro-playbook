"""Verified Steam IDs stay consistent across export tables and derived views."""
import json

import polars as pl
import pytest

from playbook.config import canonical_team, load_player_aliases, load_team_aliases, team_slug
from playbook.dedupe import apply_aliases

ALIAS = 76561198018303780
CANONICAL = 76561198386265483


def test_load_player_aliases(tmp_path):
    assert load_player_aliases(tmp_path / "missing.csv") == {}
    path = tmp_path / "players.csv"
    path.write_text("alias_steamid,canonical_steamid,name,note\n"
                    f"{ALIAS},{CANONICAL},donk,verified\n", encoding="utf-8")
    assert load_player_aliases(path) == {ALIAS: CANONICAL}
    assert load_player_aliases()[ALIAS] == CANONICAL


@pytest.mark.parametrize("dtype", [pl.UInt64, pl.Int64, pl.String])
def test_all_identity_columns_preserve_types_nulls_and_source_tables(dtype):
    values = [ALIAS, CANONICAL, None, 0, 123]
    expected = [CANONICAL, CANONICAL, None, 0, 123]
    if dtype == pl.String:
        values = [str(v) if v is not None else None for v in values]
        expected = [str(v) if v is not None else None for v in expected]
    source = {
        name: pl.DataFrame({c: values for c in cols}, schema={c: dtype for c in cols})
        for name, cols in {
            "players": ["steamid"], "player_rounds": ["steamid"],
            "positions": ["steamid"], "loadouts": ["steamid"],
            "plants": ["steamid"], "shots": ["steamid"],
            "utility": ["thrower_steamid"],
            "kills": ["attacker_steamid", "victim_steamid", "assister_steamid"],
        }.items()
    }
    source["metadata"] = pl.DataFrame({"name": ["donk"], "hltv_match_id": [ALIAS]})
    out = apply_aliases(source, {}, {ALIAS: CANONICAL})
    for name, df in source.items():
        assert out[name].schema == df.schema
        if name == "metadata":
            assert out[name].equals(df)
            continue
        for c in df.columns:
            assert df[c].to_list() == values
            assert out[name][c].to_list() == expected
    assert all(df.equals(apply_aliases(out, {}, {ALIAS: CANONICAL})[name])
               for name, df in out.items())
    assert all(df.equals(apply_aliases(source, {}, {})[name]) for name, df in source.items())


@pytest.mark.parametrize("alias,canonical,slug", [
    ("100T", "100 Thieves", "100-thieves"),
    ("OG CS2", "OG", "og"),
    ("SINNERS ESPORT", "SINNERS", "sinners"),
    ("Inner Circle Esports", "Inner Circle", "inner-circle"),
    ("Team Spirit", "Spirit", "spirit"),
    ("FLC", "Falcons", "falcons"),
])
def test_team_aliases_and_canonical_slugs(alias, canonical, slug):
    aliases = load_team_aliases()
    assert canonical_team(alias, aliases) == canonical
    assert canonical_team(canonical, aliases) == canonical
    assert team_slug(canonical) == slug


def test_export_applies_player_aliases_to_all_derived_views(tmp_path, monkeypatch):
    from playbook import export
    from playbook.store import write_tables
    from test_export_lineups import synthetic_tables
    from test_heatmap import SID
    from test_tactics import MM

    tables = synthetic_tables()
    for name, df in tables.items():
        cols = [c for c in df.columns if c == "steamid" or c.endswith("_steamid")]
        # Alternate account in one demo, main account in another; same display player.
        tables[name] = df.with_columns(
            pl.when(pl.col(c).is_in([SID, 100]))
            .then(pl.when(pl.col("demo_id") == "d0").then(pl.lit(ALIAS, pl.UInt64))
                  .otherwise(pl.lit(CANONICAL, pl.UInt64)))
            .otherwise(pl.col(c)).alias(c) for c in cols)
    # Complete the small lineup fixture so real profiles, radar, WPA and replays run.
    tables["matches"] = tables["matches"].with_columns(team_a=pl.lit("Red"), team_b=pl.lit("Blue"))
    tables["player_rounds"] = tables["player_rounds"].with_columns(
        won=pl.col("side") == "T", hs_kills=pl.lit(0), death_traded=pl.lit(False),
        is_awp=pl.lit(False), util_thrown=pl.lit(1), dist_to_team_30s=pl.lit(100.),
        site_entry_rank=pl.lit(1), lane_15s=pl.lit("A"), place_30s=pl.lit("BombsiteA"))
    tables["rounds"] = tables["player_rounds"].select("demo_id", "round_num").unique().with_columns(
        t_team=pl.lit("Red"), ct_team=pl.lit("Blue"), dur_s=pl.lit(39.), winner_side=pl.lit("T"))
    tables["plants"] = tables["plants"].with_columns(
        t_s=pl.lit(35.), steamid=pl.when(pl.col("demo_id") == "d0").then(pl.lit(ALIAS, pl.UInt64))
        .otherwise(pl.lit(CANONICAL, pl.UInt64)), team=pl.lit("Red"))
    tables["kills"] = tables["kills"].with_columns(weapon=pl.lit("ak47"))
    seen = []

    def check_winprob(t):
        seen.append("winprob")
        for df in t.values():
            for c in df.columns:
                if c == "steamid" or c.endswith("_steamid"):
                    assert ALIAS not in df[c].to_list()
        assert set(t["player_rounds"].filter(pl.col("team") == "Red")["steamid"]) == {CANONICAL}
        # Supply deterministic probabilities; keep real action attribution/aggregation.
        wp = t["rounds"].select("demo_id", "round_num").join(
            pl.DataFrame({"t_s": range(40)}), how="cross").with_columns(wp_t=.2 + pl.col("t_s") / 100)
        # the synthetic WP only drifts with the clock; keep the raw change to test attribution
        events = export.winprob.action_values(t, wp, adjust_drift=False)
        assert str(ALIAS) not in events["steamid"].to_list()
        assert str(CANONICAL) in events["steamid"].to_list()
        return {"states": wp.drop("wp_t"), "oof": wp["wp_t"].to_numpy(), "wp": wp, "events": events,
                "metrics": {"model": {"accuracy": 1., "log_loss": 0.},
                            "baseline_alive_time": {"accuracy": .5}, "matches": 2}}

    monkeypatch.setattr(export.winprob, "run", check_winprob)
    monkeypatch.setattr(export, "hltv_demo_ids", lambda: set())
    monkeypatch.setattr(export, "ACTIVE_POOL", {"de_test"})
    monkeypatch.setattr(export, "load_map", lambda _: MM)
    monkeypatch.setattr(export, "load_spot_names", lambda _: [])
    monkeypatch.setattr(export, "team_profiles", lambda *_: [])
    monkeypatch.setattr(export, "SHOWCASE_TEAMS", {"Red"})
    parsed, site = tmp_path / "parsed", tmp_path / "site"
    write_tables(tables, "synthetic", parsed)
    export.export_site(parsed, site)
    assert seen == ["winprob"]
    red = next(t for t in json.loads((site / "heatmap_teams.json").read_text()) if t["team"] == "Red")
    assert red["roster"] == [{"steamid": str(CANONICAL), "name": "red1", "color": 0, "rounds": 10}]
    heatmap = json.loads((site / "de_test/heatmaps/teams/red.json").read_text())
    assert set(heatmap["players"]) == {str(CANONICAL)}
    assert str(ALIAS) not in json.dumps(heatmap)
    players = json.loads((site / "de_test/players.json").read_text())
    red_players = [p for p in players if p["team"] == "Red"]
    assert len(red_players) == 1
    player = red_players[0]
    assert player["steamid"] == str(CANONICAL)
    assert player["rounds"]["total"] == player["T"]["radar_6d"]["rounds"] == player["T"]["wpa"]["rounds"] == 10
    assert player["T"]["wpa"]["per_round"] > 0
    replay_files = list((site / "de_test/replay").glob("*/*.json"))
    assert len(replay_files) == 10
    for path in replay_files:
        replay = json.loads(path.read_text())
        # Replay schemas expose display metadata and positional indices, not Steam IDs.
        assert sum(p["name"] == "p0" for p in replay["players"]) == 1
        kill = next(e for e in replay["events"] if e["kind"] == "kill")
        assert replay["players"][kill["by"]]["name"] == "p0"
    assert all(str(ALIAS) not in path.read_text() for path in site.rglob("*.json"))
    assert ALIAS in pl.read_parquet(parsed / "player_rounds/synthetic.parquet")["steamid"].to_list()
