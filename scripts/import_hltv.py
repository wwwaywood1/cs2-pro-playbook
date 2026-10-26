"""Import manually downloaded HLTV demos without parsing match events.

Run with the repository's venv: python scripts/import_hltv.py [--src DIR].
Archives are staged outside data/raw; only accepted demos are published. Loose
files are inspected in place and never removed, including rejected ones.

Cross-source content deduplication is performed by playbook export, before any
aggregation. Headers cannot identify a match's round-winner sequence; resolving
canonical winners also needs per-round team membership (see parse._resolve_teams).
Keep import header-only rather than decoding each download twice. Differently
named copies can be imported/parsed, but never counted twice in exported data.
"""
from __future__ import annotations

import argparse
import bz2
import gzip
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from awpy import Demo
from playbook.config import PARSED_DIR, RAW_DIR
from playbook.export import ACTIVE_POOL
from playbook.multipart import DUPLICATE_RE, game_stem, ordered_paths
from playbook.parse import demo_identity

ARCHIVES = {".rar", ".zip", ".gz", ".bz2"}
RAR_HELP = "Cannot open RAR: install an extractor with `brew install sevenzip` (7z/7zz), then retry."


@dataclass
class Result:
    archive: str
    maps: set[str] = field(default_factory=set)
    imported: int = 0
    duplicate: int = 0
    skipped: int = 0
    failed: int = 0
    reasons: list[str] = field(default_factory=list)


def read_map(path: Path) -> str:
    """Read awpy's header only, using the parser's map field."""
    name = Demo(path).header.get("map_name")
    if not isinstance(name, str) or not name:
        raise ValueError("demo header has no map_name")
    return name


def _demos(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".dem"
                  and not p.name.startswith("._"))


def _safe_member(name: str) -> None:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or (path.parts and ":" in path.parts[0]):
        raise ValueError(f"unsafe archive member: {name}")


class DamagedArchive(ValueError):
    """Every available extractor failed: an incomplete download, a damaged or an unsafe archive."""


def extract_archive(archive: Path, stage: Path) -> Path:
    """Try native extractors in order, discarding each failed attempt's files."""
    suffix = archive.suffix.lower()
    if suffix in {".gz", ".bz2"}:
        name = archive.stem
        if not name.lower().endswith(".dem"):
            name += ".dem"
        opener = gzip.open if suffix == ".gz" else bz2.open
        with opener(archive, "rb") as src, (stage / name).open("xb") as dst:
            shutil.copyfileobj(src, dst)
        return stage

    # Validate ZIP paths/links even when a native tool will do the extraction.
    if suffix == ".zip":
        try:
            zf = zipfile.ZipFile(archive)
        except zipfile.BadZipFile as exc:
            raise DamagedArchive(f"not a readable zip: {exc}") from exc
        with zf:
            for member in zf.infolist():
                _safe_member(member.filename)
                if stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError(f"archive symlink: {member.filename}")

    errors = []
    commands = [
        ("bsdtar", lambda dest: ["-xf", str(archive), "-C", str(dest)]),
        ("unar", lambda dest: ["-quiet", "-force-overwrite", "-no-directory", "-output-directory", str(dest), str(archive)]),
        ("7z", lambda dest: ["x", "-y", f"-o{dest}", str(archive)]),
    ]
    for tool, arguments in commands:
        executable = shutil.which(tool)
        if tool == "7z" and not executable:
            executable = shutil.which("7zz")  # Homebrew sevenzip names its binary 7zz.
        if not executable:
            continue
        dest = stage / tool
        dest.mkdir()
        try:
            # bsdtar's default extraction protections also reject escaping links.
            if tool == "bsdtar":
                listing = subprocess.run([executable, "-tf", str(archive)], capture_output=True, text=True)
                if listing.returncode:
                    raise ValueError(listing.stderr.strip() or "cannot list archive")
                for name in listing.stdout.splitlines():
                    _safe_member(name)
            proc = subprocess.run([executable, *arguments(dest)], capture_output=True, text=True)
            if proc.returncode:
                raise ValueError(proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}")
            for path in dest.rglob("*"):
                if path.is_symlink():
                    raise ValueError(f"archive symlink: {path.relative_to(dest)}")
            return dest
        except (OSError, ValueError) as exc:
            errors.append(f"{tool}: {str(exc).splitlines()[0]}")
            shutil.rmtree(dest)
    if suffix == ".zip":
        dest = stage / "zipfile"
        dest.mkdir()
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
        return dest
    if errors:
        raise DamagedArchive("; ".join(errors))
    raise ValueError(RAR_HELP)


def _groups(paths: list[Path]) -> list[list[Path]]:
    groups: dict[tuple[Path, str], list[Path]] = {}
    for path in paths:
        groups.setdefault((path.parent, game_stem(path)), []).append(path)
    return list(groups.values())


def _process(paths: list[Path], source: Path, destination: Path, seen: set[str],
             row: Result, *, in_place: bool = False, dry_run: bool = False) -> set[str]:
    """Count games, not recording parts; commit a multipart game as one unit."""
    accepted = set()
    for parts in _groups(paths):
        published: list[Path] = []
        try:
            parts = ordered_paths(parts)
            maps = {read_map(p) for p in parts}
            row.maps.update(maps)
            if len(maps) != 1:
                raise ValueError("multipart recordings have different maps")
            targets = [destination / p.relative_to(source).with_suffix(".dem") for p in parts]
            identity = demo_identity(targets[0])["demo_id"]
            if DUPLICATE_RE.search(parts[0].stem) or identity in seen:
                row.duplicate += 1
                continue
            if not maps <= ACTIVE_POOL:
                row.skipped += 1
                continue
            if not dry_run and not in_place:
                for src, target in zip(parts, targets):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    # Exclusive creation: a previous download is never overwritten.
                    with src.open("rb") as inp, target.open("xb") as out:
                        published.append(target)
                        shutil.copyfileobj(inp, out)
            seen.add(identity)
            accepted.add(identity)
            row.imported += 1
        except Exception as exc:
            for path in published:
                path.unlink()
            row.failed += 1
            row.reasons.append(f"{parts[0].name}: {exc}")
    return accepted


