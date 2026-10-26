import importlib.util
import json
import types
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "relocate_raw", Path(__file__).resolve().parents[1] / "scripts" / "relocate_raw.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _setup(tmp_path):
    src = tmp_path / "repo" / "data" / "raw"
    (src / "hltv" / "event-a-vs-b-bo3-X").mkdir(parents=True)
    (src / "hltv" / "event-a-vs-b-bo3-X" / "a-vs-b-m1-mirage.dem").write_bytes(b"m" * 1000)
    (src / "hltv" / "event-a-vs-b-bo3-X" / "._a-vs-b-m1-mirage.dem").write_bytes(b"junk")
    (src / "hltv" / ".import_hltv_archives.json").write_text("[]")
    dest = tmp_path / "ssd" / "raw"
    (tmp_path / "ssd").mkdir()
    return src, dest


def _args(src, dest, *extra):
    return ["--src", str(src), "--dest", str(dest), *extra]


def test_plan_only_copies_nothing(tmp_path, capsys):
    src, dest = _setup(tmp_path)
    assert mod.main(_args(src, dest)) == 0
    assert "2 left to copy" in capsys.readouterr().out
    assert not (dest / "hltv").exists()


def test_copy_switch_finish(tmp_path, capsys):
    src, dest = _setup(tmp_path)
    assert mod.main(_args(src, dest, "--switch")) == 1  # copy incomplete
    assert mod.main(_args(src, dest, "--copy")) == 0
    rel = "hltv/event-a-vs-b-bo3-X/a-vs-b-m1-mirage.dem"
    assert (dest / rel).read_bytes() == b"m" * 1000
    assert not (dest / "hltv/event-a-vs-b-bo3-X/._a-vs-b-m1-mirage.dem").exists()
    man = [json.loads(line) for line in (dest / ".relocated.jsonl").read_text().splitlines()]
    assert {m["rel"] for m in man} == {rel, "hltv/.import_hltv_archives.json"}
    # resumable: a second copy run has nothing left
    capsys.readouterr()
    assert mod.main(_args(src, dest, "--copy")) == 0
    assert "0 left to copy" in capsys.readouterr().out
    assert mod.main(_args(src, dest, "--switch")) == 0
    assert src.is_symlink() and (src / rel).read_bytes() == b"m" * 1000
    locals_ = list(src.parent.glob("raw.local-*"))
    assert len(locals_) == 1
    assert mod.main(_args(src, dest, "--finish")) == 0
    assert not locals_[0].exists() and (src / rel).exists()


def test_finish_keeps_local_copy_when_destination_lost_a_file(tmp_path, capsys):
    src, dest = _setup(tmp_path)
    mod.main(_args(src, dest, "--copy"))
    mod.main(_args(src, dest, "--switch"))
    (dest / "hltv/event-a-vs-b-bo3-X/a-vs-b-m1-mirage.dem").unlink()
    assert mod.main(_args(src, dest, "--finish")) == 1
    assert list(src.parent.glob("raw.local-*"))


def test_finish_rehashes_and_keeps_a_file_whose_destination_differs(tmp_path, capsys):
    src, dest = _setup(tmp_path)
    mod.main(_args(src, dest, "--copy"))
    mod.main(_args(src, dest, "--switch"))
    rel = "hltv/event-a-vs-b-bo3-X/a-vs-b-m1-mirage.dem"
    (dest / rel).write_bytes(b"x" * 1000)          # same size, different content
    capsys.readouterr()
    assert mod.main(_args(src, dest, "--finish")) == 1
    out = capsys.readouterr().out
    assert "SHA-256 mismatch" in out
    local = next(src.parent.glob("raw.local-*"))
    assert (local / rel).read_bytes() == b"m" * 1000                     # kept, untouched
    assert (local / "hltv/event-a-vs-b-bo3-X/._a-vs-b-m1-mirage.dem").exists()  # with its sidecar
    assert not (local / "hltv/.import_hltv_archives.json").exists()     # the verified file went


def test_finish_keeps_files_that_were_never_copied(tmp_path):
    src, dest = _setup(tmp_path)
    mod.main(_args(src, dest, "--copy"))
    mod.main(_args(src, dest, "--switch"))
    local = next(src.parent.glob("raw.local-*"))
    (local / "hltv" / "leftover.dem.part").write_bytes(b"p")
    assert mod.main(_args(src, dest, "--finish")) == 1
    assert (local / "hltv" / "leftover.dem.part").exists()
    assert not (local / "hltv" / "event-a-vs-b-bo3-X").exists()          # verified folder removed


def test_finish_with_destination_unplugged_removes_nothing(tmp_path, capsys):
    src, dest = _setup(tmp_path)
    mod.main(_args(src, dest, "--copy"))
    mod.main(_args(src, dest, "--switch"))
    dest.rename(tmp_path / "ssd" / "raw-elsewhere")
    assert mod.main(_args(src, dest, "--finish")) == 1
    assert "nothing removed" in capsys.readouterr().out
    local = next(src.parent.glob("raw.local-*"))
    assert (local / "hltv/event-a-vs-b-bo3-X/a-vs-b-m1-mirage.dem").exists()


def test_copy_is_flushed_with_f_fullfsync_when_available(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(mod, "fcntl", types.SimpleNamespace(F_FULLFSYNC=51, fcntl=lambda fd, cmd: calls.append(cmd)))
    src, dest = _setup(tmp_path)
    assert mod.main(_args(src, dest, "--copy")) == 0
    assert calls.count(51) >= 2


def test_unmounted_destination(tmp_path, capsys):
    src, _ = _setup(tmp_path)
    assert mod.main(_args(src, tmp_path / "nowhere" / "raw", "--copy")) == 1
    assert "not mounted" in capsys.readouterr().out
