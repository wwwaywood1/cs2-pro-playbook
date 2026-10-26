"""HLTV downloads use synthetic archives and mocked awpy headers, no network."""
import bz2
import gzip
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from playbook.cli import _demo_paths
from playbook.parse import demo_identity
from scripts import import_hltv as hltv


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    src = tmp_path / "raw" / "hltv"
    src.mkdir(parents=True)

    def demo(path):
        content = Path(path).read_text()
        if content == "broken":
            raise ValueError("invalid demo header")
        return SimpleNamespace(header={"map_name": content})

    monkeypatch.setattr(hltv, "Demo", demo)
    return src, tmp_path / "parsed", tmp_path / "raw"


def archive(src, name="match.zip", **members):
    path = src / name
    with zipfile.ZipFile(path, "w") as zf:
        for filename, content in members.items():
            zf.writestr(filename, content)
    return path


def run(workspace, **kwargs):
    src, parsed, raw = workspace
    return hltv.import_downloads(src, parsed=parsed, raw=raw, **kwargs)


def test_extract_filter_summary_and_rerun(workspace, capsys):
    src, _, _ = workspace
    download = archive(src, **{"nested/game.dem": "de_mirage", "old.dem": "de_vertigo"})
    row, = run(workspace)
    assert (row.imported, row.duplicate, row.skipped, row.failed) == (1, 0, 1, 0)
    assert row.maps == {"de_mirage", "de_vertigo"}
    assert (src / "match/nested/game.dem").read_text() == "de_mirage"
    assert not (src / "match/old.dem").exists()
    assert download.exists()
    output = capsys.readouterr().out
    assert "match.zip -> de_mirage, de_vertigo | 1 | 0 | 1 | 0" in output
    row, = run(workspace)                    # imported before: not extracted again
    assert (row.imported, row.failed, row.reasons) == (0, 0, ["already imported"])


def test_duplicate_parsed_existing_raw_and_batch(workspace):
    src, parsed, raw = workspace
    (parsed / "matches").mkdir(parents=True)
    (parsed / "matches/42_parsed.parquet").touch()
    other = raw / "other"
    other.mkdir()
    (other / "existing.dem").write_text("de_nuke")
    archive(src, "42-hltv.zip", **{"parsed.dem": "de_nuke"})
    archive(src, "a.zip", **{"existing.dem": "de_nuke", "new.dem": "de_mirage"})
    archive(src, "b.zip", **{"new.dem": "de_mirage"})
    rows = run(workspace)
    assert [(r.imported, r.duplicate, r.failed) for r in rows] == [(0, 1, 0), (2, 0, 0), (1, 0, 0)]
    assert not (src / "42-hltv").exists()
    assert (src / "b/new.dem").exists()
    assert (other / "existing.dem").read_text() == "de_nuke"


def test_multipart_published_together_and_identity_counted_once(workspace):
    src, _, raw = workspace
    archive(src, **{"nested/game-p2.dem": "de_nuke", "nested/game-p1.dem": "de_nuke"})
    row, = run(workspace)
    assert row.imported == 1
    groups = _demo_paths([raw])
    assert len(groups) == 1
    assert [p.name for p in groups[0]] == ["game-p1.dem", "game-p2.dem"]
    assert len({p.parent for p in groups[0]}) == 1
    assert demo_identity(groups[0][0])["demo_id"].startswith("hltv-")
    assert demo_identity(groups[0][0]) == demo_identity(groups[0][1])
    row, = run(workspace)
    assert (row.imported, row.reasons) == (0, ["already imported"])


def test_dry_run_never_extracts_or_writes(workspace, monkeypatch, capsys):
    src, _, _ = workspace
    download = archive(src, **{"game.dem": "de_nuke"})
    (src / "loose.dem").write_text("de_mirage")
    before = {p: p.read_bytes() for p in src.rglob("*") if p.is_file()}

    def forbidden(*args):
        pytest.fail("dry-run extracted an archive")

    monkeypatch.setattr(hltv, "extract_archive", forbidden)
    rows = run(workspace, dry_run=True, delete_archives=True)
    assert len(rows) == 2
    assert download.exists()
    assert before == {p: p.read_bytes() for p in src.rglob("*") if p.is_file()}
    assert "checks deferred" in capsys.readouterr().out
    assert not (src / "match").exists()


