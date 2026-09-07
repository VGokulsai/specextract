import io
import json
import os

import pytest

import spec

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture_path(name):
    return os.path.join(FIXTURES, name)


def run(monkeypatch, args):
    monkeypatch.setattr("sys.argv", ["spec.py"] + args)
    return spec.main()


def test_probe_flag_prints_script_and_keeps_contract(monkeypatch, capsys):
    rc = run(monkeypatch, ["--probe"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "console.log(JSON.stringify(out, null, 1))" in out
    assert "py -3 spec.py that-file.json" in out


def test_no_args_prints_usage_to_stderr_and_exits_2(monkeypatch, capsys):
    rc = run(monkeypatch, [])
    err = capsys.readouterr().err
    assert rc == 2
    assert "py -3 spec.py --probe > probe.js" in err


def test_end_to_end_writes_reference_md(monkeypatch, tmp_path, capsys):
    out_path = tmp_path / "REFERENCE.md"
    rc = run(monkeypatch, [fixture_path("minimal.json"), "-o", str(out_path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")
    assert text.startswith("# REFERENCE - Example")
    assert "type rows" in captured.out


def test_end_to_end_creates_missing_output_directory(monkeypatch, tmp_path):
    out_path = tmp_path / "nested" / "dir" / "REFERENCE.md"
    rc = run(monkeypatch, [fixture_path("minimal.json"), "-o", str(out_path)])
    assert rc == 0
    assert out_path.exists()


def test_missing_file_reports_error(monkeypatch, tmp_path, capsys):
    missing = tmp_path / "nope.json"
    rc = run(monkeypatch, [str(missing)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "could not read" in err


def test_malformed_json_reports_error(monkeypatch, capsys):
    rc = run(monkeypatch, [fixture_path("malformed.json")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "could not read" in err
    assert "not a page with no design" in err


def test_empty_file_reports_error(monkeypatch, capsys):
    rc = run(monkeypatch, [fixture_path("empty.json")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "empty" in err


def test_json_missing_type_reports_error(monkeypatch, tmp_path, capsys):
    p = tmp_path / "no_type.json"
    p.write_text(json.dumps({"url": "https://x.test", "page": {}}),
                 encoding="utf-8")
    rc = run(monkeypatch, [str(p)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "no type data" in err


def test_non_object_json_reports_error(monkeypatch, capsys):
    rc = run(monkeypatch, [fixture_path("not_object.json")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "could not read" in err


def test_trailing_console_text_is_tolerated_end_to_end(monkeypatch, tmp_path):
    out_path = tmp_path / "REFERENCE.md"
    rc = run(monkeypatch, [fixture_path("trailing_garbage.json"),
                           "-o", str(out_path)])
    assert rc == 0
    assert out_path.exists()


def test_stdin_dash_reads_from_stdin(monkeypatch, tmp_path, capsys):
    raw = io.open(fixture_path("minimal.json"), encoding="utf-8-sig").read()
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    out_path = tmp_path / "REFERENCE.md"
    rc = run(monkeypatch, ["-", "-o", str(out_path)])
    assert rc == 0
    assert out_path.exists()


def test_stats_flag_prints_json_summary(monkeypatch, tmp_path, capsys):
    out_path = tmp_path / "REFERENCE.md"
    rc = run(monkeypatch, [fixture_path("full.json"), "-o", str(out_path),
                           "--stats"])
    out = capsys.readouterr().out
    assert rc == 0
    # last JSON-looking block in stdout is the stats payload
    stats = json.loads(out[out.index("{"):])
    assert stats["typeStyles"] == 5
    assert stats["distinctFonts"] == 4


def test_no_summary_flag_omits_rollups(monkeypatch, tmp_path):
    out_path = tmp_path / "REFERENCE.md"
    rc = run(monkeypatch, [fixture_path("minimal.json"), "-o", str(out_path),
                           "--no-summary"])
    assert rc == 0
    text = out_path.read_text(encoding="utf-8")
    assert "## Summary" not in text
    assert "## Palette" not in text


def test_version_flag(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc_info:
        run(monkeypatch, ["--version"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "specextract" in out
