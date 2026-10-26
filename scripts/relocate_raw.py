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

Safety: each file is copied to ``<name>.part`` while hashing, flushed, re-read from the
destination and compared before it is renamed into place; a manifest
``.relocated.jsonl`` at the destination records path, size and hash. ``--switch``
refuses unless every source file is in the manifest; ``--finish`` re-checks every
file of the local copy against the manifest and the destination before deleting it.
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


def copy_verified(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    h = hashlib.sha256()
    with src.open("rb") as fi, part.open("wb") as fo:
        while chunk := fi.read(CHUNK):
            h.update(chunk)
            fo.write(chunk)
        fo.flush()
        os.fsync(fo.fileno())
    digest = h.hexdigest()
    if part.stat().st_size != src.stat().st_size or sha256_file(part) != digest:
        part.unlink(missing_ok=True)
        raise RuntimeError(f"verification failed: {src}")
    st = src.stat()
    os.utime(part, (st.st_atime, st.st_mtime))
    part.replace(dst)
    return digest


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
        locals_ = sorted(src.parent.glob(src.name + ".local-*"))
        if not locals_:
            print("No local copy left to remove.")
            return 0
        manifest = read_manifest(manifest_path)
        for local in locals_:
            bad = []
            for path in files_under(local):
                rel = path.relative_to(local).as_posix()
                rec = manifest.get(rel)
                target = dest / rel
                if rec is None or rec["size"] != path.stat().st_size or not target.exists() \
                        or target.stat().st_size != rec["size"]:
                    bad.append(rel)
            if bad:
                print(f"{local}: {len(bad)} file(s) not safely at the destination, keeping it; e.g. {bad[:3]}")
                return 1
            shutil.rmtree(local)
            print(f"removed {local}")
        return 0

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
