"""Fast tests for pure functions (no demo needed)."""

from playbook.config import load_map, team_slug
from playbook.fetch import parse_remote_path, select
from playbook.parse import half_of
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


def test_parse_remote_path():
    d = parse_remote_path("data/2025/tier1/2401337/vitality-vs-g2-inferno.dem", ["inferno", "mirage"])
    assert (d.year, d.tier, d.match_id, d.team1, d.team2, d.map) == (2025, "tier1", "2401337", "vitality", "g2", "inferno")
    assert d.local_name == "2401337_vitality-vs-g2-inferno.dem"
    multi = parse_remote_path("data/2026/tier1/2399999/the-mongolz-vs-natus-vincere-mirage.dem", ["mirage"])
    assert (multi.team1, multi.team2) == ("the-mongolz", "natus-vincere")
    assert parse_remote_path("README.md", ["mirage"]) is None


def test_select_filters_and_caps():
    paths = [
        "data/2026/tier1/3/vitality-vs-g2-mirage.dem",
        "data/2026/tier1/2/foo-vs-bar-mirage.dem",
        "data/2026/tier2/1/vitality-vs-bar-mirage.dem",
        "data/2025/tier1/4/vitality-vs-g2-nuke.dem",
    ]
    remote = [parse_remote_path(p, ["mirage", "nuke"]) for p in paths]
    targets = {"years": [2026], "tiers": ["tier1"], "maps": ["mirage"], "teams": ["vitality"], "max_demos": 5}
    assert [d.match_id for d in select(remote, targets)] == ["3"]


def test_mirage_map_config():
    mm = load_map("de_mirage")
    assert mm.lane("BombsiteA") == "A" and mm.lane("Apartments") == "B" and mm.lane("TopofMid") == "MID"
    assert mm.lane("NotACallout") == "OTHER"
    # T spawn is on the right of the radar, CT spawn on the left
    assert mm.to_radar(1216, -115)[0] > mm.to_radar(-1656, -1896)[0]


def test_team_slug():
    assert team_slug("Team Vitality") == "team-vitality"
    assert team_slug("The MongolZ") == "the-mongolz"
