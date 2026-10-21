"""Render the team heatmap view as a PNG (a mock of the site page, for checking by eye).

    python scripts/heatmap_preview.py de_mirage spirit --side CT [--phase early] [--out DIR]

Draws one panel per view (presence, holding, fights, utility landing) with the team's
players overlaid in their colours (red, blue, purple, green, orange; light = little,
deep = a lot), plus a "who owns this area" panel. Reads data/site/<map>/heatmaps.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playbook.heatmap import PHASES, combine, merge_phases  # noqa: E402

RADARS = ROOT / "web" / "public" / "radars"
# light -> deep for each player colour (same values as web/src/heatmap.ts)
PALETTE = [
    ("#fecaca", "#b91c1c"),  # red
    ("#bfdbfe", "#1d4ed8"),  # blue
    ("#e9d5ff", "#7e22ce"),  # purple
    ("#bbf7d0", "#15803d"),  # green
    ("#fed7aa", "#c2410c"),  # orange
    ("#e5e7eb", "#4b5563"),  # extra players: grey
]
GAMMA = 0.6        # lift faint areas so all five players stay visible
ALPHA_FLOOR = 0.12  # below this share of the player's peak: transparent
VIEWS = [
    ("站位 presence", {"presence": 1}),
    ("驻守 holding", {"holding": 1}),
    ("交火 shots+kills+deaths", {"shots": 1, "kills": 1, "deaths": 1}),
    ("道具落点 smoke+flash+molotov+HE", {"smoke": 1, "flash": 1, "molotov": 1, "he": 1}),
]


def hex_rgb(h: str) -> np.ndarray:
    return np.array([int(h[i : i + 2], 16) for i in (1, 3, 5)]) / 255.0


def player_rgba(grid: np.ndarray, color: int) -> np.ndarray:
    """Light-to-deep shade of the player's colour; alpha grows with intensity."""
    light, deep = (hex_rgb(c) for c in PALETTE[min(color, len(PALETTE) - 1)])
    v = np.clip(grid / (grid.max() or 1), 0, 1) ** GAMMA
    rgb = light[None, None, :] * (1 - v[..., None]) + deep[None, None, :] * v[..., None]
    alpha = np.clip((v - ALPHA_FLOOR) * 1.6, 0, 0.9)
    return np.dstack([rgb, alpha])


def owner_rgba(stack: np.ndarray, colors: list[int]) -> np.ndarray:
    """Choose the largest value relative to each player's own peak, as on the site."""
    if not len(stack):
        return np.zeros((*stack.shape[1:], 4))
    peaks = stack.max(axis=(1, 2), keepdims=True)
    relative = np.divide(stack, peaks, out=np.zeros_like(stack), where=peaks > 0)
    owner = relative.argmax(0)
    top = relative.max(0)
    v = np.clip(top, 0, 1) ** GAMMA
    rgba = np.zeros((*owner.shape, 4))
    for i, color in enumerate(colors):
        light, deep = (hex_rgb(c) for c in PALETTE[min(color, len(PALETTE) - 1)])
        m = (owner == i) & (top > 0)
        rgba[m, :3] = light * (1 - v[m, None]) + deep * v[m, None]
    rgba[..., 3] = np.clip((v - ALPHA_FLOOR) * 1.6, 0, 0.85)
    return rgba


def blur_grid(grid: np.ndarray, sigma: float) -> np.ndarray:
    from scipy.ndimage import gaussian_filter
    if sigma <= 0:
        return grid.copy()
    return gaussian_filter(grid, sigma, mode="constant", radius=max(1, int(np.ceil(3 * sigma))))


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    ap = argparse.ArgumentParser()
    ap.add_argument("map")
    ap.add_argument("team")
    ap.add_argument("--side", choices=["T", "CT"], default="CT")
    ap.add_argument("--phase", choices=PHASES)
    ap.add_argument("--level", type=int, choices=(0, 1), default=0)
    ap.add_argument("--sigma", type=float, default=1.0)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "heatmap_previews")
    a = ap.parse_args()

    entry = json.loads((ROOT / "data" / "site" / a.map / "heatmaps" / "teams" / f"{a.team}.json").read_text())
    phases = [a.phase] if a.phase else list(PHASES)
    baseline = json.loads((ROOT / "data" / "site" / a.map / "heatmaps" / "baseline.json").read_text())
    levels = baseline["levels"]
    if a.level >= levels:
        ap.error("selected level is not available on this map")
    radar = plt.imread(RADARS / f"{a.map}{'_lower' if a.level else ''}.png")
    roster = [r for r in entry["roster"] if r["rounds"][a.side]]
    plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "WenQuanYi Zen Hei", "DejaVu Sans"]

    fig, grid_axes = plt.subplots(2, 3, figsize=(19, 13.6), dpi=80)
    axes = list(grid_axes.ravel())
    legend_ax = axes.pop(2)  # top-right slot holds the legend
    legend_ax.axis("off")
    for ax, (title, weights) in zip(axes, VIEWS):
        ax.imshow(radar, extent=(0, 1024, 1024, 0))
        for r in reversed(roster):  # first colour on top
            layers = merge_phases(entry["players"][r["steamid"]], a.side, phases)
            g = blur_grid(combine(layers, weights, levels)[a.level], a.sigma)
            ax.imshow(player_rgba(g, r["color"]), extent=(0, 1024, 1024, 0), interpolation="bilinear")
        ax.set_title(title, fontsize=14)
        ax.axis("off")

    # who owns each area: the player with the largest share of presence there
    ax = axes[-1]
    ax.imshow(radar, extent=(0, 1024, 1024, 0))
    stack = np.array([blur_grid(combine(merge_phases(entry["players"][r["steamid"]], a.side, phases),
                                              {"presence": 1}, levels)[a.level], a.sigma) for r in roster])
    if not roster:
        stack = np.zeros((0, baseline["grid"], baseline["grid"]))
    rgba = owner_rgba(stack, [r["color"] for r in roster])
    ax.imshow(rgba, extent=(0, 1024, 1024, 0), interpolation="nearest")
    ax.set_title("区域归属（站位最多的选手）", fontsize=14)
    ax.axis("off")

    handles = []
    for r in roster:
        s = entry["summary"].get(r["steamid"], {}).get(a.side, {})
        lane = s.get("main_lane", {}).get(a.phase or "early", {})
        hold = (s.get("holds") or [{}])[0]
        txt = f"{r['name']}  ({r['rounds'][a.side]} 回合)\n开局主要在 {lane.get('lane', '—')}"
        if hold:
            txt += f"\n最常驻守 {hold.get('place')}：{hold.get('seconds_per_round')} 秒/回合"
        handles.append(Patch(facecolor=PALETTE[min(r["color"], 5)][1], label=txt))
    legend_ax.legend(handles=handles, loc="center left", fontsize=13, frameon=False, labelspacing=1.4,
                     handlelength=2.2, handleheight=1.6)
    fig.suptitle(f"{entry['team']} · {a.map} · {a.side} 方 · {entry['n_matches']} 场 {entry['rounds'][a.side]} 个枪局"
                 f" · 阶段：{a.phase or '全部'}", fontsize=16)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / f"{a.map}_{a.team}_{a.side}_{a.phase or 'all'}.png"
    fig.savefig(path, bbox_inches="tight")
    print(path)


if __name__ == "__main__":
    main()
