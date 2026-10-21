"""Spot tables + radar images for naming landing spots (GPT-06 style), any maps.

    python scripts/spot_briefs.py de_nuke de_dust2 de_ancient de_anubis

Reads data/site/<map>/tactics.json and data/parsed/positions; writes
delegation/inputs/spots/<map>_T.png, <map>_CT.png and spots_to_name_<maps>.csv.
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import polars as pl  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playbook.config import load_map  # noqa: E402

OUT = ROOT / "delegation" / "inputs" / "spots"


def main(maps: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in maps:
        mm = load_map(m)
        t = json.loads((ROOT / "data" / "site" / m / "tactics.json").read_text())
        used = {}
        for r in t["recipes"]:
            for c in r["core"] + r["options"]:
                used.setdefault(c["spot_id"], []).append(f"{r['site']}:{r['id'].split('-')[-1]}")
        pos = pl.read_parquet(str(ROOT / "data" / "parsed" / "positions" / f"*{m[3:]}*.parquet"))
        cen = pos.filter(pl.col("alive")).group_by("place").agg(pl.col("x").median(), pl.col("y").median(), n=pl.len())
        cen = cen.filter(pl.col("n") > 2000)
        spots = [s for s in t["spots"] if s["type"] in ("smoke", "molotov")]
        for side in ("T", "CT"):
            fig, ax = plt.subplots(figsize=(16, 16), dpi=90)
            ax.imshow(plt.imread(ROOT / "web" / "public" / "radars" / f"{m}.png"), extent=(0, 1024, 1024, 0))
            for p, x, y, _ in cen.iter_rows():
                rx, ry = mm.to_radar(x, y)
                ax.text(rx, ry, p, fontsize=10, color="#00e5ff", ha="center", weight="bold")
            for s in spots:
                if s["side"] != side:
                    continue
                mk = "o" if s["type"] == "smoke" else "^"
                ax.scatter([s["radar_x"]], [s["radar_y"]], s=420 if mk == "o" else 180,
                           c="#e0e0e0" if mk == "o" else "#ff6d00", edgecolors="black", marker=mk, zorder=3)
                ax.text(s["radar_x"] + 10, s["radar_y"] + 14, s["spot_id"].split("-s")[-1], fontsize=12,
                        color="yellow", weight="bold", bbox={"facecolor": "black", "alpha": 0.65}, zorder=4)
            ax.set_title(f"{m} · {side} · grey = smoke, orange = molotov, number = short_id, cyan = callouts")
            ax.axis("off")
            fig.savefig(OUT / f"{m}_{side}.png", bbox_inches="tight")
            plt.close(fig)
        for s in spots:
            rows.append({"map": m, "spot_id": s["spot_id"], "short_id": s["spot_id"].split("-s")[-1],
                         "side": s["side"], "type": s["type"], "callout": s["place"], "x": s["x"], "y": s["y"],
                         "z": s["z"], "radar_x": s["radar_x"], "radar_y": s["radar_y"], "n_throws": s["n_throws"],
                         "n_matches": s["n_matches"], "median_pop_t_s": s["median_pop_t_s"],
                         "used_in_recipes": " ".join(used.get(s["spot_id"], [])), "en": "", "zh": ""})
    path = OUT / f"spots_to_name_{'_'.join(x[3:] for x in maps)}.csv"
    pl.DataFrame(rows).sort("map", "side", "type", "short_id").write_csv(path)
    print(f"{len(rows)} spots -> {path}")


if __name__ == "__main__":
    main(sys.argv[1:])
