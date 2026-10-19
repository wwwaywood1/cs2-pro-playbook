"""Compare tactic labels from playbook/tactics.py with the blind-labelled rounds.

    python scripts/validate_m2.py [--labels validation/m2_blind_labels.csv]

Labels were made by looking at storyboards (scripts/storyboard.py without --labels), so
they are a human reading of the same position data, not video ground truth. Empty label
cells are not scored; `split` and `lurk` are only scored on rounds with a commit.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playbook.config import load_map  # noqa: E402
from playbook.export import build_lineups  # noqa: E402
from playbook.store import read_all  # noqa: E402
from playbook.tactics import analyse_map  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=Path, default=ROOT / "validation" / "m2_blind_labels.csv")
    a = ap.parse_args()
    lab = pl.read_csv(a.labels, schema_overrides={"round_num": pl.Int32}).with_columns(
        pl.col("target", "split", "lurk", "fake").fill_null(""))
    t = read_all()
    plans = []
    for m in lab["map"].unique().sort().to_list():
        ids = t["matches"].filter(pl.col("map") == m)["demo_id"].to_list()
        sub = {k: v.filter(pl.col("demo_id").is_in(ids)) for k, v in t.items() if "demo_id" in v.columns}
        mm = load_map(m)
        plans.append(analyse_map(sub, mm, build_lineups(sub, mm)[1])["plans"].with_columns(map=pl.lit(m)))
    alg = pl.concat(plans, how="diagonal_relaxed").select(
        "map", "demo_id", "round_num", target_alg="target", tempo_alg="tempo", split_alg="split", lurk_alg="lurk",
        fake_alg="fake_from", attempt_alg="attempt", commit_s="commit_s")
    j = lab.join(alg, on=["map", "demo_id", "round_num"], how="left")
    checks = {
        "target": (pl.lit(True), pl.col("target") == pl.col("target_alg").fill_null("")),
        "tempo": (pl.col("tempo").is_not_null(), pl.col("tempo") == pl.col("tempo_alg")),
        "split": ((pl.col("split") != "") & pl.col("commit_s").is_not_null(), (pl.col("split") == "Y") == pl.col("split_alg")),
        "lurk": ((pl.col("lurk") != "") & pl.col("commit_s").is_not_null(), (pl.col("lurk") == "Y") == pl.col("lurk_alg")),
        "fake": (pl.lit(True), pl.col("fake") == pl.col("fake_alg").fill_null("")),
    }
    print(f"{lab.height} labelled rounds ({a.labels.name})")
    for name, (scored, ok) in checks.items():
        d = j.filter(scored).with_columns(ok=ok)
        print(f"  {name:7s} {int(d['ok'].sum())}/{d.height}")
        for r in d.filter(~pl.col("ok")).iter_rows(named=True):
            print(f"      x {r['demo_id']} r{r['round_num']}: label={r[name]!r} alg={r[name + '_alg']!r}"
                  f"  ({r.get('review') or r.get('note') or ''})")


if __name__ == "__main__":
    main()
