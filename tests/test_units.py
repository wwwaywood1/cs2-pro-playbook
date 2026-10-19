"""Fast tests for pure functions (no demo needed)."""

from pathlib import Path

from playbook.config import load_map, team_slug
from playbook.fetch import group_games, select
from playbook.parse import demo_identity, half_of
from playbook.semantics import densest_window, lane_shape


def test_lane_shape_orders_lanes():
    assert lane_shape(["B", "A", "MID", "MID", "A"]) == "A2 M2 B1"
    assert lane_shape(["T_SPAWN", "CT_SPAWN"]) == "S1 C1"
    assert lane_shape([]) is None


def test_densest_window():
    n, start, lane = densest_window([16, 40, 41, 42, 49, 80], ["A", "B", "B", "B", "A", "A"], width=10)
    assert (n, start, lane) == (4, 40, "B")


def test_half_of_regulation_and_overtime():
    assert [half_of(r) for r in (1, 12, 13, 24)] == [1, 1, 2, 2]
    assert [half_of(r) for r in (25, 27, 28, 30, 31)] == [3, 3, 4, 4, 5]


FILES = [
    ("iem_cologne_major_2026/2394983-vitality-vs-mouz-iem-cologne-major/vitality-vs-mouz-m1-mirage.dem", 469),
    ("iem_cologne_major_2026/2394983-vitality-vs-mouz-iem-cologne-major/vitality-vs-mouz-m2-dust2-p1.dem", 271),
    ("iem_cologne_major_2026/2394983-vitality-vs-mouz-iem-cologne-major/vitality-vs-mouz-m2-dust2-p2.dem", 177),
    ("iem_cologne_major_2026/2394983-vitality-vs-mouz-iem-cologne-major/vitality-vs-mouz-m3-inferno.dem", 391),
    ("iem_cologne_major_2026/2394998-g2-vs-spirit-iem-cologne-major/g2-vs-spirit-m1-overpass(1).dem", 513),
    ("iem_cologne_major_2026/2394998-g2-vs-spirit-iem-cologne-major/g2-vs-spirit-m1-overpass.dem", 513),
    ("iem_cologne_major_2026/2394904-the-mongolz-vs-betboom-iem-cologne-major/the-mongolz-vs-betboom-m2-mirage.dem", 363),
    ("cac2026/2394202-pain-vs-m80/pain-vs-m80-mirage.dem", 427),
    ("README.md", 28),
]


def test_group_games_layout_multipart_and_duplicates():
    games, unmatched = group_games(FILES)
    by_key = {g.key: g for g in games}
    assert unmatched == []
    assert len(games) == 6  # dust2 p1+p2 is one game, "(1)" duplicate dropped
    dust2 = by_key["2394983-m2-dust2"]
    assert dust2.multipart and dust2.bytes == 448
    mongolz = by_key["2394904-m2-mirage"]
    assert (mongolz.team1, mongolz.team2, mongolz.event) == ("the-mongolz", "betboom", "iem_cologne_major_2026")
    assert by_key["2394202-m1-mirage"].map_no == 1  # no -mN means a single-map match


def test_select_batch_and_extras():
    games, _ = group_games(FILES)
    targets = {"events": ["iem_cologne_major_2026"], "maps": ["mirage", "inferno"], "max_demos": 2,
               "extra_one_per_map": ["dust2", "overpass"]}
    main, extra = select(games, targets)
    assert [g.key for g in main] == ["2394983-m1-mirage", "2394983-m3-inferno"]  # newest first, cap 2
    assert [g.key for g in extra] == ["2394998-m1-overpass"]  # multipart dust2 skipped
    teams_only = select(games, {**targets, "max_demos": 10, "teams": ["the-mongolz"]})[0]
    assert [g.key for g in teams_only] == ["2394904-m2-mirage"]


def test_demo_identity_from_dataset_tree_and_flat_names():
    tree = Path("data/raw/cs2povarchive/iem_cologne_major_2026/2394983-vitality-vs-mouz-iem-cologne-major/vitality-vs-mouz-m1-mirage.dem")
    assert demo_identity(tree) == {"demo_id": "2394983_vitality-vs-mouz-m1-mirage", "hltv_match_id": 2394983}
    assert demo_identity(Path("2401337_vitality-vs-g2-inferno.dem"))["hltv_match_id"] == 2401337
    assert demo_identity(Path("hltv-de_mirage-2394170.dem")) == {"demo_id": "hltv-de_mirage-2394170", "hltv_match_id": None}


def test_cli_skips_multipart_files(tmp_path):
    from playbook.cli import _demo_paths

    d = tmp_path / "ev" / "1-a-vs-b"
    d.mkdir(parents=True)
    for name in ["a-vs-b-m1-mirage.dem", "a-vs-b-m2-nuke-p1.dem", "a-vs-b-m2-nuke-p2.dem", "a-vs-b-m3-dust2(1).dem"]:
        (d / name).write_bytes(b"")
    assert [p.name for p in _demo_paths([tmp_path])] == ["a-vs-b-m1-mirage.dem"]


def test_mirage_map_config():
    mm = load_map("de_mirage")
    assert mm.lane("BombsiteA") == "A" and mm.lane("Apartments") == "B" and mm.lane("TopofMid") == "MID"
    assert mm.lane("NotACallout") == "OTHER"
    # T spawn is on the right of the radar, CT spawn on the left
    assert mm.to_radar(1216, -115)[0] > mm.to_radar(-1656, -1896)[0]


def test_team_slug():
    assert team_slug("Team Vitality") == "team-vitality"
    assert team_slug("The MongolZ") == "the-mongolz"
