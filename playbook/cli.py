"""Command line entry point.

    python -m playbook fetch --dry-run         # list demos matching config/targets.toml
    python -m playbook fetch                   # download them into data/raw/
    python -m playbook parse data/raw          # demos -> data/parsed/<table>/*.parquet
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


def _demo_paths(inputs: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in inputs:
        if p.is_dir():
            out.extend(sorted(p.glob("*.dem")))
        elif p.suffix == ".dem":
            out.append(p)
    return out


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
    for i, path in enumerate(demos, 1):
        demo_id = demo_identity(path)["demo_id"]
        if not force and is_parsed(demo_id, out):
            print(f"[{i}/{len(demos)}] {demo_id}: already parsed, skipping")
            continue
        print(f"[{i}/{len(demos)}] {path.name}")
        try:
            tables = add_semantics(parse_demo(path, aliases))
            write_tables(tables, demo_id, out)
        except Exception:  # keep going: one bad demo shouldn't stop a batch
            failed += 1
            traceback.print_exc()
    print(f"done: {len(demos) - failed} ok, {failed} failed -> {out}")
    return 1 if failed else 0


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
