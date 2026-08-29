"""The headless CLI, and the exit codes a CI job actually reads.

`headless-automation` requires `anvilate build|check|export|diff` "producing the same
artifacts, scorecards, and exit codes deterministically", and until this module there was
no `anvilate` command at all. One of the four is backed today; the other three are refused
by name with what each is waiting on, because "unknown command: build" tells a script
author they typed it wrong when the truth is that the operation is specified and unbuilt.

The exit code is the interface, so most of this file is about the code rather than the
text, and the load-bearing one is 2: a card that could not be evaluated is not a pass, and
a merge gate must not go green on it.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from anvilate.cli import (
    _ARTIFACTS,
    _UNBUILT,
    _UNBUILT_ARTIFACTS,
    EXIT_BAD_REQUEST,
    EXIT_CODES,
    EXIT_FAILED,
    EXIT_NOT_EVALUATED,
    EXIT_OK,
    EXIT_UNBUILT,
    run,
)
from anvilate.scorecard import CheckStatus

_REPO = Path(__file__).resolve().parent.parent

_SPEC = """
anvilate_spec: "1.1.0"
name: deck_plate
description: A mezzanine deck plate.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
"""


def _run(*argv):
    out, err = io.StringIO(), io.StringIO()
    code = run(list(argv), stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def spec_file(tmp_path):
    path = tmp_path / "deck.yaml"
    path.write_text(_SPEC, encoding="utf-8")
    return path


def test_check_screens_a_spec_and_reports_the_card(spec_file):
    code, out, err = _run("check", str(spec_file))
    assert "deck_plate: NOT_EVALUATED" in out
    # The reason travels with the verdict — the whole point of a not-evaluated tier.
    assert "declares no structural element type" in out
    assert code == EXIT_NOT_EVALUATED
    assert err == ""


def test_a_card_that_could_not_be_evaluated_does_not_exit_zero(spec_file):
    """No-silent-green, as the thing a CI job actually branches on.

    This is the whole reason the code is not a boolean. A merge gate running
    `anvilate check` must not go green because nothing happened to fail.
    """
    code, _out, _err = _run("check", str(spec_file))
    assert code != EXIT_OK
    assert code != EXIT_FAILED, "a screen that could not run is not a screen that failed"


def test_every_scorecard_status_has_an_exit_code_and_only_pass_is_zero():
    """A fifth status must be a decision somebody makes, not a silent 0.

    The map is total over the enumeration and asserted total here, so adding a status
    without deciding its exit code fails rather than falling through to success.
    """
    assert set(EXIT_CODES) == set(CheckStatus), "a status has no exit code"
    zero = {status for status, code in EXIT_CODES.items() if code == EXIT_OK}
    assert zero == {CheckStatus.PASS, CheckStatus.OVER_MARGIN}
    assert EXIT_CODES[CheckStatus.NOT_EVALUATED] != EXIT_CODES[CheckStatus.FAIL], (
        "a card that could not be evaluated and one that failed are different answers"
    )


def test_json_output_is_the_whole_card_not_a_summary(spec_file):
    code, out, _err = _run("check", "--format", "json", str(spec_file))
    card = json.loads(out)
    assert [entry["status"] for entry in card["entries"]] == ["not_evaluated"]
    assert code == EXIT_NOT_EVALUATED


@pytest.mark.parametrize("command", sorted(_UNBUILT))
def test_an_unbuilt_command_is_refused_by_name_with_what_it_waits_on(command):
    code, out, err = _run(command)
    assert code == EXIT_UNBUILT
    assert out == ""
    assert command in err
    assert "openspec/specs/" in err, "the refusal names no place to go and read"
    assert code not in (EXIT_OK, EXIT_FAILED, EXIT_NOT_EVALUATED), (
        "an unbuilt operation must not be reportable as any kind of verdict"
    )


def test_the_unbuilt_list_is_the_specs_own_minimum_minus_what_is_backed():
    """The four commands the requirement names, split into what is backed and what is not.

    `export` was on this list for one commit, refused whole because it "writes a downstream
    artifact from a built part". True of a DXF and of QIF results, false of the evidence
    bundle, which is assembled from a scorecard and which the MCP tool's own format
    enumeration has always listed beside them. A refusal wide enough to cover something that
    works is as misleading as a missing one.
    """
    required = {"build", "check", "export", "diff"}
    assert set(_UNBUILT) == required - {"check", "export"}


def test_a_missing_file_and_an_invalid_document_are_both_bad_requests(tmp_path):
    code, out, err = _run("check", str(tmp_path / "nope.yaml"))
    assert (code, out) == (EXIT_BAD_REQUEST, "")
    assert "No such file" in err

    bad = tmp_path / "bad.yaml"
    bad.write_text("name: x\n", encoding="utf-8")
    code, out, err = _run("check", str(bad))
    assert (code, out) == (EXIT_BAD_REQUEST, "")
    # Every path, not the first: fixing a spec one error per run is the experience this
    # avoids, and the loader already produced them all.
    assert err.count("Field required") >= 4


def test_a_document_that_is_not_a_mapping_at_all_is_a_bad_request(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    code, _out, err = _run("check", str(path))
    assert code == EXIT_BAD_REQUEST
    assert err.strip(), "the refusal says nothing"


def test_the_command_runs_as_a_real_process(spec_file):
    """The console script, driven the way a CI job drives it.

    `run()` returning an int is not evidence the installed entry point exits with it — the
    two are joined by one `SystemExit` this test is the only thing to visit.
    """
    completed = subprocess.run(
        [sys.executable, "-m", "anvilate.cli", "check", str(spec_file)],
        capture_output=True,
        text=True,
        cwd=_REPO,
        env={"PYTHONPATH": str(_REPO / "src"), "PATH": "/usr/bin:/bin"},
        timeout=180,
        check=False,
    )
    assert completed.returncode == EXIT_NOT_EVALUATED, completed.stderr
    assert "deck_plate: NOT_EVALUATED" in completed.stdout


def test_the_console_script_is_declared():
    """A module nothing installs as a command is not a CLI."""
    text = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert 'anvilate = "anvilate.cli:main"' in text


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param([], id="no command"),
        pytest.param(["check"], id="check with no file"),
        pytest.param(["frobnicate"], id="unknown command"),
        pytest.param(["check", "a.yaml", "--format", "xml"], id="bad option value"),
        pytest.param(["check", "a.yaml", "--nonsense"], id="unknown option"),
    ],
)
def test_a_usage_error_can_never_be_read_as_a_verdict(argv):
    """`ArgumentParser.error` exits **2**, hardcoded, and 2 is this CLI's "could not be
    evaluated". So every usage error came back with the code the docs tell a CI job it may
    accept — `anvilate check part.yaml || [ $? -eq 2 ]` read a typo as a screen that ran and
    could not conclude. A silent green produced by the feature that exists to stop them.

    A usage error is a bad request, which is what 3 already means.
    """
    with pytest.raises(SystemExit) as exit_info:
        _run(*argv)
    code = exit_info.value.code
    assert code == EXIT_BAD_REQUEST, argv
    assert code not in (EXIT_OK, EXIT_FAILED, EXIT_NOT_EVALUATED, EXIT_UNBUILT)


def test_help_still_exits_zero():
    """`--help` goes through `exit()` rather than `error()`; asking for help is not a
    failure, and moving the error code must not have moved this one."""
    with pytest.raises(SystemExit) as exit_info:
        _run("--help")
    assert exit_info.value.code == EXIT_OK


# --- export, and the artifact that needs no geometry -------------------------------------


def test_export_renders_the_evidence_bundle_from_a_spec_alone(spec_file):
    code, out, err = _run("export", str(spec_file))
    assert "bundle NOT_EVALUATED" in out
    # The disclaimer is a constant on the rendering, so it cannot be forgotten here.
    assert "not a substitute for detailed analysis" in out
    assert code == EXIT_NOT_EVALUATED
    assert err == ""


def test_export_json_is_the_bundle_document(spec_file):
    code, out, _err = _run("export", "--format", "json", str(spec_file))
    bundle = json.loads(out)
    assert bundle["status"] == "not_evaluated"
    assert "checks" in bundle["covers"]
    assert code == EXIT_NOT_EVALUATED


@pytest.mark.parametrize("artifact", sorted(_UNBUILT_ARTIFACTS))
def test_an_artifact_that_needs_geometry_is_refused_by_name(spec_file, artifact):
    code, out, err = _run("export", "--artifact", artifact, str(spec_file))
    assert code == EXIT_UNBUILT
    assert out == ""
    assert artifact in err and "openspec/specs/" in err


def test_the_artifact_list_is_the_mcp_tools_own():
    """`export_artifact`'s published input schema names the three formats. The CLI offering
    a fourth, or silently dropping one, is a surface saying something different from the
    contract — and dropping one is how "refused whole" happened in the first place."""
    from anvilate.mcp import tool_catalog

    tool = {tool.name: tool for tool in tool_catalog()}["export_artifact"]
    published = set(tool.input_schema["properties"]["format"]["enum"])
    offered = {name.replace("-", "_") for name in _ARTIFACTS}
    assert offered == published, (offered, published)
    assert set(_UNBUILT_ARTIFACTS) < offered, "an unbuilt artifact is not even offered"


def test_the_cli_writes_no_artifact_file_anywhere(spec_file, tmp_path, monkeypatch):
    """The bundle goes to stdout because every artifact-emitting entry point in the package
    takes a mandatory `ExportAuthorization`, and there is no bundle writer behind that gate.

    A file-writing path here would be the first one outside `anvilate.export` — exactly the
    bypass the gate exists to prevent — so this asserts the export command creates nothing.
    """
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.rglob("*"))
    _run("export", str(spec_file))
    _run("export", "--format", "json", str(spec_file))
    assert set(tmp_path.rglob("*")) == before, "the CLI wrote a file"


def test_export_reports_a_bad_spec_the_same_way_check_does(tmp_path):
    """One loader for both commands, so a missing file cannot be reported two ways."""
    missing = str(tmp_path / "nope.yaml")
    check_code, _out, check_err = _run("check", missing)
    export_code, _out, export_err = _run("export", missing)
    assert check_code == export_code == EXIT_BAD_REQUEST
    assert check_err.startswith("anvilate check: ") and export_err.startswith("anvilate export: ")
    assert check_err.split(": ", 1)[1] == export_err.split(": ", 1)[1]
