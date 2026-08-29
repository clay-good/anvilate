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
    _UNBUILT,
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


def test_the_unbuilt_list_is_the_specs_own_minimum_and_check_is_not_on_it():
    """The four commands the requirement names, split into the one that is backed and the
    three that are not — so shipping `export` means deleting its entry here."""
    required = {"build", "check", "export", "diff"}
    assert set(_UNBUILT) == required - {"check"}


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