def test_loose_import_is_in_place_and_persistently_deduplicated(workspace):
    src, _, _ = workspace
    (src / "game-p1.dem").write_text("de_nuke")
    (src / "game-p2.dem").write_text("de_nuke")
    row, = run(workspace)
    assert (row.imported, row.failed) == (1, 0)
    assert (src / "game-p2.dem").read_text() == "de_nuke"
    row, = run(workspace)
    assert (row.imported, row.duplicate) == (0, 1)


@pytest.mark.parametrize("suffix,compress", [("gz", gzip.compress), ("bz2", bz2.compress)])
def test_single_compressed_demo(workspace, suffix, compress):
    src, _, raw = workspace
    path = src / f"game.dem.{suffix}"
    path.write_bytes(compress(b"de_nuke"))
    row, = run(workspace, delete_archives=True)
    assert (row.imported, row.failed) == (1, 0)
    assert not path.exists()
    assert (src / "game.dem/game.dem").read_bytes() == b"de_nuke"
    assert len(_demo_paths([raw])) == 1


def test_bad_header_retains_archive_and_other_games_continue(workspace):
    src, _, _ = workspace
    download = archive(src, **{"bad.dem": "broken", "good.dem": "de_nuke"})
    row, = run(workspace, delete_archives=True)
    assert (row.imported, row.failed) == (1, 1)
    assert download.exists()
    assert not (src / "match/bad.dem").exists()
    assert "invalid demo header" in row.reasons[0]


@pytest.mark.parametrize("members", [
    {"game-p2.dem": "de_nuke"},
    {"game-p1.dem": "de_nuke", "game-p3.dem": "de_nuke"},
    {"game-p1.dem": "de_nuke", "game-p2.dem": "de_mirage"},
])
def test_invalid_multipart_is_not_partially_published(workspace, members):
    src, _, _ = workspace
    download = archive(src, **members)
    row, = run(workspace, delete_archives=True)
    assert (row.imported, row.failed) == (0, 1)
    assert download.exists()
    assert not (src / "match").exists()


def test_zipfile_fallback_after_native_failures(workspace, monkeypatch):
    src, _, _ = workspace
    archive(src, **{"game.dem": "de_nuke"})
    monkeypatch.setattr(hltv.shutil, "which", lambda tool: f"/fake/{tool}")
    calls = []

    def fail(command, **kwargs):
        calls.append(command[0])
        return subprocess.CompletedProcess(command, 1, "", "unsupported format")

    monkeypatch.setattr(hltv.subprocess, "run", fail)
    row, = run(workspace)
    assert (row.imported, row.failed) == (1, 0)
    assert calls == ["/fake/bsdtar", "/fake/unar", "/fake/7z"]


def test_rar_without_extractor_has_one_install_hint(workspace, monkeypatch, capsys):
    src, _, _ = workspace
    (src / "match.rar").write_bytes(b"rar")
    monkeypatch.setattr(hltv.shutil, "which", lambda tool: None)
    row, = run(workspace, delete_archives=True)
    assert row.failed == 1
    assert "brew install sevenzip" in row.reasons[0]
    assert capsys.readouterr().out.count("brew install sevenzip") == 1
    assert (src / "match.rar").exists()


def test_existing_file_is_never_overwritten(workspace):
    src, _, _ = workspace
    archive(src, **{"game.dem": "de_nuke"})
    target = src / "match/game.dem"
    target.parent.mkdir()
    target.write_text("previous data")
    row, = run(workspace)
    assert row.duplicate == 1
    assert target.read_text() == "previous data"


