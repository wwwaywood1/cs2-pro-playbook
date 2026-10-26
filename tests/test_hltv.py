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


def test_tier1_filter():
    assert hltv.is_tier1("IEM Cologne Major 2026", CFG)
    assert hltv.is_tier1("PGL Masters Bucharest 2026", CFG)
    assert not hltv.is_tier1("StarLadder StarSeries Fall 2026 Europe Closed Qualifier", CFG)
    assert not hltv.is_tier1("Digital Crusade DraculaN Season 6", CFG)


def test_slug_prefixes_and_archive_matching():
    assert "iem-cologne-major-2026-aurora-vs-spirit" in hltv.slug_prefixes("aurora-vs-spirit-iem-cologne-major-2026")
    keys = hltv.archive_keys(["iem-cologne-major-2026-aurora-vs-spirit-bo3--Sux_g3FZEXx-GCHN3oYPP",
                              "esports-world-cup-2026-vitality-vs-100-thieves-nuke-xgmnZlKoCUg1rSdM6g5Q-g"])
    assert keys[("iem-cologne-major-2026-aurora-vs-spirit", "bo3")] == 1
    assert keys[("esports-world-cup-2026-vitality-vs-100-thieves", "map")] == 1


def test_plan_orders_by_stars_then_recency_and_skips_known():
    rows = hltv.parse_results((FIX / "results.html").read_text())
    want, have, skipped = hltv.plan_matches(
        rows, ["iem-cologne-major-2026-aurora-vs-spirit-bo3--Sux_g3FZEXx-GCHN3oYPP"], since="2026-01-01", cfg=CFG)
    assert [r.match_id for r in have] == [2394977]
    assert [r.match_id for r in skipped] == [2396053]          # closed qualifier
    assert [r.match_id for r in want] == [2399731, 2396562]    # 3 stars first, then 2
    assert all(r.unix_ms >= 1767225600000 for r in want)       # 2025 match excluded by --since


def test_download_script_is_valid_bash(tmp_path):
    import subprocess
    script = hltv.download_script("aurora", [{"demo_id": 113185, "hltv_match_id": 2399731}])
    path = tmp_path / "dl.sh"
    path.write_text(script)
    assert subprocess.run(["bash", "-n", str(path)]).returncode == 0
    assert "113185 2399731" in script and "/download/demo/$demo" in script
