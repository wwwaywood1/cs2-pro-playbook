#!/usr/bin/env python3
"""Move the raw demo store (data/raw, hundreds of GB) to an external drive, safely.

    python scripts/relocate_raw.py            # plan: what is left to copy, free space
    python scripts/relocate_raw.py --copy     # copy every file, SHA-256 verified, resumable
    python scripts/relocate_raw.py --switch   # data/raw -> data/raw.local-<date>; data/raw becomes a symlink
    python scripts/relocate_raw.py --finish   # after the export has been checked: delete data/raw.local-*

The destination is ``[raw] dir`` in config/storage.toml. Demo ids depend only on the
folder and file names below ``data/raw`` (see playbook.parse.demo_identity), so the
parsed data and the site stay valid when the tree lives elsewhere and ``data/raw`` is a
symlink to it.

Safety: each file is copied to ``<name>.part`` while hashing, flushed to the drive
(F_FULLFSYNC on macOS), re-read from the destination and compared before it is renamed
into place; a manifest ``.relocated.jsonl`` at the destination records path, size and
hash. ``--switch`` refuses unless every source file is in the manifest. ``--finish``
deletes the local copy file by file: a local file goes only after its destination copy
has been re-read and its SHA-256 matches the manifest (and the local size still matches);
files that do not verify are kept and reported, empty folders are removed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import tomllib
from datetime import date
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

ROOT = Path(__file__).resolve().parent.parent
CHUNK = 8 << 20
SKIP = {".DS_Store"}
MARGIN = 20e9  # keep this much free on the destination


def load_dest(config: Path) -> Path | None:
    if not config.exists():
        return None
    value = (tomllib.loads(config.read_text(encoding="utf-8")).get("raw") or {}).get("dir")
    return Path(value).expanduser() if value else None


def files_under(root: Path) -> list[Path]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("._"))
        for name in sorted(filenames):
            if name.startswith("._") or name in SKIP or name.endswith(".part"):
                continue
            out.append(Path(dirpath) / name)
    return out


def read_manifest(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                out[rec["rel"]] = rec
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


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


def copy_verified(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    h = hashlib.sha256()
    with src.open("rb") as fi, part.open("wb") as fo:
        while chunk := fi.read(CHUNK):
            h.update(chunk)
            fo.write(chunk)
        fo.flush()
        flush_to_disk(fo.fileno())
    digest = h.hexdigest()
    if part.stat().st_size != src.stat().st_size or sha256_file(part) != digest:
        part.unlink(missing_ok=True)
        raise RuntimeError(f"verification failed: {src}")
    st = src.stat()
    os.utime(part, (st.st_atime, st.st_mtime))
    part.replace(dst)
    sync_dir(dst.parent)
    return digest


def unverified(path: Path, rel: str, manifest: dict[str, dict], dest: Path) -> str | None:
    """Why the local file ``path`` must be kept; None when its destination copy is verified:
    listed in the manifest, local size unchanged, and the destination file re-hashes to the
    manifest's SHA-256."""
    rec = manifest.get(rel)
    if rec is None:
        return "not in the manifest"
    if path.stat().st_size != rec["size"]:
        return "local file changed since it was copied"
    target = dest / rel
    if not target.is_file():
        return "missing at the destination"
    if target.stat().st_size != rec["size"]:
        return "different size at the destination"
    if sha256_file(target) != rec["sha256"]:
        return "different content at the destination (SHA-256 mismatch)"
    return None


def is_junk(name: str) -> bool:
    """macOS sidecar files that are never copied (AppleDouble ._*, .DS_Store)."""
    return name.startswith("._") or name in SKIP


def prune_empty_dirs(root: Path) -> None:
    """Remove the folders below and including ``root`` that hold nothing but macOS sidecar
    files; a folder that still holds anything else is left exactly as it is."""
    for dirpath, _dirs, _files in os.walk(root, topdown=False):
        entries = list(os.scandir(dirpath))
        if all(e.is_file(follow_symlinks=False) and is_junk(e.name) for e in entries):
            for entry in entries:
                os.unlink(entry.path)
            os.rmdir(dirpath)


