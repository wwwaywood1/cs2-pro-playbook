"""Checked team facts (playbook/insights.py)."""

from playbook.insights import _compare, _z


def test_z_and_compare_thresholds():
    assert abs(_z(30, 50, 300, 1000)) > 4
    f = _compare("x", "T", 30, 50, 300, 1000, "快攻", "Fast hits")
    assert f["direction"] == "more" and f["value"] == 0.6 and f["baseline"] == 0.3
    assert "高于" in f["text"]["zh"] and "60%" in f["text"]["en"]
    assert _compare("x", "T", 17, 50, 300, 1000, "a", "b") is None  # 34% vs 30%: too small
    assert _compare("x", "T", 6, 10, 300, 1000, "a", "b") is None  # too few rounds
