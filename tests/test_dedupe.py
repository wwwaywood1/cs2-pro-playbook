"""Cross-source identity and export filtering, using synthetic parsed tables."""
import json

import polars as pl
import pytest

from playbook.dedupe import deduplicate_tables, hltv_demo_ids, match_signature


def game(demo_id="archive", sequence=("Falcons", "Spirit", "Falcons"), **updates):
    match = dict(demo_id=demo_id, map="de_mirage", team_a="Falcons", team_b="Spirit",
                 score_a=2, score_b=1, n_rounds=3, tick_rate=64.)
    match.update(updates)
    rounds = pl.DataFrame({"demo_id": [demo_id] * len(sequence),
                           "round_num": list(range(1, len(sequence) + 1)),
                           "winner_team": sequence, "dur_s": [30.] * len(sequence),
                           "end_tick": [6400 * i for i in range(1, len(sequence) + 1)]})
    return match, rounds


def test_signature_ignores_source_ids_ticks_row_order_and_team_order():
    m, r = game()
    other, rr = game("hltv", ("Team Falcons", "Team Spirit", "Team Falcons"),
                     team_a="Team Spirit", team_b="Team Falcons", score_a=1, score_b=2,
                     hltv_match_id=123)
    rr = rr.with_columns(end_tick=pl.col("end_tick") + 99999, dur_s=pl.lit(31.)).reverse()
    assert match_signature(m, r) is not None
    assert match_signature(m, r) == match_signature(other, rr)


def test_same_score_different_round_sequence_is_a_different_match():
    m, r = game()
    other, rr = game("other", ("Spirit", "Falcons", "Falcons"))
    assert match_signature(m, r) != match_signature(other, rr)


def test_side_winners_resolve_to_teams_across_halftime():
    m, r = game()
    rr = r.drop("winner_team").with_columns(
        ct_team=pl.Series(["Falcons", "Falcons", "Spirit"]),
        t_team=pl.Series(["Spirit", "Spirit", "Falcons"]),
        winner_side=pl.Series(["CT", "T", "T"]))
    assert match_signature(m, r) == match_signature(m, rr)


@pytest.mark.parametrize("updates", [{"map": "de_nuke"}, {"team_b": "Monte"}])
def test_map_and_opponent_are_part_of_identity(updates):
    m, r = game()
    other, rr = game(sequence=("Falcons", updates.get("team_b", "Spirit"), "Falcons"), **updates)
    assert match_signature(m, r) != match_signature(other, rr)


@pytest.mark.parametrize("damage", ["empty", "partial", "repeated", "unknown_team", "score", "missing_team"])
def test_incomplete_or_inconsistent_history_has_no_signature(damage):
    m, r = game()
    if damage == "empty":
        r = pl.DataFrame()
    elif damage == "partial":
        r = r.head(2)
    elif damage == "repeated":
        r = r.with_columns(round_num=pl.lit(1))
    elif damage == "unknown_team":
        r = r.with_columns(winner_team=pl.lit("Other"))
    elif damage == "score":
        m["score_a"] = 1
    else:
        m["team_a"] = None
    assert match_signature(m, r) is None


def test_missing_winners_fall_back_to_rounded_durations_and_team_aligned_score():
    m, r = game(sequence=(None, None, None))
    other = dict(m, team_a="Spirit", team_b="Falcons", score_a=1, score_b=2)
    rr = r.with_columns(dur_s=pl.lit(30.01), end_tick=pl.col("end_tick") + 90000)
    assert match_signature(m, r) is not None
    assert match_signature(m, r) == match_signature(other, rr)
    assert match_signature(m, r) != match_signature(m, r.with_columns(dur_s=pl.lit(40.)))
    assert match_signature(m, r) != match_signature(dict(m, score_a=1, score_b=2), r)
    assert match_signature(m, r.drop("dur_s", "end_tick")) is None


def test_end_tick_fallback_uses_tick_rate_and_rounding():
    m, r = game(sequence=(None, None, None))
    r = r.drop("dur_s")
    assert match_signature(m, r) is not None
    assert match_signature(m, r) == match_signature(m, r.with_columns(end_tick=pl.col("end_tick") + 1))
    assert match_signature(m, r) != match_signature(m, r.with_columns(end_tick=pl.col("end_tick") + 640))
    assert match_signature(dict(m, tick_rate=None), r) is None


def test_partial_winners_cannot_hide_conflicting_results():
    m, r = game(sequence=("Falcons", None, None))
    _, rr = game(sequence=("Spirit", None, None))
    assert match_signature(m, r) is not None
    assert match_signature(m, r) != match_signature(m, rr)


