"""Build the per-map callout tables (and the DeepSeek brief) from real demos.

    python scripts/make_map_briefs.py data/raw            # every demo under data/raw
    python scripts/make_map_briefs.py a.dem b.dem --brief # also write delegation/DS-05_map_configs.md
    python scripts/make_map_briefs.py --parsed de_nuke de_inferno   # from data/parsed, no re-parsing

For every map it writes delegation/inputs/<map>_callouts.csv with one row per in-game
place name (m_szLastPlaceName) seen during live rounds:

    callout, samples, x, y, z, radar_x, radar_y, t_when_a_plant, t_when_b_plant, ct_first_20s

- samples          player-seconds spent there (all players, live round time)
- x, y, z          median world position; radar_x/radar_y = pixel on the 1024x1024 radar
- t_when_a_plant   T player-seconds there in rounds that ended up planted on A
- t_when_b_plant   same for rounds planted on B
- ct_first_20s     CT player-seconds there in the first 20 s of a round (CT setup spots)

Those last three columns are what tells a reviewer which site a corridor leads to.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import polars as pl  # noqa: E402

from playbook.cli import _demo_paths  # noqa: E402
from playbook.config import load_map  # noqa: E402
from playbook.parse import parse_demo  # noqa: E402

INPUTS = ROOT / "delegation" / "inputs"
BRIEF = ROOT / "delegation" / "DS-05_map_configs.md"
TEMPLATE = ROOT / "delegation" / "templates" / "DS-05_header.md"


def collect(demos: list[Path]) -> dict[str, dict]:
    """map -> {"positions": [...], "plants": [...], "demos": [...]} from parsed demos."""
    out: dict[str, dict] = {}
    for path in demos:
        try:
            t = parse_demo(path)
        except Exception as exc:  # one bad demo should not stop the table
            print(f"  skipped {path.name}: {exc}")
            continue
        m = t["matches"]["map"][0]
        d = out.setdefault(m, {"positions": [], "plants": [], "demos": []})
        d["positions"].append(t["positions"])
        d["plants"].append(t["plants"])
        row = t["matches"].row(0, named=True)
        d["demos"].append(f"{row['team_a']} vs {row['team_b']} ({row['score_a']}-{row['score_b']}, {path.name})")
    return out


def collect_parsed(maps: list[str], parsed: Path = ROOT / "data" / "parsed") -> dict[str, dict]:
    """Same as collect() from the already parsed tables (every demo of each map in ``parsed``)."""
    matches = pl.concat([pl.read_parquet(f) for f in sorted((parsed / "matches").glob("*.parquet"))],
                        how="diagonal_relaxed")
    out: dict[str, dict] = {}
    for map_name in maps:
        rows = matches.filter(pl.col("map") == map_name).sort("demo_id")
        ids = rows["demo_id"].to_list()
        if not ids:
            print(f"  {map_name}: no parsed demos")
            continue
        cols = ["demo_id", "round_num", "side", "t_s", "x", "y", "z", "place", "alive"]
        out[map_name] = {
            "positions": [pl.read_parquet(parsed / "positions" / f"{i}.parquet", columns=cols) for i in ids],
            "plants": [pl.read_parquet(parsed / "plants" / f"{i}.parquet") for i in ids
                       if (parsed / "plants" / f"{i}.parquet").exists()],
            "demos": ids,
        }
    return out


def table(map_name: str, data: dict) -> pl.DataFrame:
    mm = load_map(map_name)
    pos = pl.concat(data["positions"], how="diagonal_relaxed").filter(pl.col("alive") & (pl.col("place") != ""))
    plants = (
        pl.concat(data["plants"], how="diagonal_relaxed")
        .sort("tick").group_by("demo_id", "round_num", maintain_order=True).agg(pl.col("site").first())
    )
    pos = pos.join(plants, on=["demo_id", "round_num"], how="left")
    t = (
        pos.group_by(pl.col("place").alias("callout"))
        .agg(
            samples=pl.len(),
            x=pl.col("x").median().round(0),
            y=pl.col("y").median().round(0),
            z=pl.col("z").median().round(0),
            t_when_a_plant=((pl.col("side") == "T") & (pl.col("site") == "A")).sum(),
            t_when_b_plant=((pl.col("side") == "T") & (pl.col("site") == "B")).sum(),
            ct_first_20s=((pl.col("side") == "CT") & (pl.col("t_s") <= 20)).sum(),
        )
        .with_columns(
            radar_x=((pl.col("x") - mm.radar["pos_x"]) / mm.radar["scale"]).round(0).cast(pl.Int32),
            radar_y=((mm.radar["pos_y"] - pl.col("y")) / mm.radar["scale"]).round(0).cast(pl.Int32),
        )
        .sort("x")
    )
    return t.select("callout", "samples", "x", "y", "z", "radar_x", "radar_y",
                    "t_when_a_plant", "t_when_b_plant", "ct_first_20s")


def markdown_table(df: pl.DataFrame) -> str:
    cols = df.columns
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.iter_rows():
        lines.append("| " + " | ".join("" if v is None else (f"{v:g}" if isinstance(v, float) else str(v)) for v in row) + " |")
    return "\n".join(lines)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--parsed" in sys.argv:
        data = collect_parsed(args)
    else:
        data = collect(_demo_paths([Path(a) for a in args] or [ROOT / "data" / "raw"]))
    INPUTS.mkdir(parents=True, exist_ok=True)
    sections = []
    for map_name in sorted(data):
        df = table(map_name, data[map_name])
        out = INPUTS / f"{map_name}_callouts.csv"
        df.write_csv(out)
        print(f"{map_name}: {df.height} callouts from {len(data[map_name]['demos'])} demo(s) -> {out.relative_to(ROOT)}")
        mm = load_map(map_name)
        sections.append(
            f"### {mm.display_name}（`{map_name}`）\n\n"
            f"- 来源 demo：{'；'.join(data[map_name]['demos'])}\n"
            f"- 输入表：`delegation/inputs/{map_name}_callouts.csv`（共 {df.height} 个点位，下表与之相同）\n"
            f"- 要改的文件：`config/maps/{map_name}.toml`；`web/src/i18n/zh.json` 和 `web/src/i18n/en.json` 里的 `callout.{map_name}`\n"
            f"- 雷达图（核对位置用）：`web/public/radars/{map_name}.png`，表中 radar_x / radar_y 是这张 1024×1024 图上的像素坐标\n\n"
            + markdown_table(df) + "\n"
        )
    if "--brief" in sys.argv and sections:
        header = TEMPLATE.read_text(encoding="utf-8")
        maps = ", ".join(f"`{m}`" for m in sorted(data))
        BRIEF.write_text(
            header.replace("{MAPS}", maps).replace("{MAP_ARGS}", " ".join(sorted(data)))
            + "\n## 各地图输入\n\n" + "\n".join(sections),
            encoding="utf-8",
        )
        print(f"brief -> {BRIEF.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
