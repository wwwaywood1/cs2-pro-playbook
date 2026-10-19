"""Render heatmap panels for a player or team as a PNG (to check the data by eye).

    python scripts/heatmap_preview.py de_mirage --player donk [--phase early] [--out DIR]
    python scripts/heatmap_preview.py de_mirage --team spirit [--vs-baseline]

Rows: T side, CT side. Columns: presence, holding, shots, utility thrown, and the
combined view the site shows by default (presence + shots + utility, 1:1:1 on shares).
--vs-baseline draws the team's combined share minus the map average (red = more than
other teams, blue = less).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
from scipy.ndimage import gaussian_filter  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playbook.config import load_map  # noqa: E402
from playbook.heatmap import GRID, PHASES, build_heatmaps, combine, to_array  # noqa: E402
from playbook.store import read_all  # noqa: E402

RADARS = ROOT / "web" / "public" / "radars"
COLUMNS = [("presence", {"presence": 1}), ("holding", {"holding": 1}), ("shots", {"shots": 1}),
           ("util_throw", {"util_throw": 1}), ("combined 1:1:1", {"presence": 1, "shots": 1, "util_throw": 1})]


def merged_layers(entry: dict, side: str, phases: list[str]) -> dict[str, list]:
    """Sum the chosen phases into one sparse list per layer."""
    acc: dict[str, dict[int, float]] = {}
    for ph in phases:
        for layer, flat in entry["data"].get(side, {}).get(ph, {}).items():
            d = acc.setdefault(layer, {})
            for i in range(0, len(flat), 2):
                d[flat[i]] = d.get(flat[i], 0.0) + flat[i + 1]
    return {k: [x for c in sorted(v) for x in (c, v[c])] for k, v in acc.items()}


def draw_panel(ax, radar, grid: np.ndarray, title: str, diverging: bool = False) -> None:
    ax.imshow(radar, extent=(0, 1024, 1024, 0))
    g = gaussian_filter(grid, 1.2)
    if diverging:
        lim = np.abs(g).max() or 1
        rgba = plt.get_cmap("coolwarm")((g / lim + 1) / 2)
        rgba[..., 3] = np.clip(np.abs(g) / lim * 1.8, 0, 0.9)
        ax.imshow(rgba, extent=(0, 1024, 1024, 0), interpolation="bilinear")
    else:
        g = g / (g.max() or 1)
        rgba = plt.get_cmap("inferno")(g)
        rgba[..., 3] = np.clip(g * 1.6, 0, 0.9)
        ax.imshow(rgba, extent=(0, 1024, 1024, 0), interpolation="bilinear")
    ax.set_title(title, fontsize=9)
    ax.axis("off")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("map")
    ap.add_argument("--player")
    ap.add_argument("--team")
    ap.add_argument("--phase", choices=PHASES)
    ap.add_argument("--vs-baseline", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "heatmap_previews")
    a = ap.parse_args()

    t = read_all()
    ids = t["matches"].filter(pl.col("map") == a.map)["demo_id"].to_list()
    sub = {k: v.filter(pl.col("demo_id").is_in(ids)) for k, v in t.items() if "demo_id" in v.columns}
    mm = load_map(a.map)
    hm = build_heatmaps(sub, mm)
    if a.player:
        entry = next(p for p in hm["players"].values() if (p["name"] or "").lower() == a.player.lower())
        label = f"{entry['name']} ({entry['team']})"
    else:
        entry = hm["teams"][a.team.lower()]
        label = entry["team"]
    phases = [a.phase] if a.phase else list(PHASES)
    radar = plt.imread(RADARS / f"{a.map}.png")

    cols = COLUMNS + ([("vs other teams", None)] if a.vs_baseline else [])
    fig, axes = plt.subplots(2, len(cols), figsize=(4 * len(cols), 8.4), dpi=80)
    for r, side in enumerate(("T", "CT")):
        layers = merged_layers(entry, side, phases)
        for c, (name, weights) in enumerate(cols):
            ax = axes[r, c]
            if weights is None:
                base = merged_layers(hm["baseline"], side, phases)
                w = {"presence": 1, "shots": 1, "util_throw": 1}
                diff = combine(layers, w)[0] - combine(base, w)[0]
                draw_panel(ax, radar, diff, f"{side} · {name}", diverging=True)
                continue
            grid = combine(layers, weights)[0] if len(weights) > 1 else to_array(layers.get(name, []))[0]
            per_round = entry["per_round"].get(side, {}).get(a.phase or "all", {}).get(name)
            sub_title = f" · {per_round}/round" if per_round is not None else ""
            draw_panel(ax, radar, grid, f"{side} · {name}{sub_title}")
    n = entry["rounds"]
    fig.suptitle(f"{a.map} · {label} · {entry['n_matches']} matches · T {n['T']} / CT {n['CT']} rounds"
                 f" · phase: {a.phase or 'all'}", fontsize=12)
    a.out.mkdir(parents=True, exist_ok=True)
    name = (a.player or a.team).lower().replace(" ", "-")
    path = a.out / f"{a.map}_{name}_{a.phase or 'all'}{'_vs' if a.vs_baseline else ''}.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    print(path)


if __name__ == "__main__":
    main()