def table_set():
    games = [game("a"), game("z"), game("different", ("Spirit", "Falcons", "Falcons"))]
    return {"matches": pl.DataFrame([g[0] for g in games]),
            "rounds": pl.concat([g[1] for g in games]),
            **{name: pl.DataFrame({"demo_id": ["a", "z", "different"], "value": [1, 2, 3]})
               for name in ("players", "player_rounds", "team_rounds", "positions", "utility", "kills", "plants", "shots", "economy", "loadouts")},
            "metadata": pl.DataFrame({"version": [1]})}


@pytest.mark.parametrize("preferred,kept,dropped", [(set(), "a", "z"), ({"z"}, "z", "a"), ({"a", "z"}, "a", "z")])
def test_dedupe_filters_every_table_deterministically_without_mutating(preferred, kept, dropped):
    t = table_set()
    filtered, duplicates = deduplicate_tables(t, preferred_ids=preferred)
    assert duplicates == [{"map": "de_mirage", "demo_id": dropped, "kept_demo_id": kept}]
    for name, df in filtered.items():
        if "demo_id" in df.columns:
            assert set(df["demo_id"]) == {kept, "different"}
            assert set(t[name]["demo_id"]) == {"a", "z", "different"}
    reverse = {name: df.reverse() for name, df in t.items()}
    _, again = deduplicate_tables(reverse, preferred_ids=preferred)
    assert again == duplicates
    assert deduplicate_tables(filtered, preferred_ids=preferred)[1] == []
    assert filtered["metadata"].equals(t["metadata"])


def test_missing_signatures_never_deduplicate():
    t = table_set()
    t["rounds"] = pl.DataFrame()
    filtered, duplicates = deduplicate_tables(t)
    assert not duplicates
    assert filtered["matches"].height == 3


def test_hltv_preference_uses_raw_location_and_multipart_identity(tmp_path):
    for name in ("hltv/42-match/gotv-p1.dem", "hltv/42-match/gotv-p2.dem",
                 "hltv/other/GAME.DEM", "cs2povarchive/99-match/archive.dem"):
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
    assert hltv_demo_ids(tmp_path) == {"42_gotv", "GAME"}
    assert hltv_demo_ids(tmp_path / "missing") == set()


def test_export_deduplicates_before_all_aggregation(tmp_path, monkeypatch, capsys):
    from playbook import export
    from playbook.store import write_tables
    from test_export_lineups import synthetic_tables
    from test_tactics import MM

    t = synthetic_tables()
    # Two complete recordings with identical winners; event payloads differ.
    t = {name: df.with_columns(round_num=((pl.col("round_num") + 1) // 2).cast(pl.Int32))
         if "round_num" in df.columns else df for name, df in t.items()}
    t["matches"] = t["matches"].with_columns(team_a=pl.lit("Red"), team_b=pl.lit("Blue"),
                                            score_a=pl.lit(5), score_b=pl.lit(0), n_rounds=pl.lit(5))
    t["rounds"] = pl.DataFrame([{"demo_id": demo, "round_num": n, "winner_team": "Red"}
                                for demo in ("d0", "d1") for n in range(1, 6)])
    expected = {name: df.filter(pl.col("demo_id") == "d1") for name, df in t.items()}
    lineups, _ = export.build_lineups(expected, MM)
    # Check the earliest semantic processing boundary, then run real tactics,
    # lineups and heatmaps through the rest of the export.
    original_plants = export.round_plants

    def plants(filtered):
        for name, df in filtered.items():
            assert set(df["demo_id"]) == {"d1"}, name
        return original_plants(filtered)

    monkeypatch.setattr(export, "round_plants", plants)
    monkeypatch.setattr(export, "hltv_demo_ids", lambda: {"d1"})
    monkeypatch.setattr(export, "ACTIVE_POOL", {"de_test"})
    monkeypatch.setattr(export, "load_map", lambda _: MM)
    monkeypatch.setattr(export, "load_spot_names", lambda _: [])
    monkeypatch.setattr(export, "team_profiles", lambda *_: [])
    monkeypatch.setattr(export, "player_profiles", lambda *_: [])
    parsed, site = tmp_path / "parsed", tmp_path / "site"
    write_tables(t, "synthetic", parsed)
    export.export_site(parsed, site)
    assert "deduplicated 1 duplicate demos" in capsys.readouterr().out
    assert json.loads((site / "index.json").read_text())["maps"][0]["n_matches"] == 1
    assert json.loads((site / "de_test/lineups.json").read_text()) == lineups
    assert pl.read_parquet(parsed / "matches/synthetic.parquet").height == 2