def finish(locals_: list[Path], dest: Path, manifest: dict[str, dict]) -> int:
    """Delete the local copies file by file, each only after its destination copy verified."""
    status = 0
    for local in locals_:
        files = files_under(local)
        kept: list[tuple[str, str]] = []
        for i, path in enumerate(files, 1):
            rel = path.relative_to(local).as_posix()
            problem = unverified(path, rel, manifest, dest)
            if problem:
                kept.append((rel, problem))
                print(f"[{i}/{len(files)}] KEPT {rel}: {problem}", flush=True)
                continue
            path.unlink()
            print(f"[{i}/{len(files)}] verified, local copy removed: {rel}", flush=True)
        prune_empty_dirs(local)
        if not local.exists():
            print(f"removed {local}")
            continue
        status = 1
        left = sum(1 for p in local.rglob("*") if p.is_file() and not is_junk(p.name))
        print(f"{local} kept: {left} file(s) left, {len(kept)} of them did not verify against the destination"
              + ("; e.g. " + "; ".join(f"{rel} ({why})" for rel, why in kept[:3]) if kept else
                 " (the others were never copied, e.g. *.part; check them by hand)"))
    return status


def human(n: float) -> str:
    return f"{n / 1e9:.1f} GB"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--dest", type=Path, help="override [raw] dir from config/storage.toml")
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "storage.toml")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--copy", action="store_true")
    mode.add_argument("--switch", action="store_true")
    mode.add_argument("--finish", action="store_true")
    args = ap.parse_args(argv)

    dest = args.dest or load_dest(args.config)
    if dest is None:
        print("No [raw] dir in config/storage.toml; nothing to do.")
        return 0
    src = args.src
    manifest_path = dest / ".relocated.jsonl"

    if args.finish:
        locals_ = [p for p in sorted(src.parent.glob(src.name + ".local-*")) if p.is_dir() and not p.is_symlink()]
        if not locals_:
            print("No local copy left to remove.")
            return 0
        if not dest.is_dir() or not manifest_path.is_file():
            print(f"Destination {dest} or its manifest is missing (drive not mounted?); nothing removed.")
            return 1
        return finish(locals_, dest, read_manifest(manifest_path))

    if src.is_symlink():
        target = os.readlink(src)
        print(f"{src} is already a symlink to {target}" + ("" if src.exists() else " (NOT MOUNTED)"))
        return 0
    if not src.is_dir():
        print(f"No source directory {src}")
        return 1
    if not dest.parent.exists():
        print(f"Destination volume not mounted ({dest.parent}); skipping.")
        return 1
    dest.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(manifest_path)
    files = files_under(src)
    todo = []
    for path in files:
        rel = path.relative_to(src).as_posix()
        rec = manifest.get(rel)
        if rec and rec["size"] == path.stat().st_size and (dest / rel).exists() \
                and (dest / rel).stat().st_size == rec["size"]:
            continue
        todo.append(path)
    total = sum(p.stat().st_size for p in files)
    left = sum(p.stat().st_size for p in todo)
    free = shutil.disk_usage(dest).free
    print(f"{len(files)} files ({human(total)}) in {src}; {len(todo)} left to copy ({human(left)}); "
          f"{human(free)} free at {dest}")

    if args.switch:
        if todo:
            print("Refusing to switch: copy is incomplete (run --copy first).")
            return 1
        local = src.with_name(f"{src.name}.local-{date.today().isoformat()}")
        src.rename(local)
        src.symlink_to(dest, target_is_directory=True)
        print(f"{src} -> {dest}; local copy kept at {local} (remove with --finish once the export checks out)")
        return 0
    if not args.copy:
        return 0
    if left > free - MARGIN:
        print("Not enough free space on the destination.")
        return 1
    done_bytes, started, failures = 0, time.time(), 0
    with manifest_path.open("a", encoding="utf-8") as man:
        for i, path in enumerate(todo, 1):
            rel = path.relative_to(src).as_posix()
            try:
                size = path.stat().st_size
                digest = copy_verified(path, dest / rel)
            except Exception as exc:  # keep going; the source is untouched
                failures += 1
                print(f"[{i}/{len(todo)}] FAILED {rel}: {exc}", flush=True)
                continue
            man.write(json.dumps({"rel": rel, "size": size, "sha256": digest}) + "\n")
            man.flush()
            done_bytes += size
            rate = done_bytes / 1e6 / max(time.time() - started, 1e-6)
            print(f"[{i}/{len(todo)}] {rel} ({size / 1e6:.0f} MB, {rate:.0f} MB/s avg)", flush=True)
    print(f"copied {human(done_bytes)}; {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
