import json
import importlib.util
import types
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "archive_downloads", Path(__file__).resolve().parents[1] / "scripts" / "archive_downloads.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _setup(tmp_path):
    src = tmp_path / "hltv"
    src.mkdir()
    (src / "a-bo3-x.rar").write_bytes(b"A" * 1000)
    (src / "a-bo3-x").mkdir()                      # extracted -> imported
    (src / "b-bo3-y.zip").write_bytes(b"B" * 10)   # listed in registry (all duplicates)
    (src / ".import_hltv_archives.json").write_text(json.dumps(["b-bo3-y.zip"]))
    (src / "c-bo3-z.rar").write_bytes(b"C" * 10)   # not imported yet -> stays
    (src / "._a-bo3-x.rar").write_bytes(b"\0" * 4)  # AppleDouble sidecar -> ignored
    return src


def _dest(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    return dest


def test_dry_run_lists_only_imported(tmp_path, capsys):
    src = _setup(tmp_path)
    dest = _dest(tmp_path)
    assert mod.main(["--src", str(src), "--dest", str(dest)]) == 0
    out = capsys.readouterr().out
    assert "2 archive(s)" in out and "c-bo3-z" not in out
    assert not list(dest.iterdir())


def test_apply_moves_and_verifies(tmp_path):
    src = _setup(tmp_path)
    dest = _dest(tmp_path)
    assert mod.main(["--src", str(src), "--dest", str(dest), "--apply"]) == 0
    assert (dest / "a-bo3-x.rar").read_bytes() == b"A" * 1000
    assert (dest / "b-bo3-y.zip").exists()
    assert not (src / "a-bo3-x.rar").exists() and not (src / "b-bo3-y.zip").exists()
    assert (src / "c-bo3-z.rar").exists() and (src / "._a-bo3-x.rar").exists()
    lines = [json.loads(l) for l in (dest / ".archived.jsonl").read_text().splitlines()]
    assert {l["name"] for l in lines} == {"a-bo3-x.rar", "b-bo3-y.zip"}
    assert not list(dest.glob("*.part"))


def test_resume_with_existing_identical_copy(tmp_path):
    src = _setup(tmp_path)
    dest = _dest(tmp_path)
    (dest / "a-bo3-x.rar").write_bytes(b"A" * 1000)
    assert mod.main(["--src", str(src), "--dest", str(dest), "--apply"]) == 0
    assert not (src / "a-bo3-x.rar").exists()


def test_mismatched_existing_copy_keeps_source(tmp_path):
    src = _setup(tmp_path)
    dest = _dest(tmp_path)
    (dest / "a-bo3-x.rar").write_bytes(b"Z" * 1000)   # same size, different bytes
    assert mod.main(["--src", str(src), "--dest", str(dest), "--apply"]) == 1
    assert (src / "a-bo3-x.rar").exists()


def test_name_clash_with_different_size_keeps_both(tmp_path, capsys):
    src = _setup(tmp_path)
    dest = _dest(tmp_path)
    (dest / "a-bo3-x.rar").write_bytes(b"Z" * 500)    # another archive under the same name
    assert mod.main(["--src", str(src), "--dest", str(dest), "--apply"]) == 1
    assert (dest / "a-bo3-x.rar").read_bytes() == b"Z" * 500       # not overwritten
    assert (src / "a-bo3-x.rar").read_bytes() == b"A" * 1000       # source kept
    assert not list(dest.glob("*.part"))
    assert "different file with this name" in capsys.readouterr().out
    assert not (src / "b-bo3-y.zip").exists()                       # the others still move


def test_unmounted_volume_is_skipped(tmp_path, capsys):
    src = _setup(tmp_path)
    assert mod.main(["--src", str(src), "--dest", "/Volumes/NoSuchDrive-xyz/archives", "--apply"]) == 0
    assert "not mounted" in capsys.readouterr().out
    assert (src / "a-bo3-x.rar").exists()


def test_stale_mount_point_folder_is_not_a_mounted_volume(tmp_path, monkeypatch, capsys):
    # after an unclean eject macOS can leave /Volumes/<name> behind as a plain folder
    monkeypatch.setattr(mod, "VOLUMES", tmp_path / "Volumes")
    stale = tmp_path / "Volumes" / "My PSSD"
    stale.mkdir(parents=True)
    src = _setup(tmp_path)
    assert mod.main(["--src", str(src), "--dest", str(stale / "archives"), "--apply"]) == 0
    assert "not mounted" in capsys.readouterr().out
    assert not (stale / "archives").exists() and (src / "a-bo3-x.rar").exists()


def test_mounted_volume_gets_its_archive_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "VOLUMES", tmp_path / "Volumes")
    volume = tmp_path / "Volumes" / "My PSSD"
    volume.mkdir(parents=True)
    monkeypatch.setattr(mod.os.path, "ismount", lambda p: Path(p) == volume)
    src = _setup(tmp_path)
    dest = volume / "cs2-pro-playbook-data" / "hltv-archives"
    assert mod.main(["--src", str(src), "--dest", str(dest), "--apply"]) == 0
    assert (dest / "a-bo3-x.rar").read_bytes() == b"A" * 1000


def test_missing_plain_destination_is_not_created(tmp_path, capsys):
    src = _setup(tmp_path)
    dest = tmp_path / "no" / "such" / "dir"
    assert mod.main(["--src", str(src), "--dest", str(dest), "--apply"]) == 0
    assert "does not exist" in capsys.readouterr().out
    assert not (tmp_path / "no").exists() and (src / "a-bo3-x.rar").exists()


def test_copies_are_flushed_with_f_fullfsync_when_available(tmp_path, monkeypatch):
    calls = []
    fake = types.SimpleNamespace(F_FULLFSYNC=51, fcntl=lambda fd, cmd: calls.append(cmd))
    monkeypatch.setattr(mod, "fcntl", fake)
    src = _setup(tmp_path)
    dest = _dest(tmp_path)
    assert mod.main(["--src", str(src), "--dest", str(dest), "--apply"]) == 0
    assert calls.count(51) >= 2     # each of the two copied archives (plus their folder)
