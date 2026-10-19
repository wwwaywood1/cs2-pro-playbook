"""Draw one round on the radar, for checking tactic labels by eye.

    python scripts/storyboard.py de_mirage 2394848_nrg-vs-flyquest-mirage 7 [--labels] [--out DIR]
    python scripts/storyboard.py --sample de_mirage 12 --seed 1 [--labels] [--out DIR]

Shows the T side's paths (dots coloured by round time, X = death), the plant, every T
grenade (marker by type, label = pop time in seconds), and CT positions at 15 s (squares).
Without --labels the title carries only the round id, so a human can label the round
blind (see scripts/validate_m2.py); with --labels it adds what playbook.tactics found.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import polars as pl  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playbook.config import load_map  # noqa: E402
from playbook.store import read_all  # noqa: E402

RADARS = ROOT / "web" / "public" / "radars"
MARK = {"smoke": ("o", "#9e9e9e", 140), "molotov": ("^", "#ff6d00", 90), "flashbang": ("*", "#ffd600", 120),
        "he": ("D", "#00c853", 60)}
COLORS = ["#e53935", "#8e24aa", "#fb8c00", "#43a047", "#00acc1"]


def load_map_tables(map_name: str) -> dict[str, pl.DataFrame]:
    t = read_all()
    ids = t["matches"].filter(pl.col("map") == map_name)["demo_id"].to_list()
    return {k: v.filter(pl.col("demo_id").is_in(ids)) for k, v in t.items() if "demo_id" in v.columns}


def draw(sub: dict[str, pl.DataFrame], map_name: str, demo_id: str, rnd: int, out: Path,
         title_extra: str | None = None) -> Path:
    mm = load_map(map_name)
    key = (pl.col("demo_id") == demo_id) & (pl.col("round_num") == rnd)
    pos = sub["positions"].filter(key)
    tr = sub["team_rounds"].filter(key & (pl.col("side") == "T")).row(0, named=True)
    end_s = tr["dur_s"]

    fig, ax = plt.subplots(figsize=(9, 9), dpi=100)
    img = RADARS / f"{map_name}.png"
    if img.exists():
        ax.imshow(plt.imread(img), extent=(0, 1024, 1024, 0))
    ax.set_xlim(0, 1024)
    ax.set_ylim(1024, 0)
    ax.axis("off")

    t = pos.filter((pl.col("side") == "T") & (pl.col("t_s") >= 0) & (pl.col("t_s") <= end_s)).sort("steamid", "t_s")
    for i, (sid, p) in enumerate(t.group_by("steamid", maintain_order=True)):
        alive = p.filter(pl.col("alive"))
        rx, ry = mm.to_radar(alive["x"].to_numpy(), alive["y"].to_numpy())
        col = COLORS[i % len(COLORS)]
        ax.plot(rx, ry, "-", color=col, lw=1.2, alpha=0.8)
        sc = ax.scatter(rx, ry, c=alive["t_s"].to_numpy(), cmap="viridis", vmin=0, vmax=115, s=10, zorder=3)
        if len(rx):
            ax.text(rx[0], ry[0], alive["name"][0][:8], color=col, fontsize=7, weight="bold")
            if alive.height < p.height:  # died
                ax.scatter([rx[-1]], [ry[-1]], marker="x", color=col, s=80, lw=2, zorder=4)
    fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.01, label="round time (s)")

    ct = pos.filter((pl.col("side") == "CT") & (pl.col("t_s") == 15) & pl.col("alive"))
    rx, ry = mm.to_radar(ct["x"].to_numpy(), ct["y"].to_numpy())
    ax.scatter(rx, ry, marker="s", facecolor="none", edgecolor="#2196f3", s=70, lw=2, zorder=4, label="CT @15s")

    u = sub["utility"].filter(key & (pl.col("thrower_side") == "T") & ~pl.col("is_post_round") & pl.col("land_x").is_not_null())
    for r in u.iter_rows(named=True):
        if r["type"] not in MARK:
            continue
        m, c, s = MARK[r["type"]]
        x, y = mm.to_radar(r["land_x"], r["land_y"])
        ax.scatter([x], [y], marker=m, color=c, s=s, edgecolor="black", lw=0.6, zorder=5)
        ax.text(x + 6, y - 4, f"{r['pop_t_s']:.0f}", fontsize=7, color="white",
                bbox={"facecolor": "black", "alpha": 0.5, "pad": 0.5, "lw": 0})

    plants = sub["plants"].filter(key)
    for r in plants.iter_rows(named=True):
        x, y = mm.to_radar(r["x"], r["y"])
        ax.scatter([x], [y], marker="P", color="red", s=220, edgecolor="white", lw=1.5, zorder=6)
        ax.text(x + 8, y + 14, f"plant {r['t_s']:.0f}s", color="red", fontsize=9, weight="bold")

    title = f"{map_name} {demo_id} r{rnd}  T={tr['team']}  ({'won' if tr['won'] else 'lost'}, {tr['buy_type']}, {end_s:.0f}s)"
    if title_extra:
        title += "\n" + title_extra
    ax.set_title(title, fontsize=9)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{demo_id}_r{rnd:02d}.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def label_text(plan: dict) -> str:
    bits = [f"tempo={plan['tempo']}", f"commit={plan['commit_s']}", f"target={plan['target']}",
            f"split={plan['split']}({plan['n_directions']})", f"lurk={plan['lurker_name']}",
            f"fake={plan['fake_from']}", f"recipe={plan.get('recipe_id')}"]
    return "  ".join(bits)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("args", nargs="+")
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--labels", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "storyboards")
    a = ap.parse_args()
    map_name = a.args[0]
    sub = load_map_tables(map_name)
    plans = None
    if a.labels:
        from playbook.export import build_lineups
        from playbook.tactics import analyse_map

        mm = load_map(map_name)
        plans = analyse_map(sub, mm, build_lineups(sub, mm)[1])["plans"]
    if a.sample:
        n = int(a.args[1])
        gun = sub["team_rounds"].filter((pl.col("side") == "T") & pl.col("buy_type").is_in(["full", "force"]))
        rows = sorted(gun.select("demo_id", "round_num").iter_rows())
        targets = random.Random(a.seed).sample(rows, n)
    else:
        targets = [(a.args[1], int(a.args[2]))]
    for demo_id, rnd in targets:
        extra = None
        if plans is not None:
            extra = label_text(plans.filter((pl.col("demo_id") == demo_id) & (pl.col("round_num") == rnd)).row(0, named=True))
        print(draw(sub, map_name, demo_id, rnd, a.out, extra))


if __name__ == "__main__":
    main()