def print_summary(rows: list[Result]) -> None:
    print("archive -> maps found | imported | duplicate | skipped (map not in pool) | failed (reason)")
    for row in rows:
        print(f"{row.archive} -> {', '.join(sorted(row.maps)) or '?'} | {row.imported} | "
              f"{row.duplicate} | {row.skipped} | {row.failed}"
              + (" | " + "; ".join(row.reasons) if row.reasons else ""))
    if not rows:
        print("No supported downloads found directly under source directory.")


def import_downloads(src: Path = RAW_DIR / "hltv", *, parsed: Path = PARSED_DIR,
                     raw: Path = RAW_DIR, dry_run: bool = False,
                     delete_archives: bool = False) -> list[Result]:
    src = src.resolve()
    if not src.exists():
        print(f"Source does not exist: {src} (put HLTV downloads here).")
        return []
    if not src.is_dir():
        raise ValueError(f"Source is not a directory: {src}")
    inputs = sorted(p for p in src.iterdir() if p.is_file() and p.suffix.lower() in ARCHIVES | {".dem"}
                    and not p.name.startswith("._"))
    loose = [p for p in inputs if p.suffix.lower() == ".dem"]
    loose_set = set(loose)
    seen = {p.stem for p in parsed.glob("*/*.parquet")}
    for root in {src, raw.resolve()}:
        seen.update(demo_identity(p)["demo_id"] for p in _demos(root) if p not in loose_set)

    # Persist successful in-place imports so reruns also recognize loose files.
    manifest = src / ".import_hltv.json"
    registered = set()
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(data, list) or any(not isinstance(item, str) for item in data):
            raise ValueError(f"Invalid loose-demo registry: {manifest}")
        registered.update(data)
        seen.update(registered)
    loose_ids = registered.copy()
    rows = []
    for parts in _groups(loose):
        row = Result(" + ".join(p.name for p in parts))
        rows.append(row)
        loose_ids.update(_process(parts, src, src, seen, row, in_place=True, dry_run=dry_run))
        if dry_run:
            row.reasons.append("dry-run: loose demos would remain in place")
    if not dry_run and loose_ids != registered:
        # Atomic registry update; no download contents are modified.
        with tempfile.NamedTemporaryFile(mode="w", dir=src, prefix=".import_hltv-", delete=False) as handle:
            json.dump(sorted(loose_ids), handle)
        Path(handle.name).replace(manifest)

    # Archives imported without failures (including all-duplicate ones); lets
    # scripts/archive_downloads.py move them off the internal disk afterwards.
    processed_path = src / ".import_hltv_archives.json"
    processed = set(json.loads(processed_path.read_text(encoding="utf-8"))) if processed_path.exists() else set()
    processed_before = set(processed)
    for archive in inputs:
        if archive.suffix.lower() not in ARCHIVES:
            continue
        row = Result(archive.name)
        rows.append(row)
        destination = src / archive.stem
        if archive.name in processed and destination.is_dir():
            # imported before (e.g. downloaded twice): nothing to extract again
            row.reasons.append("already imported")
            continue
        if dry_run:
            row.reasons.append(f"dry-run: would extract to {destination}; map/duplicate checks deferred"
                               + ("; would delete archive only if import succeeds" if delete_archives else "; keep archive"))
            continue
        try:
            with tempfile.TemporaryDirectory(prefix="hltv-import-") as tmp:
                extracted = extract_archive(archive, Path(tmp))
                demos = _demos(extracted)
                if not demos:
                    raise ValueError("archive contains no .dem files")
                _process(demos, extracted, destination, seen, row)
            if not row.failed:
                processed.add(archive.name)
            if delete_archives and not row.failed:
                archive.unlink()
        except DamagedArchive as exc:
            # Incomplete or damaged download: set it aside so refresh doesn't retry it forever.
            row.failed += 1
            bad = src / ".bad"
            bad.mkdir(exist_ok=True)
            target = bad / archive.name
            if not target.exists():
                archive.replace(target)
            row.reasons.append(f"damaged or incomplete download, moved to {bad.name}/ - download it again "
                               f"({str(exc).splitlines()[0][:160]})")
        except Exception as exc:
            row.failed += 1
            row.reasons.append(str(exc))
    if not dry_run and processed != processed_before:
        with tempfile.NamedTemporaryFile(mode="w", dir=src, prefix=".import_hltv-", delete=False) as handle:
            json.dump(sorted(processed), handle)
        Path(handle.name).replace(processed_path)
    print_summary(rows)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=RAW_DIR / "hltv", help="directory of HLTV downloads")
    parser.add_argument("--dry-run", action="store_true", help="show the plan without extraction or writes")
    parser.add_argument("--delete-archives", action="store_true", help="delete archives after a failure-free import")
    args = parser.parse_args(argv)
    try:
        rows = import_downloads(args.src, dry_run=args.dry_run, delete_archives=args.delete_archives)
    except (OSError, ValueError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    return int(any(row.failed for row in rows))


if __name__ == "__main__":
    sys.exit(main())
