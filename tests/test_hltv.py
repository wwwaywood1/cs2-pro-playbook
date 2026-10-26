from pathlib import Path

from playbook import hltv

FIX = Path(__file__).parent / "fixtures" / "hltv"
CFG = hltv.load_config()


def test_parse_results_rows_stars_and_featured_duplicate():
    rows = hltv.parse_results((FIX / "results.html").read_text())
    ids = [r.match_id for r in rows]
    assert ids.count(2399731) == 1                      # featured copy without a date is dropped
    g2 = next(r for r in rows if r.match_id == 2399731)
    assert g2.unix_ms == 1792933200000 and g2.stars == 3 and g2.fmt == "bo3"
    assert g2.teams == ["G2", "Aurora"] and g2.event == "PGL Masters Bucharest 2026" and g2.score == "0-2"
    big = next(r for r in rows if r.match_id == 2396562)
    assert big.fmt == "cch" and big.stars == 2


def _result(mid, unix, event="PGL Masters Bucharest 2026", fmt="bo3"):
    return (f'<div class="result-con" data-zonedgrouping-entry-unix="{unix}">'
            f'<a href="/matches/{mid}/g2-vs-aurora-pgl-masters-bucharest-2026"><table><tr>'
            f'<td><div class="team">G2</div></td><td class="result-score">0 - 2</td><td><div class="team">Aurora</div></td>'
            f'<td><span class="event-name">{event}</span></td><td><div class="stars"><i></i><i></i></div>'
            f'<div class="map-text">{fmt}</div></td></tr></table></a></div>')


def test_featured_copy_never_replaces_the_dated_one_in_either_order():
    featured_first = hltv.parse_results(_result(1, 0) + _result(1, 1792933200000) + _result(2, 1792900000000))
    dated_first = hltv.parse_results(_result(1, 1792933200000) + _result(1, 0) + _result(2, 1792900000000))
    for rows in (featured_first, dated_first):
        assert [r.match_id for r in rows] == [1, 2]
        assert rows[0].unix_ms == 1792933200000
    only_featured = hltv.parse_results(_result(3, 0) + _result(3, 0))
    assert [(r.match_id, r.unix_ms) for r in only_featured] == [(3, None)]


def test_parse_match_demo_date_maps():
    page = hltv.parse_match((FIX / "match.html").read_text())
    assert page.demo_id == 112905 and page.unix_ms == 1792323000000
    assert page.event == "Thunderpick World Championship 2026" and page.event_id == 8932
    assert page.teams == ["Aurora", "Falcons"] and page.maps_played == ["Anubis", "Dust2"]


def test_parse_team_roster_and_logo():
    team = hltv.parse_team((FIX / "team.html").read_text())
    assert team.name == "Aurora"
    assert team.logos and "teamlogo" in team.logos[0]
    assert [p["nick"] for p in team.roster] == ["XANTARES", "woxic"]
    assert team.roster[0]["status"] == "STARTER" and "playerbodyshot" in team.roster[0]["bodyshot"]


TIER1 = ["StarLadder StarSeries Fall 2026", "Thunderpick World Championship 2026", "ESL Pro League Season 24",
         "PGL Masters Bucharest 2026", "IEM Cologne Major 2026", "BLAST Open Porto 2026", "Esports World Cup 2026",
         "FISSURE Playground 3", "CS Asia Championships 2026"]
NOT_TIER1 = ["Thunderpick World Championship 2026 North America Series", "ESL Pro League Season 24 Conference",
             "BLAST Premier All-Star Showcase", "StarLadder StarSeries Fall 2026 Europe Closed Qualifier",
             "Digital Crusade DraculaN Season 6", "CCT Season 3 Europe Series 12"]


def test_tier1_filter():
    assert [e for e in TIER1 if not hltv.is_tier1(e, CFG)] == []
    assert [e for e in NOT_TIER1 if hltv.is_tier1(e, CFG)] == []


def test_terms_start_at_a_word():
    assert hltv.has_term("CCT Season 3 Europe Series 12", "Series")
    assert not hltv.has_term("StarLadder StarSeries Fall 2026", "Series")
    assert hltv.has_term("ESL Pro League Season 23 Qualifiers", "qualifier")


def test_slug_prefixes_and_archive_matching():
    assert "iem-cologne-major-2026-aurora-vs-spirit" in hltv.slug_prefixes("aurora-vs-spirit-iem-cologne-major-2026")
    keys = hltv.archive_keys(["iem-cologne-major-2026-aurora-vs-spirit-bo3--Sux_g3FZEXx-GCHN3oYPP",
                              "esports-world-cup-2026-vitality-vs-100-thieves-nuke-xgmnZlKoCUg1rSdM6g5Q-g"])
    assert keys[("iem-cologne-major-2026-aurora-vs-spirit", "bo3")] == 1
    assert keys[("esports-world-cup-2026-vitality-vs-100-thieves", "map")] == 1


