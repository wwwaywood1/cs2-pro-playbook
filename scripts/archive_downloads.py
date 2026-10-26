#!/usr/bin/env python3
"""Move imported HLTV download archives (.rar/.zip/...) off the internal disk.

    python scripts/archive_downloads.py            # dry run: list what would move
    python scripts/archive_downloads.py --apply    # copy, verify (SHA-256), then delete the original

After `scripts/import_hltv.py` has extracted an archive into ``data/raw/hltv/<stem>/``,
the archive itself is only a backup. This script moves such archives to the
directory configured in ``config/storage.toml`` (``[archive] dir``), e.g. an external
SSD. Demo identities come from the extracted folder names, never from the archive
files, so moving archives does not change any parsed data.

Safety: every file is copied to ``<name>.part``, flushed to the drive (F_FULLFSYNC on
macOS), re-read and compared by SHA-256 against the source before the source is
deleted. Interrupted runs resume. A manifest ``.archived.jsonl`` in the destination
records name, size and hash. When the destination already holds a different file with
the same name, both are kept and the archive is reported (resolve it by hand).

Nothing happens unless the destination is reachable: a ``/Volumes/<name>/...`` path
needs that volume mounted (the empty mount-point folder an unclean eject can leave
behind does not count); any other path must already exist as a directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import tomllib
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

ROOT = Path(__file__).resolve().parent.parent
ARCHIVES = (".rar", ".zip", ".gz", ".bz2", ".7z")
CHUNK = 8 << 20
VOLUMES = Path("/Volumes")


def load_dest(config: Path) -> Path | None:
    if not config.exists():
        return None
    data = tomllib.loads(config.read_text(encoding="utf-8"))
    value = (data.get("archive") or {}).get("dir")
    return Path(value).expanduser() if value else None


def volume_root(path: Path) -> Path | None:
    """``/Volumes/<name>`` when ``path`` is on an external volume, else None."""
    try:
        rel = Path(os.path.abspath(path)).relative_to(VOLUMES)
    except ValueError:
        return None
    return VOLUMES / rel.parts[0] if rel.parts else None


def destination_problem(dest: Path) -> str | None:
    """Why archives cannot be moved to ``dest`` right now; None when they can."""
    root = volume_root(dest)
    if root is not None:
        if not os.path.ismount(root):
            return f"Archive volume not mounted ({root}); skipping."
    elif not dest.is_dir():
        return f"Archive directory {dest} does not exist (create it first); skipping."
    return None


def flush_to_disk(fd: int) -> None:
    """fsync, and on macOS F_FULLFSYNC, which also makes the drive write out its own cache."""
    os.fsync(fd)
    if fcntl is not None and hasattr(fcntl, "F_FULLFSYNC"):
        try:
            fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
        except OSError:
            pass  # not supported by this filesystem; the fsync above still happened


def sync_dir(path: Path) -> None:
    """Make a rename inside ``path`` durable (best effort: not every filesystem allows it)."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        flush_to_disk(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def candidates(src: Path, imported_only: bool) -> list[Path]:
    """Archives that import_hltv.py already handled: extracted folder exists or the
    archive is listed in ``.import_hltv_archives.json`` (e.g. all maps were duplicates)."""
    registry = src / ".import_hltv_archives.json"
    processed = set(json.loads(registry.read_text(encoding="utf-8"))) if registry.exists() else set()
    out = []
    for p in sorted(src.iterdir()):
        if not p.is_file() or p.name.startswith(("._", ".")):
            continue
        if p.suffix.lower() not in ARCHIVES:
            continue
        if imported_only and not (src / p.stem).is_dir() and p.name not in processed:
            continue
        out.append(p)
    return out


def sha256_copy(src: Path, dst: Path) -> str:
    h = hashlib.sha256()
    with src.open("rb") as fi, dst.open("wb") as fo:
        while chunk := fi.read(CHUNK):
            h.update(chunk)
            fo.write(chunk)
        fo.flush()
        flush_to_disk(fo.fileno())
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def move_one(src: Path, dest_dir: Path, manifest: Path) -> tuple[str, int]:
    final = dest_dir / src.name
    size = src.stat().st_size
    if final.exists():
        other = final.stat().st_size
        if other != size:  # never overwrite: keep both, leave the source where it is
            raise RuntimeError(f"a different file with this name is already archived ({final}, {other} bytes "
                               f"vs {size}); kept both, nothing moved")
        digest = sha256_file(src)
        if sha256_file(final) != digest:
            raise RuntimeError(f"existing copy differs: {final}; kept both, nothing moved")
        status = "verified-existing"
    else:
        part = dest_dir / (src.name + ".part")
        digest = sha256_copy(src, part)
        if part.stat().st_size != size or sha256_file(part) != digest:
            raise RuntimeError(f"verification failed for {src.name}")
        part.replace(final)
        sync_dir(dest_dir)
        status = "copied"
    with manifest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"name": src.name, "size": size, "sha256": digest,
                             "moved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}) + "\n")
    src.unlink()
    return status, size


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=ROOT / "data" / "raw" / "hltv")
    ap.add_argument("--dest", type=Path, default=None, help="override [archive] dir from config/storage.toml")
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "storage.toml")
    ap.add_argument("--all", action="store_true", help="also move archives that have no extracted folder")
    ap.add_argument("--apply", action="store_true", help="actually move (default: dry run)")
    args = ap.parse_args(argv)

    dest = args.dest or load_dest(args.config)
    if dest is None:
        print("No archive destination configured (config/storage.toml [archive] dir); nothing to do.")
        return 0
    problem = destination_problem(dest)
    if problem:
        print(problem)
        return 0
    if not args.src.is_dir():
        print(f"No source directory {args.src}; nothing to do.")
        return 0
    files = candidates(args.src, imported_only=not args.all)
    total = sum(p.stat().st_size for p in files)
    print(f"{len(files)} archive(s), {total / 1e9:.1f} GB -> {dest}")
    if not args.apply:
        for p in files[:20]:
            print(f"  would move {p.name} ({p.stat().st_size / 1e6:.0f} MB)")
        if len(files) > 20:
            print(f"  ... and {len(files) - 20} more")
        return 0
    dest.mkdir(parents=True, exist_ok=True)  # only ever creates folders inside a mounted volume
    manifest = dest / ".archived.jsonl"
    done = moved_bytes = 0
    failures = []
    started = time.time()
    for i, p in enumerate(files, 1):
        try:
            status, size = move_one(p, dest, manifest)
            done += 1
            moved_bytes += size
            rate = moved_bytes / 1e6 / max(time.time() - started, 1e-6)
            print(f"[{i}/{len(files)}] {status} {p.name} ({size / 1e6:.0f} MB, {rate:.0f} MB/s avg)", flush=True)
        except Exception as exc:  # keep going; the original stays in place
            failures.append((p.name, str(exc)))
            print(f"[{i}/{len(files)}] FAILED {p.name}: {exc}", flush=True)
    print(f"done: {done} moved ({moved_bytes / 1e9:.1f} GB), {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
