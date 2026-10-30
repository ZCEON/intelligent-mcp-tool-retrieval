"""Tests for the output-safety protections in scripts/extract_real_mcp_tools.py.

These tests NEVER run the extractor against real source repositories.
SERVER_TARGETS, OUTPUT_RAW, OUTPUT_REPORT, get_commit, and the per-tier
extractors are monkeypatched to temporary paths or fakes, so no real
dataset file is read or written.
"""

import json

from scripts import extract_real_mcp_tools as extractor


FAKE_TOOL = {
    "name": "fake_tool",
    "description": "A fake tool used only in tests.",
    "server": "fake",
    "source_repo": "https://example.invalid/repo",
    "commit": "0" * 40,
    "license": "MIT",
    "extraction_method": "python_ast",
    "source_file": "fake.py",
    "inputSchema": {
        "type": "object",
        "properties": {"q": {"type": "string"}},
        "required": [],
    },
}


# ---------------------------------------------------------------------------
# check_output_safety
# ---------------------------------------------------------------------------


def test_check_output_safety_blocks_missing_directories():
    message = extractor.check_output_safety(
        [FAKE_TOOL], ["fake (src/fake)"]
    )

    assert message is not None
    assert "missing" in message
    assert "fake (src/fake)" in message
    assert "NOT modified" in message


def test_check_output_safety_blocks_zero_tools():
    message = extractor.check_output_safety([], [])

    assert message is not None
    assert "zero tools" in message
    assert "NOT modified" in message


def test_check_output_safety_prefers_missing_directories_message():
    # Both problems at once: missing directories must be reported.
    message = extractor.check_output_safety([], ["a", "b"])

    assert message is not None
    assert "missing" in message


def test_check_output_safety_allows_valid_extraction():
    assert extractor.check_output_safety([FAKE_TOOL], []) is None


# ---------------------------------------------------------------------------
# write_json_atomic
# ---------------------------------------------------------------------------


def test_write_json_atomic_writes_valid_json_and_leaves_no_tmp(tmp_path):
    target = tmp_path / "out.json"
    payload = {"tools": [FAKE_TOOL], "count": 1}

    extractor.write_json_atomic(target, payload)

    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert not target.with_name(target.name + ".tmp").exists()


def test_write_json_atomic_creates_missing_parent_directories(tmp_path):
    target = tmp_path / "deep" / "nested" / "out.json"

    extractor.write_json_atomic(target, {"count": 0})

    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == {"count": 0}


def test_write_json_atomic_keeps_existing_file_when_serialization_fails(
    tmp_path,
):
    target = tmp_path / "out.json"
    original = {"tools": [FAKE_TOOL], "count": 1}
    extractor.write_json_atomic(target, original)

    try:
        extractor.write_json_atomic(target, {"bad": object()})
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError for unserializable payload")

    # Existing file is untouched and no temp file is left behind.
    assert json.loads(target.read_text(encoding="utf-8")) == original
    assert not target.with_name(target.name + ".tmp").exists()


# ---------------------------------------------------------------------------
# main(): guard rails (real SERVER_TARGETS / outputs are never touched)
# ---------------------------------------------------------------------------


def _redirect_outputs(monkeypatch, tmp_path):
    raw = tmp_path / "raw" / "real_mcp_tools_raw.json"
    report = tmp_path / "reports" / "extraction_report.json"
    monkeypatch.setattr(extractor, "OUTPUT_RAW", raw)
    monkeypatch.setattr(extractor, "OUTPUT_REPORT", report)
    return raw, report


def _seed_existing_outputs(raw, report):
    raw.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(
        json.dumps({"tools": [FAKE_TOOL], "count": 1}), encoding="utf-8"
    )
    report.write_text(
        json.dumps({"total_tools": 1}), encoding="utf-8"
    )


def test_main_blocks_when_source_directories_are_missing(
    monkeypatch, tmp_path, capsys
):
    raw, report = _redirect_outputs(monkeypatch, tmp_path)
    _seed_existing_outputs(raw, report)
    before_raw = raw.read_bytes()
    before_report = report.read_bytes()

    # One target whose directory does not exist under the clone root.
    monkeypatch.setattr(
        extractor,
        "SERVER_TARGETS",
        [("fake", "servers", "does-not-exist", "python")],
    )

    exit_code = extractor.main(["--clone-root", str(tmp_path)])

    assert exit_code == extractor.EXIT_BLOCKED
    assert "EXTRACTION BLOCKED" in capsys.readouterr().out

    # Existing outputs are byte-for-byte untouched, and no temp files remain.
    assert raw.read_bytes() == before_raw
    assert report.read_bytes() == before_report
    assert list(tmp_path.rglob("*.tmp")) == []


def test_main_blocks_when_zero_tools_are_discovered(
    monkeypatch, tmp_path, capsys
):
    raw, report = _redirect_outputs(monkeypatch, tmp_path)
    _seed_existing_outputs(raw, report)
    before_raw = raw.read_bytes()
    before_report = report.read_bytes()

    # No targets at all -> zero tools extracted -> must not write.
    monkeypatch.setattr(extractor, "SERVER_TARGETS", [])

    exit_code = extractor.main(["--clone-root", str(tmp_path)])

    assert exit_code == extractor.EXIT_BLOCKED
    assert "zero tools" in capsys.readouterr().out
    assert raw.read_bytes() == before_raw
    assert report.read_bytes() == before_report
    assert list(tmp_path.rglob("*.tmp")) == []


def test_main_writes_outputs_when_extraction_succeeds(
    monkeypatch, tmp_path
):
    raw, report = _redirect_outputs(monkeypatch, tmp_path)

    # Fake but valid source layout: clone_root/<repo-dir>/ exists.
    repo_dir = tmp_path / extractor.REPOS["servers"]["dir"]
    repo_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        extractor,
        "SERVER_TARGETS",
        [("fake", "servers", ".", "python")],
    )
    monkeypatch.setattr(extractor, "get_commit", lambda d: "fakecommit")
    monkeypatch.setattr(
        extractor,
        "extract_python_server",
        lambda server_dir, server_name, repo_key, commit: (
            [FAKE_TOOL],
            [],
        ),
    )

    exit_code = extractor.main(["--clone-root", str(tmp_path)])

    assert exit_code == extractor.EXIT_OK

    written = json.loads(raw.read_text(encoding="utf-8"))
    assert written["count"] == 1
    assert written["tools"] == [FAKE_TOOL]

    written_report = json.loads(report.read_text(encoding="utf-8"))
    assert written_report["total_tools"] == 1
    assert written_report["validation_errors"] == []
    assert list(tmp_path.rglob("*.tmp")) == []
