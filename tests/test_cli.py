"""Tests for the CLI."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from template_linter.cli import main

GOOD = {
    "entity": {
        "id": "ENT_SAMPLE",
        "name": "sample",
        "description": "A collected specimen.",
        "fields": [
            {"name": "sample_id", "type": "string", "required": True,
             "description": "Lab-assigned identifier"},
            {"name": "status", "type": "enum", "required": True,
             "description": "Workflow state",
             "allowed_values": ["collected", "released"]},
        ],
    }
}

BAD = {
    "entity": {
        "id": "ENT_SAMPLE",
        "name": "Sample",  # not snake_case
        "description": "",  # missing
        "fields": [
            {"name": "sample_id", "type": "dropdown",  # unknown type
             "description": "Lab-assigned identifier"},
            {"name": "status", "type": "enum",  # no allowed_values
             "description": "Workflow state"},
            {"name": "batch", "type": "lookup",  # no lookup_target
             "description": "Batch"},
        ],
    }
}


@pytest.fixture
def tmpfiles(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(GOOD))
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(BAD))
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    return tmp_path


def test_clean_file_exits_zero(tmpfiles, capsys):
    assert main([str(tmpfiles / "good.json")]) == 0
    out = capsys.readouterr().out
    assert "0 error(s), 0 warning(s)" in out


def test_bad_file_exits_one(tmpfiles, capsys):
    assert main([str(tmpfiles / "bad.json")]) == 1
    out = capsys.readouterr().out
    assert "FIELD-004" in out
    assert "FIELD-006" in out
    assert "FIELD-011" in out
    assert "ENT-004" in out


def test_broken_json_exits_one(tmpfiles):
    assert main([str(tmpfiles / "broken.json")]) == 1


def test_missing_path_exits_two(capsys):
    assert main(["/does/not/exist.json"]) == 2


def test_directory_input(tmpfiles):
    assert main([str(tmpfiles)]) == 1  # bad.json fails the set


def test_json_format(tmpfiles, capsys):
    assert main([str(tmpfiles / "bad.json"), "--format", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["errors"] >= 3
    assert any(f["code"] == "FIELD-004" for f in payload["findings"])


def test_quiet_flag(tmpfiles, capsys):
    assert main([str(tmpfiles / "good.json"), "--quiet"]) == 0
    assert capsys.readouterr().out.strip() == "0 error(s), 0 warning(s)"


def test_strict_flag(tmpfiles):
    # bad.json has warnings too; strict still exits 1 (already errors)
    assert main([str(tmpfiles / "bad.json"), "--strict"]) == 1


def test_console_script_end_to_end(tmpfiles):
    proc = subprocess.run(
        [sys.executable, "-m", "template_linter.cli", str(tmpfiles / "good.json")],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "0 error(s), 0 warning(s)" in proc.stdout
