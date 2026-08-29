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
    # stderr carries the blocking checks — see the stderr tests below.
    assert "not_evaluated: T1 analytical" in err


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
    payload = json.loads(out)
    # A list whatever the count. A shape that changes with the number of arguments is a
    # shape every caller has to branch on, and the branch is wrong the first time a
    # directory happens to hold exactly one spec.
    assert list(payload) == ["specs"] and len(payload["specs"]) == 1
    entry = payload["specs"][0]
    assert entry["path"] == str(spec_file) and entry["name"] == "deck_plate"
    assert [e["status"] for e in entry["scorecard"]["entries"]] == ["not_evaluated"]
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


def test_version_reports_what_is_installed_not_a_module_constant():
    """A script asking a tool its version is asking what it is running.

    `anvilate.__version__` answers what somebody last typed — the same defect as a
    hand-written bill of materials, one file over — so this reads the installed metadata,
    and the gate below is what keeps the two from ever disagreeing.
    """
    from importlib.metadata import version

    with pytest.raises(SystemExit) as exit_info:
        _run("--version")
    assert exit_info.value.code == EXIT_OK
    completed = subprocess.run(
        [sys.executable, "-m", "anvilate.cli", "--version"],
        capture_output=True,
        text=True,
        cwd=_REPO,
        env={"PYTHONPATH": str(_REPO / "src"), "PATH": "/usr/bin:/bin"},
        timeout=180,
        check=False,
    )
    assert completed.stdout.strip() == f"anvilate {version('anvilate')}"


def test_version_ignores_the_module_constant_when_the_two_disagree(monkeypatch):
    """The gate below keeps the two equal, which makes reading either one give the same
    answer today — so swapping the source killed no mutation. The distinction only shows
    where it matters: a version bumped in the source tree and not reinstalled. Then a script
    asking what it is running must be told what it is running.
    """
    from importlib.metadata import version

    import anvilate
    from anvilate.cli import _installed_version

    monkeypatch.setattr(anvilate, "__version__", "9.9.9-typed-by-hand")
    assert _installed_version() == version("anvilate")
    assert _installed_version() != "9.9.9-typed-by-hand"


def test_the_three_places_the_version_is_written_agree():
    """`pyproject.toml`, `anvilate.__version__`, and the installed distribution.

    Nothing joined them. A bump to `pyproject.toml` alone would leave the agent skill
    declaring one version, the CLI reporting a second, and the attestation's application
    entry a third — three literals restating the same fact, none of which can be wrong out
    loud.
    """
    import re
    from importlib.metadata import version

    import anvilate

    pyproject = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
    declared = re.search(r'(?m)^version = "([^"]+)"', pyproject)
    assert declared is not None, "pyproject declares no version"
    assert declared.group(1) == anvilate.__version__, (
        f"pyproject says {declared.group(1)}, anvilate.__version__ says {anvilate.__version__}"
    )
    assert version("anvilate") == anvilate.__version__, (
        f"the installed distribution is {version('anvilate')}, the module says "
        f"{anvilate.__version__} — reinstall, or the two have genuinely drifted"
    )


# --- many specs, and the checks a CI log has to show --------------------------------------


@pytest.fixture
def spec_tree(tmp_path):
    """A directory holding two specs and one YAML file that is not one."""
    tree = tmp_path / "parts"
    (tree / "nested").mkdir(parents=True)
    (tree / "deck.yaml").write_text(_SPEC, encoding="utf-8")
    (tree / "nested" / "beam.yaml").write_text(
        _SPEC.replace("deck_plate", "beam_a"), encoding="utf-8"
    )
    (tree / "ci-config.yaml").write_text("not: a spec\n", encoding="utf-8")
    return tree


def test_check_screens_every_spec_under_a_directory(spec_tree):
    """`headless-automation` asks for revalidating *all specs in a repository* on push."""
    code, out, err = _run("check", str(spec_tree))
    assert "deck_plate:" in out and "beam_a:" in out
    assert "2 specs: NOT_EVALUATED" in out
    assert code == EXIT_NOT_EVALUATED
    # Found by searching, carries no `anvilate_spec`: skipped, and *said* to be skipped.
    assert "ci-config.yaml: not a Design Spec, skipped" in err


def test_a_file_named_on_the_command_line_is_taken_at_its_word(spec_tree):
    """The difference from the directory case, and it matters: a document found by
    searching that is not a spec is some other YAML file, while one the caller named is an
    error, because they said it was a spec and it is not."""
    code, out, err = _run("check", str(spec_tree / "ci-config.yaml"))
    assert code == EXIT_BAD_REQUEST
    assert out == "" and "skipped" not in err
    assert err.strip(), "the refusal says nothing"


def test_an_empty_directory_is_a_bad_request_rather_than_a_pass(tmp_path):
    """The silent-green shape this most invites: nothing found, nothing failed, exit 0."""
    empty = tmp_path / "nothing"
    empty.mkdir()
    code, out, err = _run("check", str(empty))
    assert code == EXIT_BAD_REQUEST, "an empty search must not read as everything passing"
    assert out == "" and "no Design Spec found" in err


def test_the_run_reports_the_worst_verdict_it_found(spec_tree, monkeypatch):
    """One failing part fails the run, which is what a merge gate needs."""
    from anvilate import screening
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    real = screening.screen_spec

    def _fail_the_beam(spec):
        if spec.name == "beam_a":
            return Scorecard(
                entries=(
                    ScorecardEntry(
                        name="bending", status=CheckStatus.FAIL, detail="over the limit"
                    ),
                )
            )
        return real(spec)

    monkeypatch.setattr(screening, "screen_spec", _fail_the_beam)
    code, out, err = _run("check", str(spec_tree))
    assert code == EXIT_FAILED, "a failing part must outrank a not-evaluated one"
    assert "2 specs: FAIL" in out
    assert "fail: bending — over the limit" in err


def test_every_blocking_check_is_listed_on_stderr(spec_file):
    """`headless-automation`: "the process exits non-zero with the failing checks listed on
    stderr". A check that could not run is listed too and labelled as such — it blocks
    exactly as hard, and calling it a failure would be a different claim.
    """
    _code, out, err = _run("check", str(spec_file))
    assert "not_evaluated: T1 analytical" in err
    assert "fail:" not in err
    assert str(spec_file) in err, "a CI log needs to know which spec"
    # The card still goes to stdout; stderr is the summary a log shows, not a replacement.
    assert "deck_plate: NOT_EVALUATED" in out


def test_a_passing_card_writes_nothing_to_stderr(spec_file, monkeypatch):
    """The other half. A stderr line for every check would make the requirement useless."""
    from anvilate import screening
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    monkeypatch.setattr(
        screening,
        "screen_spec",
        lambda spec: Scorecard(
            entries=(ScorecardEntry(name="bending", status=CheckStatus.PASS, detail="clear"),)
        ),
    )
    code, out, err = _run("check", str(spec_file))
    assert (code, err) == (EXIT_OK, "")
    assert "PASS" in out