def test_publish_failure_rolls_back_only_new_parts(workspace, monkeypatch):
    src, _, _ = workspace
    archive(src, **{"game-p1.dem": "de_nuke", "game-p2.dem": "de_nuke"})
    original = hltv.shutil.copyfileobj

    def fail_second(inp, out, *args, **kwargs):
        if out.name.endswith("game-p2.dem"):
            raise OSError("disk full")
        return original(inp, out, *args, **kwargs)

    monkeypatch.setattr(hltv.shutil, "copyfileobj", fail_second)
    row, = run(workspace)
    assert (row.imported, row.failed) == (0, 1)
    assert list((src / "match").glob("*.dem")) == []


def test_unsafe_zip_paths_rejected(workspace):
    src, _, _ = workspace
    archive(src, **{"../escape.dem": "de_nuke"})
    row, = run(workspace)
    assert row.failed == 1
    assert "unsafe archive member" in row.reasons[0]
    assert not (src.parent / "escape.dem").exists()


def test_only_top_level_downloads_are_inputs(workspace):
    src, _, _ = workspace
    nested = src / "previous"
    nested.mkdir()
    archive(nested, **{"game.dem": "de_nuke"})
    assert run(workspace) == []


def test_homebrew_7zz_fallback(workspace, monkeypatch):
    src, _, _ = workspace
    (src / "match.rar").write_bytes(b"rar")
    monkeypatch.setattr(hltv.shutil, "which", lambda tool: "/fake/7zz" if tool == "7zz" else None)
    calls = []

    def extract(command, **kwargs):
        calls.append(command)
        dest = Path(next(arg[2:] for arg in command if arg.startswith("-o")))
        (dest / "game.dem").write_text("de_nuke")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(hltv.subprocess, "run", extract)
    row, = run(workspace)
    assert row.imported == 1
    assert calls[0][0:2] == ["/fake/7zz", "x"]


def test_zipfile_works_without_native_extractors(workspace, monkeypatch):
    src, _, _ = workspace
    archive(src, **{"game.dem": "de_nuke"})
    monkeypatch.setattr(hltv.shutil, "which", lambda tool: None)
    row, = run(workspace)
    assert (row.imported, row.failed) == (1, 0)


def test_case_insensitive_demo_extension_is_discovered(workspace):
    src, _, raw = workspace
    (src / "game.DEM").write_text("de_nuke")
    row, = run(workspace)
    assert row.imported == 1
    assert _demo_paths([raw]) == [[src / "game.DEM"]]


def test_damaged_download_is_set_aside_not_retried(workspace, monkeypatch):
    src, _, _ = workspace
    (src / "cut-short.zip").write_bytes(b"PK\x03\x04 truncated")
    row, = run(workspace)
    assert row.failed == 1 and "download it again" in row.reasons[0]
    assert (src / ".bad" / "cut-short.zip").exists() and not (src / "cut-short.zip").exists()
    assert run(workspace) == []          # nothing left to retry


def test_rar_that_every_extractor_rejects_is_set_aside(workspace, monkeypatch):
    src, _, _ = workspace
    (src / "match.rar").write_bytes(b"rar")
    monkeypatch.setattr(hltv.shutil, "which", lambda tool: f"/fake/{tool}")
    monkeypatch.setattr(hltv.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "Truncated input file"))
    row, = run(workspace)
    assert row.failed == 1 and (src / ".bad" / "match.rar").exists()


def test_archive_imported_before_is_not_extracted_again(workspace, monkeypatch):
    src, _, _ = workspace
    archive(src, **{"game.dem": "de_nuke"})
    row, = run(workspace)
    assert row.imported == 1
    calls = []
    monkeypatch.setattr(hltv, "extract_archive", lambda *a: calls.append(a))
    row, = run(workspace)
    assert calls == [] and row.reasons == ["already imported"] and not row.failed