def test_plan_orders_by_stars_then_recency_and_skips_known():
    rows = hltv.parse_results((FIX / "results.html").read_text())
    want, have, skipped, ambiguous = hltv.plan_matches(
        rows, ["iem-cologne-major-2026-aurora-vs-spirit-bo3--Sux_g3FZEXx-GCHN3oYPP"], since="2026-01-01", cfg=CFG)
    assert [r.match_id for r in have] == [2394977]
    assert [r.match_id for r in skipped] == [2396053]          # closed qualifier
    assert [r.match_id for r in want] == [2399731, 2396562]    # 3 stars first, then 2
    assert all(r.unix_ms >= 1767225600000 for r in want)       # 2025 match excluded by --since
    assert ambiguous == []


def test_plan_skips_known_match_ids():
    rows = hltv.parse_results((FIX / "results.html").read_text())
    plan = hltv.plan_matches(rows, [], since="2026-01-01", cfg=CFG, known_ids={2399731})
    assert 2399731 in [r.match_id for r in plan.have] and 2399731 not in [r.match_id for r in plan.want]


def _row(mid, unix_ms, fmt="bo3", slug="aurora-vs-spirit-iem-cologne-major-2026"):
    return hltv.ResultRow(mid, slug, unix_ms, 3, "IEM Cologne Major 2026", fmt, ["Aurora", "Spirit"], "2-1")


BO3 = "iem-cologne-major-2026-aurora-vs-spirit-bo3--Sux_g3FZEXx-GCHN3oYPP"
BO3_B = "iem-cologne-major-2026-aurora-vs-spirit-bo3-Zz9_k2LmQpRs7TuVwXy0"


def test_rematch_with_fewer_archives_than_matches_is_ambiguous():
    final, groups = _row(2, 1781395131000), _row(1, 1781295131000)     # same event, teams, format
    plan = hltv.plan_matches([final, groups], [BO3], since="2026-01-01", cfg=CFG)
    assert plan.have == [] and plan.want == []
    assert [r.match_id for r in plan.ambiguous] == [2, 1]
    # an archive and its extracted folder (same stem) are one archive, not two
    plan = hltv.plan_matches([final, groups], [BO3, BO3], since="2026-01-01", cfg=CFG)
    assert [r.match_id for r in plan.ambiguous] == [2, 1]
    # one archive per match: both are had
    plan = hltv.plan_matches([final, groups], [BO3, BO3_B], since="2026-01-01", cfg=CFG)
    assert [r.match_id for r in plan.have] == [2, 1] and plan.ambiguous == []


def test_rematch_counts_matches_outside_the_date_window():
    inside, before = _row(2, 1767400000000), _row(1, 1767100000000)    # 2026-01-03 and 2025-12-30
    plan = hltv.plan_matches([inside, before], [BO3], since="2026-01-01", cfg=CFG)
    assert [r.match_id for r in plan.ambiguous] == [2] and plan.have == []


def test_registered_match_id_settles_a_rematch():
    final, groups = _row(2, 1781395131000), _row(1, 1781295131000)
    # the one archive is registered to match 1, so the caller leaves its stem out
    plan = hltv.plan_matches([final, groups], [], since="2026-01-01", cfg=CFG, known_ids={1})
    assert [r.match_id for r in plan.have] == [1] and [r.match_id for r in plan.want] == [2]


def test_a_match_listed_twice_is_one_match():
    row = _row(2, 1781395131000)
    plan = hltv.plan_matches([row, row], [BO3], since="2026-01-01", cfg=CFG)
    assert [r.match_id for r in plan.have] == [2] and plan.ambiguous == []


def test_bo1_and_single_map_are_the_same_format():
    assert hltv.format_key("bo1") == hltv.format_key("nuke") == hltv.format_key("cch") == "map"
    assert hltv.format_key("bo3") == "bo3" and hltv.format_key("") == ""
    map_archive = "iem-cologne-major-2026-aurora-vs-spirit-nuke-xgmnZlKoCUg1rSdM6g5Q-g"
    bo1_archive = "iem-cologne-major-2026-aurora-vs-spirit-bo1-xgmnZlKoCUg1rSdM6g5Q-g"
    assert hltv.plan_matches([_row(5, 1781295131000, fmt="bo1")], [map_archive], since="2026-01-01", cfg=CFG).have
    assert hltv.plan_matches([_row(5, 1781295131000, fmt="nuke")], [bo1_archive], since="2026-01-01", cfg=CFG).have
    assert hltv.plan_matches([_row(5, 1781295131000, fmt="nuke")], [BO3], since="2026-01-01", cfg=CFG).want


def test_queue_text():
    assert hltv.queue_text([{"demo_id": 113185, "hltv_match_id": 2399731},
                            {"demo_id": 1, "hltv_match_id": 2}]) == "113185 2399731\n1 2\n"
