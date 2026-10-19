"""Command line entry point.

    python -m playbook fetch --dry-run         # list demos matching config/targets.toml
    python -m playbook fetch                   # download them into data/raw/
    python -m playbook parse data/raw          # demos -> data/parsed/<table>/*.parquet
    python -m playbook relabel                 # re-apply config/maps/*.toml to parsed tables
    python -m playbook export                  # parsed tables -> data/site/*.json
    python -m playbook run                     # parse data/raw + export
    python -m playbook callouts some.dem       # list callout names (to write config/maps/*.toml)
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from playbook.config import PARSED_DIR, RAW_DIR, SITE_DIR


def _demo_paths(inputs: list[Path]) -> list[list[Path]]:
    """Group one game's parts in numeric order; ignore duplicate uploads.

    Explicit part paths select that game and discover its sibling parts too.
    Overlapping input directories/files do not duplicate a parse.
    """
    from playbook.multipart import DUPLICATE_RE, PART_RE, game_stem

    found = set()
    for p in inputs:
        if p.is_dir():
            found.update(p.rglob("*.dem"))
        elif p.suffix == ".dem" and not DUPLICATE_RE.search(p.stem):
            found.add(p)
            if PART_RE.search(p.stem):
                found.update(q for q in p.parent.glob("*.dem") if game_stem(q) == game_stem(p))
    groups = {}
    for p in sorted(found):
        if not DUPLICATE_RE.search(p.stem):
            p = p.resolve()
            groups.setdefault((p.parent, game_stem(p)), set()).add(p)

    # Validation belongs inside cmd_parse's per-game try block, so a missing
    # part rejects its game without preventing unrelated games from parsing.
    def number(p):
        match = PART_RE.search(p.stem)
        return int(match[1]) if match else 0

    return [sorted(paths, key=number) for paths in groups.values()]


def cmd_parse(inputs: list[Path], out: Path, force: bool) -> int:
    from playbook.config import load_team_aliases
    from playbook.parse import demo_identity, parse_demo
    from playbook.semantics import add_semantics
    from playbook.store import is_parsed, write_tables

    demos = _demo_paths(inputs)
    if not demos:
        print("no .dem files found", file=sys.stderr)
        return 1
    aliases = load_team_aliases()
    failed = 0
    for i, paths in enumerate(demos, 1):
        demo_id = demo_identity(paths[0])["demo_id"]
        if not force and is_parsed(demo_id, out):
            print(f"[{i}/{len(demos)}] {demo_id}: already parsed, skipping")
            continue
        print(f"[{i}/{len(demos)}] {'+'.join(p.name for p in paths)}")
        try:
            tables = add_semantics(parse_demo(paths, aliases))
            write_tables(tables, demo_id, out)
        except Exception:  # keep going: one bad demo shouldn't stop a batch
            failed += 1
            traceback.print_exc()
    print(f"done: {len(demos) - failed} ok, {failed} failed -> {out}")
    return 1 if failed else 0


def cmd_relabel(parsed: Path, maps: list[str]) -> int:
    """Re-apply the current map configs and rebuild the semantic tables, demo by demo."""
    import polars as pl

    from playbook.semantics import add_semantics, relabel
    from playbook.store import TABLES, write_tables

    files = sorted((parsed / "matches").glob("*.parquet"))
    n = 0
    for f in files:
        demo_id = f.stem
        m = pl.read_parquet(f)
        if maps and m["map"][0] not in maps:
            continue
        raw = {name: pl.read_parquet(parsed / name / f"{demo_id}.parquet")
               for name in TABLES if name not in ("team_rounds", "player_rounds")}
        write_tables(add_semantics(relabel(raw)), demo_id, parsed)
        n += 1
    print(f"relabelled {n} demo(s) in {parsed}")
    return 0


def cmd_export(parsed: Path, out: Path) -> int:
    from playbook.export import export_site

    export_site(parsed, out)
    return 0


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="playbook", description="CS2 pro demo -> tactics pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download demos listed by config/targets.toml")
    f.add_argument("--dry-run", action="store_true", help="only list what would be downloaded")
    f.add_argument("--out", type=Path, default=RAW_DIR)

    p = sub.add_parser("parse", help="parse demos into parquet tables")
    p.add_argument("inputs", type=Path, nargs="*", default=[RAW_DIR])
    p.add_argument("--out", type=Path, default=PARSED_DIR)
    p.add_argument("--force", action="store_true", help="re-parse demos that already have output")

    rl = sub.add_parser("relabel", help="re-apply config/maps/*.toml to parsed tables (no demo needed)")
    rl.add_argument("maps", nargs="*", help="only these maps, e.g. de_nuke (default: all)")
    rl.add_argument("--parsed", type=Path, default=PARSED_DIR)

    e = sub.add_parser("export", help="aggregate parsed tables into site JSON")
    e.add_argument("--parsed", type=Path, default=PARSED_DIR)
    e.add_argument("--out", type=Path, default=SITE_DIR)

    r = sub.add_parser("run", help="parse + export")
    r.add_argument("inputs", type=Path, nargs="*", default=[RAW_DIR])
    r.add_argument("--force", action="store_true")

    c = sub.add_parser("callouts", help="list callout names in a demo")
    c.add_argument("demo", type=Path)

    args = ap.parse_args(argv)
    if args.cmd == "fetch":
        from playbook.fetch import fetch

        fetch(dry_run=args.dry_run, out_dir=args.out)
        code = 0
    elif args.cmd == "parse":
        code = cmd_parse(args.inputs, args.out, args.force)
    elif args.cmd == "relabel":
        code = cmd_relabel(args.parsed, args.maps)
    elif args.cmd == "export":
        code = cmd_export(args.parsed, args.out)
    elif args.cmd == "run":
        code = cmd_parse(args.inputs, PARSED_DIR, args.force)
        code = cmd_export(PARSED_DIR, SITE_DIR) or code
    elif args.cmd == "callouts":
        import polars as pl

        from playbook.parse import list_callouts

        with pl.Config(tbl_rows=100):
            print(list_callouts(args.demo))
        code = 0
    sys.exit(code)