def test_hung_extractor_is_stopped_and_the_next_one_tried(workspace, monkeypatch):
    src, _, _ = workspace
    (src / "match.rar").write_bytes(b"rar")
    monkeypatch.setattr(hltv.shutil, "which", lambda tool: f"/fake/{tool}" if tool != "7z" else None)
    calls = []

    def extract(command, **kwargs):
        calls.append((command[0], kwargs.get("timeout")))
        if command[0] == "/fake/bsdtar" and "-tf" in command:
            return subprocess.CompletedProcess(command, 0, "game.dem\n", "")
        if command[0] == "/fake/bsdtar":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        dest = Path(command[command.index("-output-directory") + 1])
        (dest / "game.dem").write_text("de_nuke")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(hltv.subprocess, "run", extract)
    row, = run(workspace)
    assert (row.imported, row.failed) == (1, 0)
    assert [tool for tool, _ in calls] == ["/fake/bsdtar", "/fake/bsdtar", "/fake/unar"]
    assert all(limit and limit >= hltv.EXTRACT_TIMEOUT_S for _, limit in calls)
    assert not (src / "match" / "bsdtar").exists()


def test_archive_whose_extractors_all_time_out_is_kept_for_a_retry(workspace, monkeypatch):
    src, _, _ = workspace
    (src / "match.rar").write_bytes(b"rar")
    monkeypatch.setattr(hltv.shutil, "which", lambda tool: f"/fake/{tool}" if tool in {"unar", "7z"} else None)

    def hang(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(hltv.subprocess, "run", hang)
    row, = run(workspace)
    assert row.failed == 1 and "timed out" in row.reasons[0]
    assert (src / "match.rar").exists() and not (src / ".bad").exists()


def test_extract_timeout_grows_with_the_archive(tmp_path):
    small, big = tmp_path / "s.rar", tmp_path / "b.rar"
    small.write_bytes(b"x")
    big.write_bytes(b"x" * 4_000_000)
    assert hltv.extract_timeout(small) >= hltv.EXTRACT_TIMEOUT_S
    assert hltv.extract_timeout(big) - hltv.extract_timeout(small) == pytest.approx(4_000_000 / hltv.EXTRACT_MIN_RATE, abs=0.01)


def test_registry_is_saved_after_each_archive_and_merged(workspace, monkeypatch):
    src, _, _ = workspace
    archive(src, "a.zip", **{"game.dem": "de_nuke"})
    archive(src, "b.zip", **{"other.dem": "de_mirage"})
    registry = src / ".import_hltv_archives.json"
    registry.write_text('["written-by-another-run.rar"]')
    original = hltv._process

    def stop_on_second(paths, source, destination, seen, row, **kwargs):
        if destination.name == "b":
            assert '"a.zip"' in registry.read_text()   # the first archive is on record already
            raise KeyboardInterrupt
        return original(paths, source, destination, seen, row, **kwargs)

    monkeypatch.setattr(hltv, "_process", stop_on_second)
    with pytest.raises(KeyboardInterrupt):
        run(workspace)
    assert set(hltv._load_processed(registry)) == {"a.zip", "written-by-another-run.rar"}


def test_second_import_on_the_same_folder_is_refused(workspace):
    src, _, _ = workspace
    archive(src, **{"game.dem": "de_nuke"})
    with hltv.import_lock(src.resolve()):
        with pytest.raises(ValueError, match="another import"):
            run(workspace)
    row, = run(workspace)                     # lock released
    assert row.imported == 1


def test_archive_on_another_disk_is_copied_to_the_staging_folder_first(workspace, monkeypatch):
    src, _, _ = workspace
    (src / "match.rar").write_bytes(b"rar")
    monkeypatch.setattr(hltv, "same_device", lambda path, folder: False)
    monkeypatch.setattr(hltv.shutil, "which", lambda tool: "/fake/7zz" if tool == "7zz" else None)
    seen = []

    def extract(command, **kwargs):
        source = Path(command[-1])
        seen.append((source, source.read_bytes()))
        dest = Path(next(arg[2:] for arg in command if arg.startswith("-o")))
        (dest / "game.dem").write_text("de_nuke")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(hltv.subprocess, "run", extract)
    row, = run(workspace)
    assert row.imported == 1
    (source, content), = seen
    assert source.name == "source.rar" and source.parent != src and content == b"rar"
    assert not source.exists()                       # staging folder removed afterwards
    assert (src / "match.rar").exists()              # the original is untouched
