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

import base64
import io
import json
import re
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


# A spec that reaches a pack screen, so a run summary has real verdicts to count.
_LUG_SPEC = """
anvilate_spec: "1.3.0"
name: padeye
description: A lifting lug.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
element_type: lifting_lug
element_params:
  name: padeye
  material: ASTM-A36
  width: {magnitude: 120.0, unit: mm}
  hole_diameter: {magnitude: 40.0, unit: mm}
  thickness: {magnitude: 20.0, unit: mm}
  load: {magnitude: 60.0, unit: kN}
constraints:
  min_safety_factor: {value: 2.0, origin: user_stated}
"""


def _hostile_documents():
    """Documents that are valid per the schema and hostile to the screen, from the screening
    tests — one corpus, exercised at both surfaces."""
    from test_screening import _adversarial_specs

    return _adversarial_specs()


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
    # `status` is the run-level verdict the text summary prints; it joined `specs` when the
    # payload stopped dropping the two conclusions the text rendering carries. The keys are
    # asserted exactly rather than by membership, so a third cannot appear unremarked.
    assert sorted(payload) == ["specs", "status"] and len(payload["specs"]) == 1
    entry = payload["specs"][0]
    assert sorted(entry) == ["governing", "name", "path", "scorecard", "status"]
    assert entry["path"] == str(spec_file) and entry["name"] == "deck_plate"
    assert [e["status"] for e in entry["scorecard"]["entries"]] == ["not_evaluated", "pass"]
    assert code == EXIT_NOT_EVALUATED


def test_the_json_says_everything_the_text_says(tmp_path):
    """Two renderings of one run, compared line by line rather than spot-checked.

    The payload used to carry `entries` and nothing else: not the card's verdict, and not
    the governing check. The verdict is recoverable from the exit code; **`governing` is not
    recoverable at all** without reimplementing `Scorecard.governing()` — the worst check by
    a specific ordering — at every call site that reads this JSON. A layer of verdicts
    dropped from a machine-readable rendering is the same silent green the interchange file
    is gated against.

    Two specs, so the run-level summary line is exercised as well as the per-spec ones —
    and they screen to *different* verdicts on purpose. Two cards that agree cannot tell a
    worst-of from a best-of, and the mutation that swaps them survived while they did.
    """
    first, second = tmp_path / "a.yaml", tmp_path / "b.yaml"
    first.write_text(_SPEC, encoding="utf-8")
    second.write_text(
        _SPEC.replace("deck_plate", "other_plate").replace("ASTM-A36", "NOT-A-REAL-ALLOY"),
        encoding="utf-8",
    )

    _code, text, _err = _run("check", str(first), str(second))
    code, raw, _err = _run("check", "--format", "json", str(first), str(second))
    payload = json.loads(raw)

    # The run-level verdict, which the text prints as its last line.
    # The prefix is the contract a log filter greps for; the counts after it say how much
    # of the run was affected, which `60 specs: FAIL` over 58 passing parts did not.
    summary = text.splitlines()[-1]
    assert summary.startswith(f"2 specs: {payload['status'].upper()}")
    assert summary.endswith("passed") or "failed" in summary or "not evaluated" in summary

    assert len(payload["specs"]) == 2
    for entry in payload["specs"]:
        block = next(b for b in text.split("\n\n") if b.startswith(f"{entry['name']}  ("))
        lines = block.splitlines()
        assert lines[0] == f"{entry['name']}  ({entry['path']}): {entry['status'].upper()}"
        governing = entry["governing"]
        printed = next(line for line in lines if line.startswith("  governing:"))
        assert governing is not None, "the text names a governing check and the JSON has none"
        assert printed.split(":", 1)[1].strip() == (f"{governing['name']} ({governing['status']})")
        # And every check in the text is one the JSON carries, with the same verdict.
        rendered = [line for line in lines[1:-1] if not line.startswith("       ")]
        assert len(rendered) == len(entry["scorecard"]["entries"])
        for line, check in zip(rendered, entry["scorecard"]["entries"], strict=True):
            assert line.split() == [check["status"], *check["name"].split()]

    verdicts = {entry["status"] for entry in payload["specs"]}
    assert verdicts == {"not_evaluated", "fail"}, verdicts
    assert payload["status"] == "fail", "the run reports the worst card, not the best"
    assert code == EXIT_FAILED


def test_the_export_roll_up_is_in_both_renderings_and_is_the_exit_code(tmp_path):
    """`check` prints its run-level verdict in text and in JSON. `export` printed it in
    neither, and a CI job publishing bundles for a repository got N blocks with the worst
    to be found by scanning them. A verdict only an exit code carries is one nobody reads
    in a log.

    The three are one computation now, so the printed line, the payload and the exit code
    cannot disagree about the same run — which is the failure having three of them invites.
    """
    first, second = tmp_path / "a.yaml", tmp_path / "b.yaml"
    first.write_text(_SPEC, encoding="utf-8")
    second.write_text(
        _SPEC.replace("deck_plate", "other_plate").replace("ASTM-A36", "NOT-A-REAL-ALLOY"),
        encoding="utf-8",
    )

    code, text, _err = _run("export", str(first), str(second))
    json_code, raw, _err = _run("export", "--format", "json", str(first), str(second))
    payload = json.loads(raw)

    assert {bundle["bundle"]["status"] for bundle in payload["bundles"]} == {
        "not_evaluated",
        "fail",
    }, "the two bundles agree, so a worst-of and a best-of are indistinguishable here"
    assert payload["status"] == "fail"
    assert text.splitlines()[-1].startswith("2 bundles: FAIL")
    assert "1 failed" in text.splitlines()[-1], "the roll-up line no longer says how many"
    assert code == json_code == EXIT_FAILED


def test_a_card_with_nothing_to_govern_says_so_in_both_renderings():
    """`governing()` returns None on an ordinary card of passing checks that carry no
    safety factor. The text prints a line saying so rather than omitting it, because a
    missing line and a card with nothing to govern must not look the same — and the JSON
    key is present and null for exactly the same reason."""
    from anvilate.cli import _render
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    card = Scorecard(
        entries=(ScorecardEntry(name="tip deflection", status=CheckStatus.PASS, detail="4.8 mm"),)
    )
    assert card.governing() is None
    assert "governing:     none" in _render("plate", card)


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
    # `diff`'s spec-change half is backed too — its requirement says "two builds of a part
    # (or a spec change)", and the parenthesis is what a merge gate reads. Only `build` has
    # no half that a spec file alone can answer.
    assert set(_UNBUILT) == required - {"check", "export", "diff"}


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


def test_every_declared_console_script_resolves_to_a_callable():
    """A module nothing installs as a command is not a CLI, and a command pointing at a
    symbol that has moved is worse — it installs fine and fails the first time it is run.

    The first version of this asserted one substring of `pyproject.toml`, which covers one
    of the two scripts and resolves neither. This is the rule `ToolDefinition.backing`
    follows, pointed at the entry points a user actually receives: import the module, get
    the attribute, require it to be callable.
    """
    import importlib
    import tomllib

    config = tomllib.loads((_REPO / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = config["project"]["scripts"]
    assert set(scripts) == {"anvilate", "anvilate-mcp"}, scripts

    for name, target in scripts.items():
        module_name, separator, attribute = target.partition(":")
        assert separator, f"{name} declares {target!r}, which names no attribute"
        module = importlib.import_module(module_name)
        entry = getattr(module, attribute, None)
        assert callable(entry), f"{name} points at {target}, which is not callable"

    # And the one this file exercises really is the one installed.
    assert scripts["anvilate"] == "anvilate.cli:main"
    from anvilate.cli import main

    assert importlib.import_module("anvilate.cli").main is main


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
    payload = json.loads(out)
    # A list whatever the count, the same shape `check --format json` uses.
    # `status` is the run-level roll-up, which is also the exit code. Keys asserted
    # exactly rather than by membership, so a third cannot appear unremarked.
    assert sorted(payload) == ["bundles", "status"] and len(payload["bundles"]) == 1
    entry = payload["bundles"][0]
    assert entry["path"] == str(spec_file) and entry["name"] == "deck_plate"
    assert entry["bundle"]["status"] == "not_evaluated"
    assert "checks" in entry["bundle"]["covers"]
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
    # Name and path, because two parts in a repository can share a name.
    assert "deck_plate  (" in out and "beam_a  (" in out
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


def test_a_run_over_many_specs_says_which_file_each_came_from(spec_tree, tmp_path):
    """Two parts in a repository can share a name — a `bracket.yaml` under two assemblies.

    The first version printed the spec's name alone, so a repo-wide run over two files with
    the same name produced two identical blocks and no way to tell which was which. The
    single-spec case is left alone: the caller named the file.
    """
    same = tmp_path / "same"
    (same / "a").mkdir(parents=True)
    (same / "b").mkdir(parents=True)
    for side in ("a", "b"):
        (same / side / "part.yaml").write_text(_SPEC, encoding="utf-8")

    _code, out, _err = _run("check", str(same))
    assert out.count("deck_plate") == 2
    assert str(same / "a" / "part.yaml") in out
    assert str(same / "b" / "part.yaml") in out

    # One spec keeps the bare name: the caller named the file, so repeating it is noise.
    _code, single, _err = _run("check", str(spec_tree / "deck.yaml"))
    assert single.startswith("deck_plate: ")


def test_every_exit_code_a_verdict_can_produce_has_a_severity():
    """The roll-up over many specs orders codes by `_EXIT_SEVERITY.index`, which raises on a
    code that is not in the list. A fifth status with a new code would reach it."""
    from anvilate.cli import _EXIT_SEVERITY

    assert set(EXIT_CODES.values()) <= set(_EXIT_SEVERITY)
    assert _EXIT_SEVERITY.index(EXIT_FAILED) > _EXIT_SEVERITY.index(EXIT_NOT_EVALUATED)
    assert _EXIT_SEVERITY.index(EXIT_NOT_EVALUATED) > _EXIT_SEVERITY.index(EXIT_OK)


# --- verify, the command the attestation capability names ---------------------------------


@pytest.fixture
def envelope(tmp_path):
    """A signed attestation on disk, with its subjects and its key beside it."""
    import json
    import runpy

    from anvilate.attestation import Attestation, LocalHmacSigner

    namespace = runpy.run_path(str(_REPO / "examples" / "attested_evidence_bundle.py"))
    key = b"a-local-key-for-the-tests"
    signed = Attestation.signed_by(namespace["_bundle"](), LocalHmacSigner(key))
    path = tmp_path / "attestation.json"
    path.write_text(json.dumps(signed.to_envelope()), encoding="utf-8")
    (tmp_path / "key.bin").write_bytes(key)
    (tmp_path / "scorecard.json").write_bytes(namespace["SCORECARD_JSON"])
    (tmp_path / "lug.dxf").write_bytes(namespace["DRAWING_DXF"])
    return path


def _verify_args(envelope, *, key=True, artifacts=("scorecard.json", "lug.dxf")):
    directory = envelope.parent
    argv = ["verify", str(envelope)]
    if key:
        argv += ["--hmac-key-file", str(directory / "key.bin")]
    for name in artifacts:
        argv += ["--artifact", f"{name}={directory / name}"]
    return argv


def test_verify_passes_only_when_the_signature_and_every_subject_were_checked(envelope):
    code, out, err = _run(*_verify_args(envelope))
    assert code == EXIT_OK
    assert out.startswith("PASS")
    assert "symmetric_verified" in out
    assert "unchecked   none" in out
    assert err == ""


def test_a_signature_nobody_checked_is_not_a_pass(envelope):
    """The rule the whole library follows about a check that could not run, at the shell.

    Without a key there is nothing to verify the signature against, and reporting that as
    success would be the single worst thing this command could do.
    """
    code, out, _err = _run(*_verify_args(envelope, key=False))
    assert code == EXIT_NOT_EVALUATED
    assert out.startswith("NOT_EVALUATED")
    assert "not_checked" in out


def test_a_subject_with_no_file_is_reported_unchecked_rather_than_assumed(envelope):
    code, out, _err = _run(*_verify_args(envelope, artifacts=("scorecard.json",)))
    assert code == EXIT_NOT_EVALUATED
    assert "unchecked   lug.dxf" in out
    assert "checked     scorecard.json" in out


def test_a_tampered_subject_fails_and_names_what_did_not_match(envelope):
    (envelope.parent / "lug.dxf").write_bytes(b"not the drawing that was attested")
    code, out, err = _run(*_verify_args(envelope))
    assert code == EXIT_FAILED
    assert out.startswith("FAIL")
    assert "lug.dxf" in err and "digest mismatch" in err


def test_a_symmetric_signature_is_not_reported_as_attestation(envelope):
    """`attested` is True only for an authorship-establishing signature.

    A shared secret proves the envelope was not altered by anyone without the key and
    proves nothing about who made it. A fully checked symmetric envelope therefore reads
    PASS with `attested=False`, and printing that pair without the reason invites exactly
    the wrong conclusion — so the reason is printed.
    """
    _code, out, _err = _run(*_verify_args(envelope))
    assert "attested=False" in out
    assert "not who made it" in out
    assert "anyone holding the key could have" in out


def test_verify_refuses_what_is_not_an_envelope(tmp_path):
    for content, expected in (
        ("not json at all", "not JSON"),
        ('{"payload": "!!!"}', "not a DSSE envelope"),
    ):
        path = tmp_path / "bad.json"
        path.write_text(content, encoding="utf-8")
        code, out, err = _run("verify", str(path))
        assert (code, out) == (EXIT_BAD_REQUEST, "")
        assert expected in err

    code, _out, err = _run("verify", str(tmp_path / "absent.json"))
    assert code == EXIT_BAD_REQUEST and "No such file" in err


def test_a_malformed_artifact_pair_is_a_bad_request(envelope):
    code, _out, err = _run("verify", str(envelope), "--artifact", "no-equals-sign")
    assert code == EXIT_BAD_REQUEST
    assert "NAME=PATH" in err


def test_verify_json_is_the_report(envelope):
    import json as json_module

    code, out, _err = _run(*_verify_args(envelope), "--format", "json")
    report = json_module.loads(out)
    assert report["signature_state"] == "symmetric_verified"
    assert sorted(report["checked_subjects"]) == ["lug.dxf", "scorecard.json"]
    assert code == EXIT_OK


def test_the_verify_json_carries_what_the_text_headline_says(envelope):
    """Three of the report's conclusions are computed rather than stored, so `model_dump`
    left all three out and the payload carried only the fields behind them.

    **`attested` is the consequential one.** A consumer reading
    `signature_state: symmetric_verified` and nothing else concludes the envelope is
    attested — which is precisely what the text headline exists to correct, because a
    shared secret proves the envelope was not altered and says nothing about who made it.
    The text printed `attested=False` and the paragraph explaining it; the JSON gave a
    machine only the half that invites the wrong conclusion.

    `status` was absent too, and so was the toolchain the requirement asks this command to
    report — which was true of one of its two renderings.
    """
    code, text, _err = _run(*_verify_args(envelope))
    _code, raw, _err = _run(*_verify_args(envelope), "--format", "json")
    payload = json.loads(raw)

    assert text.splitlines()[0] == f"{payload['status'].upper()}  attested={payload['attested']}"
    assert payload["attested"] is False, "a symmetric signature is not attestation"
    assert payload["status"] == "pass" and code == EXIT_OK

    producer = payload["producer"]
    assert f"produced by {producer['name']} {producer['version']}" in text
    listed = ", ".join(f"{c['name']} {c['version']}" for c in payload["toolchain"])
    assert f"toolchain   {listed}" in text
    assert any(component["name"] == "pint" for component in payload["toolchain"])


def test_a_signature_nobody_checked_is_not_a_pass_in_the_json_either(envelope):
    """The rule the whole library follows, on the surface a machine reads. Without a key
    the signature was not checked, and the payload must say `not_evaluated` rather than
    leave a consumer to infer it from `signature_state` alone."""
    code, raw, _err = _run(*_verify_args(envelope, key=False), "--format", "json")
    payload = json.loads(raw)
    assert payload["status"] == "not_evaluated"
    assert payload["attested"] is False
    assert code == EXIT_NOT_EVALUATED


def test_verify_reports_the_toolchain_the_envelope_attests(envelope):
    """`evidence-attestation`'s own scenario: an engineer running the verification command
    "confirms the signature, that artifact digests match, **and reports the toolchain
    versions attested**". The first version showed the first two.

    Read out of the verified statement, not out of the environment: what a verifier wants
    to know is what produced the artifact, not what is installed on the machine reading it.
    """
    import json as json_module

    from anvilate.attestation import Attestation

    statement = Attestation.model_validate(
        json_module.loads(envelope.read_text(encoding="utf-8"))
    ).statement()
    components = statement["predicate"]["bom"]["components"]
    assert components, "the fixture attests no toolchain, so this checked nothing"

    _code, out, _err = _run(*_verify_args(envelope))
    for component in components:
        assert f"{component['name']} {component['version']}" in out
    assert "produced by anvilate" in out


def test_a_toolchain_read_from_the_machine_would_be_the_wrong_answer(envelope, monkeypatch):
    """The distinction that makes the line worth printing.

    A verifier on a different machine, with different versions installed, must still be
    told what produced the artifact. So the versions shown come from the envelope, and a
    changed local environment does not move them.
    """
    import json as json_module
    from importlib import metadata

    monkeypatch.setattr(metadata, "version", lambda name: "99.99.99-local")
    _code, out, _err = _run(*_verify_args(envelope))
    assert "99.99.99-local" not in out
    statement = json_module.loads(envelope.read_text(encoding="utf-8"))
    assert statement, "the envelope is empty"


def test_an_envelope_attesting_no_toolchain_says_so(tmp_path):
    """A bundle attesting no toolchain and one whose toolchain nobody printed must not read
    the same — the vanishing-heading rule, one surface over."""
    import json as json_module
    import runpy

    from anvilate.attestation import Attestation, EnvironmentBOM

    namespace = runpy.run_path(str(_REPO / "examples" / "attested_evidence_bundle.py"))
    bundle = namespace["_bundle"]()
    bare = bundle.model_copy(
        update={
            "predicate": bundle.predicate.model_copy(
                update={
                    "bom": EnvironmentBOM(
                        application=bundle.predicate.bom.application, components=()
                    )
                }
            )
        }
    )
    path = tmp_path / "bare.json"
    path.write_text(json_module.dumps(Attestation.unsigned(bare).to_envelope()), encoding="utf-8")
    _code, out, _err = _run("verify", str(path))
    assert "toolchain   none attested" in out


# --- diff, for the half a spec change alone can answer -------------------------------------


@pytest.fixture
def spec_pair(tmp_path):
    before = tmp_path / "before.yaml"
    after = tmp_path / "after.yaml"
    before.write_text(_SPEC, encoding="utf-8")
    after.write_text(
        _SPEC.replace("A mezzanine deck plate.", "A mezzanine deck plate, revised."),
        encoding="utf-8",
    )
    return before, after


def test_diff_reports_the_spec_change_and_the_verdicts(spec_pair):
    before, after = spec_pair
    code, out, err = _run("diff", str(before), str(after))
    assert "-description: A mezzanine deck plate." in out
    assert "+description: A mezzanine deck plate, revised." in out
    assert "no verdict changed" in out
    assert code == EXIT_OK and err == ""


def test_all_three_sections_render_even_when_empty(spec_pair):
    """The vanishing-heading rule. A diff with no spec change and one nobody diffed must
    not read the same, and the geometry half is *named* rather than omitted — a reader who
    sees no mass delta should be told there is none to be had."""
    before, _after = spec_pair
    _code, out, _err = _run("diff", str(before), str(before))
    for heading in ("SPEC", "CHECKS", "GEOMETRY"):
        assert heading in out
    assert "no change" in out
    assert "no verdict changed" in out
    assert "need two built parts" in out


def test_a_check_that_regressed_fails_the_run_and_is_named(spec_pair, monkeypatch):
    """`headless-automation`'s scenario: a commit changes a shared pattern and a downstream
    part's validation now fails, and CI fails on that part."""
    from anvilate import screening
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    def _screen(spec):
        status = CheckStatus.FAIL if "revised" in spec.description else CheckStatus.PASS
        return Scorecard(
            entries=(ScorecardEntry(name="bending", status=status, detail="the moment"),)
        )

    monkeypatch.setattr(screening, "screen_spec", _screen)
    before, after = spec_pair
    code, out, err = _run("diff", str(before), str(after))
    assert code == EXIT_FAILED
    assert "! bending: pass → fail" in out
    assert "bending: pass → fail" in err


def test_a_check_that_was_already_failing_is_not_a_regression(spec_pair, monkeypatch):
    """A part that was failing and still fails has not got worse, and a diff that failed the
    build for it would fail every build until somebody fixed an unrelated part."""
    from anvilate import screening
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    monkeypatch.setattr(
        screening,
        "screen_spec",
        lambda spec: Scorecard(
            entries=(ScorecardEntry(name="bending", status=CheckStatus.FAIL, detail="still"),)
        ),
    )
    before, after = spec_pair
    code, out, err = _run("diff", str(before), str(after))
    assert code == EXIT_OK, "an unchanged failure is not a regression"
    assert err == ""
    assert "no verdict changed" in out


def test_an_improvement_is_reported_and_does_not_fail_the_run(spec_pair, monkeypatch):
    from anvilate import screening
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    def _screen(spec):
        status = CheckStatus.PASS if "revised" in spec.description else CheckStatus.FAIL
        return Scorecard(entries=(ScorecardEntry(name="bending", status=status, detail="d"),))

    monkeypatch.setattr(screening, "screen_spec", _screen)
    before, after = spec_pair
    code, out, err = _run("diff", str(before), str(after))
    assert code == EXIT_OK and err == ""
    assert "! bending: fail → pass" in out


def test_a_check_present_in_only_one_card_is_added_or_removed_not_regressed(spec_pair, monkeypatch):
    """A different set of checks is not a worse set. Reported as added and removed rather
    than silently counted as either."""
    from anvilate import screening
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    def _screen(spec):
        name = "shear" if "revised" in spec.description else "bending"
        return Scorecard(entries=(ScorecardEntry(name=name, status=CheckStatus.FAIL, detail="d"),))

    monkeypatch.setattr(screening, "screen_spec", _screen)
    before, after = spec_pair
    code, out, _err = _run("diff", str(before), str(after))
    assert "+ shear: added (fail)" in out
    assert "- bending: removed (was fail)" in out
    assert code == EXIT_OK, "a different set of checks is not a regression"


def test_a_regression_to_not_evaluated_still_fails_the_run(spec_pair, monkeypatch):
    """No-silent-green in the diff: a check that used to run and now cannot has got worse."""
    from anvilate import screening
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    def _screen(spec):
        status = CheckStatus.NOT_EVALUATED if "revised" in spec.description else CheckStatus.PASS
        return Scorecard(entries=(ScorecardEntry(name="bending", status=status, detail="d"),))

    monkeypatch.setattr(screening, "screen_spec", _screen)
    before, after = spec_pair
    code, _out, err = _run("diff", str(before), str(after))
    assert code == EXIT_NOT_EVALUATED
    assert "pass → not_evaluated" in err


def test_diff_is_no_longer_on_the_unbuilt_list():
    """The list is the four the requirement names minus what is backed, and `diff`'s spec
    half is backed now. Only its geometry half is not, and that is named in the output."""
    from anvilate.cli import _DIFF_NEEDS_GEOMETRY

    assert set(_UNBUILT) == {"build"}
    assert "geometry-generation" in _DIFF_NEEDS_GEOMETRY


# --- diff --format json, and the one document both renderings come off ---------------------


def _pair_screening(monkeypatch, was: CheckStatus, now: CheckStatus):
    """Screen `before.yaml` to `was` and `after.yaml` to `now`, one check called `bending`."""
    from anvilate import screening
    from anvilate.scorecard import Scorecard, ScorecardEntry

    def _screen(spec):
        status = now if "revised" in spec.description else was
        return Scorecard(entries=(ScorecardEntry(name="bending", status=status, detail="d"),))

    monkeypatch.setattr(screening, "screen_spec", _screen)


_EVERY_STATUS = (
    CheckStatus.PASS,
    CheckStatus.OVER_MARGIN,
    CheckStatus.NOT_EVALUATED,
    CheckStatus.FAIL,
)


def test_the_json_diff_is_the_only_thing_on_stdout(spec_pair):
    """A caller piping this into a parser gets a document, not a document with a headline
    printed above it — the failure mode `--format json` exists to avoid."""
    before, after = spec_pair
    code, out, err = _run("diff", "--format", "json", str(before), str(after))
    payload = json.loads(out)
    assert code == EXIT_OK and err == ""
    assert payload["before"]["path"] == str(before)
    assert payload["after"]["path"] == str(after)


def test_the_json_diff_carries_every_section_on_every_run(spec_pair):
    """The shape does not change with the content. A payload whose keys come and go is one
    every caller has to branch on, and the branch is wrong the first time a comparison turns
    out to be empty — the rule the text rendering already follows by printing `GEOMETRY` with
    nothing under it."""
    before, after = spec_pair
    sections = {"before", "after", "spec", "verdict", "checks", "geometry", "regression"}
    for arguments in ((before, before), (before, after)):
        _code, out, _err = _run("diff", "--format", "json", *[str(p) for p in arguments])
        payload = json.loads(out)
        assert set(payload) == sections, arguments
        assert set(payload["checks"]) == {"moved", "unchanged"}
        assert payload["geometry"] == {
            "compared": False,
            "reason": payload["geometry"]["reason"],
        }


@pytest.mark.parametrize("was", _EVERY_STATUS)
@pytest.mark.parametrize("now", _EVERY_STATUS)
def test_the_text_diff_is_that_same_document_rendered(spec_pair, monkeypatch, was, now):
    """The gate this whole change is built around, over all sixteen verdict pairs.

    The text rendering used to *be* the comparison, so a second renderer for JSON would have
    been a second answer to "what moved". Feeding the published payload back through
    `_render_diff` and getting the text run's own stdout is what proves there is one
    document: a JSON payload computed separately could agree on these sixteen and drift on
    the seventeenth, and this cannot.
    """
    from anvilate.cli import _render_diff

    _pair_screening(monkeypatch, was, now)
    before, after = spec_pair
    _code, text, _err = _run("diff", str(before), str(after))
    _code, out, _err = _run("diff", "--format", "json", str(before), str(after))
    assert _render_diff(json.loads(out)) + "\n" == text


@pytest.mark.parametrize("was", _EVERY_STATUS)
@pytest.mark.parametrize("now", _EVERY_STATUS)
def test_the_exit_code_is_the_regression_the_payload_publishes(spec_pair, monkeypatch, was, now):
    """`regression.status` is this payload's `governing`: the one conclusion a consumer
    cannot rebuild without reimplementing which moves count as worse — including that `fail`
    and `not_evaluated` are incomparable, which no ordering of the four expresses. The exit
    code is computed from it, so the two cannot disagree."""
    _pair_screening(monkeypatch, was, now)
    before, after = spec_pair
    code, out, _err = _run("diff", "--format", "json", str(before), str(after))
    regression = json.loads(out)["regression"]
    assert regression["regressed"] is (regression["status"] is not None)
    expected = (
        EXIT_OK if regression["status"] is None else EXIT_CODES[CheckStatus(regression["status"])]
    )
    assert code == expected


def test_both_directions_between_fail_and_not_evaluated_are_reported_as_worse(
    spec_pair, monkeypatch
):
    """Neither is an improvement: one loses the check, the other reveals a failure."""
    for was, now in (
        (CheckStatus.FAIL, CheckStatus.NOT_EVALUATED),
        (CheckStatus.NOT_EVALUATED, CheckStatus.FAIL),
    ):
        _pair_screening(monkeypatch, was, now)
        before, after = spec_pair
        _code, out, _err = _run("diff", "--format", "json", str(before), str(after))
        payload = json.loads(out)
        assert [entry["worse"] for entry in payload["checks"]["moved"]] == [True], (was, now)
        assert payload["regression"]["regressed"] is True


def test_a_deleted_check_is_not_worse_and_the_card_verdict_is_what_catches_it(
    spec_pair, monkeypatch
):
    """Deleting the failing check is how a failing gate gets silenced. `worse` stays False
    on a removal — a different set of checks is not a worse set — and what reports it instead
    is the card's own roll-up, which cannot be deleted by deleting the checks."""
    from anvilate import screening
    from anvilate.scorecard import Scorecard, ScorecardEntry

    def _screen(spec):
        if "revised" in spec.description:
            return Scorecard(
                entries=(
                    ScorecardEntry(
                        name="T1 analytical", status=CheckStatus.NOT_EVALUATED, detail="d"
                    ),
                )
            )
        return Scorecard(
            entries=(ScorecardEntry(name="bending", status=CheckStatus.FAIL, detail="d"),)
        )

    monkeypatch.setattr(screening, "screen_spec", _screen)
    before, after = spec_pair
    code, out, _err = _run("diff", "--format", "json", str(before), str(after))
    payload = json.loads(out)
    removed = [e for e in payload["checks"]["moved"] if e["change"] == "removed"]
    assert [e["name"] for e in removed] == ["bending"]
    assert removed[0]["worse"] is False
    assert payload["verdict"] == {"before": "fail", "after": "not_evaluated", "worse": True}
    assert code == EXIT_NOT_EVALUATED


def test_an_unbuilt_operation_is_refused_by_name_however_it_is_invoked():
    """`anvilate build part.yaml` is what a reader of the help types, and it used to fail
    as a *usage error*.

    "unrecognized arguments: part.yaml", exit 3 — which this CLI defines as *the request was
    wrong*. The request was not wrong. The operation is specified and unbuilt, which is what
    code 4 exists to say, and bare `anvilate build` said exactly that all along. There is no
    invocation of an unbuilt operation that would be correct, so an argparse complaint about
    the arguments can only send the caller looking in the wrong place.
    """
    for arguments in ([], ["part.yaml"], ["a.yaml", "b.yaml"], ["part.yaml", "--output", "x.step"]):
        code, _out, err = _run("build", *arguments)
        assert code == EXIT_UNBUILT, (arguments, code, err)
        assert _UNBUILT["build"] in err, (arguments, err)
        assert "unrecognized arguments" not in err, arguments


def test_a_built_command_still_reports_a_usage_error_as_one():
    """The other half: swallowing arguments for the unbuilt command must not have taught
    the built ones to swallow theirs. A missing spec is still a bad request, not a verdict.
    """
    for command, arguments in (("check", []), ("diff", ["only-one.yaml"]), ("verify", [])):
        # `ArgumentParser.error` raises rather than returning; `main` is what turns it into
        # an exit code, so the code is read off the SystemExit here as it is above.
        with pytest.raises(SystemExit) as refused:
            _run(command, *arguments)
        assert refused.value.code == EXIT_BAD_REQUEST, command


def test_asking_an_unbuilt_command_for_help_is_not_a_failure():
    """`--help` exits 0 everywhere, including here — asking what a command is waiting on is
    not the same as invoking it."""
    with pytest.raises(SystemExit) as asked:
        _run("build", "--help")
    assert asked.value.code == EXIT_OK


def test_the_diff_is_of_the_spec_not_of_the_file(tmp_path):
    """Two files that differ textually and compile to the same spec are *no change*.

    That is the whole reason to diff the typed IR rather than the bytes: a reordered
    mapping, a comment, a requoted string are edits to a file and not to a design, and a
    review comment that reports them buries the change that matters. `git diff` is the tool
    for the other question.
    """
    before = tmp_path / "before.yaml"
    after = tmp_path / "after.yaml"
    before.write_text(_SPEC, encoding="utf-8")
    lines = [line for line in _SPEC.splitlines() if line.strip()]
    after.write_text(
        "# a comment the parser drops\n" + "\n".join(reversed(lines)) + "\n", encoding="utf-8"
    )
    assert before.read_text() != after.read_text(), "the two files are identical"

    code, out, err = _run("diff", str(before), str(after))
    assert code == EXIT_OK and err == ""
    assert "no change" in out
    assert "no verdict changed" in out


def test_export_bundles_every_spec_under_a_directory(spec_tree):
    """`headless-automation` asks CI to publish evidence bundles for a repository, and a
    command taking one file at a time makes that a shell loop in a script nothing
    type-checks. `export` takes the same paths `check` does, and says so the same way."""
    code, out, err = _run("export", str(spec_tree))
    assert out.count("bundle NOT_EVALUATED") == 2
    assert str(spec_tree / "deck.yaml") in out
    assert str(spec_tree / "nested" / "beam.yaml") in out
    assert "ci-config.yaml: not a Design Spec, skipped" in err
    assert "anvilate export:" in err, "the skip line names the command that skipped it"
    assert code == EXIT_NOT_EVALUATED


def test_export_json_over_a_tree_is_one_entry_per_spec(spec_tree):
    _code, out, _err = _run("export", "--format", "json", str(spec_tree))
    bundles = json.loads(out)["bundles"]
    assert sorted(entry["name"] for entry in bundles) == ["beam_a", "deck_plate"]
    assert all(
        "scorecard" in entry["bundle"]["covers"] or entry["bundle"]["covers"] for entry in bundles
    )


def test_a_single_exported_bundle_carries_no_path_header(spec_file):
    """The same rule `check` follows: one named spec keeps the bare rendering, because the
    caller supplied the path and repeating it is noise."""
    _code, out, _err = _run("export", str(spec_file))
    assert not out.startswith("# ")
    assert out.startswith("bundle ")


def test_export_over_an_empty_directory_is_a_bad_request(tmp_path):
    empty = tmp_path / "nothing"
    empty.mkdir()
    code, out, err = _run("export", str(empty))
    assert code == EXIT_BAD_REQUEST and out == ""
    assert "anvilate export: no Design Spec found" in err


def test_export_reports_the_worst_bundle_status_over_a_tree(spec_tree, monkeypatch):
    from anvilate import screening
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    def _screen(spec):
        status = CheckStatus.FAIL if spec.name == "beam_a" else CheckStatus.PASS
        return Scorecard(entries=(ScorecardEntry(name="bending", status=status, detail="d"),))

    monkeypatch.setattr(screening, "screen_spec", _screen)
    code, _out, _err = _run("export", str(spec_tree))
    assert code == EXIT_FAILED, "one failing bundle fails the run"


# --- the help text is output too, and it can be wrong -------------------------------------


def _help(*argv) -> str:
    """`--help` goes through argparse's own printing, which writes to the real stdout
    rather than to the streams `run` is handed — so it is redirected rather than passed."""
    import contextlib

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), pytest.raises(SystemExit):
        run([*argv, "--help"])
    # Whitespace-normalised: argparse rewraps to the terminal width, so a phrase this file
    # asserts can be split across lines by nothing more than a longer command name.
    return " ".join(captured.getvalue().split())


def test_the_program_help_states_no_rule_a_command_breaks():
    """The first thing a user reads, contradicted by a command in the same output.

    It used to say "Exit code 0 only when every check passed" — `check`'s rule stated as
    the program's, and false for `diff`, whose 0 means nothing got worse and which returns
    it on a run where every check fails.
    """
    text = _help()
    assert "only when every check passed" not in text
    # It states the codes, which *are* shared, and defers what counts as failure.
    for code in ("0", "1", "2", "3", "4"):
        assert code in text
    assert "differs per command" in text
    assert "never a pass" in text, "code 2 must not be described as a kind of success"


@pytest.mark.parametrize("command", ["check", "diff", "verify", "export"])
def test_every_backed_command_explains_its_own_exit_code(command):
    """The program help defers to these, so they have to say something."""
    text = _help(command)
    assert "xit" in text, f"{command} --help says nothing about its exit code"
    assert "0" in text


def test_diff_help_says_its_zero_is_not_the_same_zero():
    """The specific confusion this exists to prevent: a reader assuming `diff` exiting 0
    means the part passes."""
    text = _help("diff")
    assert "got WORSE" in text or "got worse" in text
    assert "already failing" in text


def test_the_unbuilt_command_still_says_what_it_waits_on_in_help():
    text = _help()
    assert "geometry kernel" in text


def test_the_card_names_the_governing_check(spec_file):
    """The line a reviewer reads first, and the card did not carry it.

    `Scorecard.governing()` has always known which check is closest to (or furthest past)
    its limit — blocking status first, then utilization — and the calculation report prints
    it. The shell printed the entries in the order they were produced and left the reader
    to rank them.
    """
    _code, out, _err = _run("check", str(spec_file))
    assert "governing:" in out
    assert "T1 analytical (not_evaluated)" in out


def test_the_governing_line_is_the_scorecards_own_answer(spec_file, monkeypatch):
    """Not the first entry, and not the worst-looking one: whatever `governing()` returns.

    Blocking status outranks utilization, so a not-evaluated check governs over a passing
    one at 99% — asserted here through the shell, because a rendering that picked the first
    failing entry would agree with the library on most cards and differ on exactly the ones
    the ordering exists for.
    """
    from anvilate import screening
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    tight = ScorecardEntry.from_safety_factor("tight", computed=1.0001, required=1.0)
    blocked = ScorecardEntry(
        name="unrunnable", status=CheckStatus.NOT_EVALUATED, detail="no element type"
    )
    card = Scorecard(entries=(tight, blocked))
    monkeypatch.setattr(screening, "screen_spec", lambda spec: card)

    _code, out, _err = _run("check", str(spec_file))
    assert card.governing() is not None and card.governing().name == "unrunnable"
    assert "governing:     unrunnable (not_evaluated)" in out
    assert "governing:     tight" not in out


def test_a_card_with_nothing_to_govern_says_so(spec_file, monkeypatch):
    """`governing()` is None when nothing blocks and no check carries a safety factor — an
    ordinary card of passing deflection checks, not an error. A missing line and a card with
    nothing to govern must not look the same."""
    from anvilate import screening
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    passing = Scorecard(
        entries=(ScorecardEntry(name="deflection", status=CheckStatus.PASS, detail="clear"),)
    )
    assert passing.governing() is None
    monkeypatch.setattr(screening, "screen_spec", lambda spec: passing)

    code, out, _err = _run("check", str(spec_file))
    assert code == EXIT_OK
    assert "governing:     none" in out
    assert "nothing blocks" in out


def test_every_command_line_the_docs_print_is_one_this_cli_accepts():
    """A shell block is the part of a docs page a reader runs first.

    Nothing held them against the parser, so a renamed command or a dropped flag would ship
    as instructions — and the pages carry twelve invocations across four commands, which is
    the kind of surface that drifts a flag at a time. Held by parsing the parser rather than
    by a list here: a flag added to `check` needs no edit, and one removed fails on the page
    that still tells a reader to pass it.

    Only ```bash blocks are read. A ```text block prints Anvilate's *output*, which quotes
    command lines back — including the refusals, whose whole point is that they name a flag
    combination the parser accepted and the library then declined.
    """
    import argparse
    import re
    from pathlib import Path

    from anvilate.cli import _build_parser

    parser = _build_parser()
    commands = next(
        dict(action.choices)
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    flags = {
        name: {option for a in sub._actions for option in a.option_strings}
        for name, sub in commands.items()
    }

    repo = Path(__file__).resolve().parent.parent
    pages = [repo / "README.md", *sorted((repo / "docs").rglob("*.md"))]
    invocations = []
    for page in pages:
        for block in re.findall(r"^```bash\n(.*?)^```", page.read_text(), re.M | re.S):
            for line in block.splitlines():
                line = line.split("#", 1)[0].strip()
                match = re.match(r"anvilate\s+(\S+)((?:\s+\S+)*)", line)
                if match:
                    invocations.append((page.name, match.group(1), match.group(2).split()))

    assert len(invocations) >= 8, f"only {len(invocations)} documented command lines found"
    problems = []
    for page, command, rest in invocations:
        if command.startswith("-"):
            if command not in {option for a in parser._actions for option in a.option_strings}:
                problems.append(f"{page}: `anvilate {command}` is not an option of anvilate")
            continue
        if command not in commands:
            problems.append(
                f"{page}: `anvilate {command}` is not a command; have {sorted(commands)}"
            )
            continue
        for token in rest:
            if token.startswith("--") and token not in flags[command]:
                problems.append(
                    f"{page}: `anvilate {command} {token}` — {command} takes "
                    f"{sorted(f for f in flags[command] if f.startswith('--'))}"
                )
    assert not problems, "documented command lines the CLI would refuse:\n  " + "\n  ".join(
        problems
    )


def test_the_card_prints_the_repair_hint_under_a_failing_check():
    """The most actionable thing a failing entry carries, and the shell dropped it.

    Where a design inverse exists the hint is the value that lands exactly on the required
    margin. The calculation report printed it; `anvilate check` printed the failure and left
    the reader to solve the inverse themselves.
    """
    from anvilate.cli import _render
    from anvilate.scorecard import Direction, RepairHint, Scorecard, ScorecardEntry

    hint = RepairHint(
        parameter="thickness", direction=Direction.INCREASE, corrective_value=12.0, unit="mm"
    )
    failing = ScorecardEntry.from_safety_factor(
        "pin bearing", computed=1.0, required=2.0, repair_hint=hint
    )
    passing = ScorecardEntry.from_safety_factor("net tension", computed=2.0, required=2.0)
    rendered = _render("padeye", Scorecard(entries=(failing, passing)))

    assert "→ increase thickness to 12 mm" in rendered
    # One arrow, not two: a passing check carries no hint and must not grow a line.
    assert rendered.count("→") == 1
    # And it sits under its own entry rather than at the end of the card.
    lines = rendered.splitlines()
    assert lines.index("                 → increase thickness to 12 mm") < lines.index(
        "  pass           net tension"
    )


def test_the_card_prints_the_clause_each_check_cites():
    """The clause is what separates this from a spreadsheet, and the shell dropped it.

    `ScorecardEntry.__str__` has always appended `[reference]`; this renderer builds its own
    lines and printed the detail alone, so every cited check read at the shell as an uncited
    one. A check with no clause — a material resolving, a tier gap — grows no line.
    """
    from anvilate.cli import _render
    from anvilate.scorecard import Scorecard, ScorecardEntry

    cited = ScorecardEntry.from_safety_factor("pin bearing", computed=3.0, required=2.0).model_copy(
        update={"reference": "ASME BTH-1 §3-3"}
    )
    uncited = ScorecardEntry.from_safety_factor("net tension", computed=2.5, required=2.0)
    rendered = _render("padeye", Scorecard(entries=(cited, uncited)))

    assert "[ASME BTH-1 §3-3]" in rendered
    assert rendered.count("[ASME BTH-1 §3-3]") == 1, "one clause, on the check that cites it"
    lines = rendered.splitlines()
    assert lines.index("                 [ASME BTH-1 §3-3]") < lines.index(
        "  pass           net tension"
    )


@pytest.mark.parametrize("label", sorted(_hostile_documents()))
def test_the_command_answers_a_hostile_document_rather_than_raising(label, tmp_path):
    """The same corpus as `tests/test_screening.py`, driven through the command.

    The distinction earns itself: that corpus builds a `DesignSpec` in Python and calls
    `screen_spec`, and it missed a crash the command hit on the first try — an alloy the
    database does not carry, named inside `element_params` where a real document names it.
    A screen is not the surface a user runs; this is.
    """
    from anvilate.spec import dump_spec_yaml

    path = tmp_path / "part.yaml"
    path.write_text(dump_spec_yaml(_hostile_documents()[label]), encoding="utf-8")
    code, out, err = _run("check", str(path))
    assert code in (EXIT_FAILED, EXIT_NOT_EVALUATED), f"{label}: exited {code}"
    assert out.strip(), f"{label}: printed no card"
    assert "Traceback" not in out and "Traceback" not in err


def test_diff_reports_the_cards_own_verdict_moving(tmp_path):
    """The regression no per-check comparison can see.

    A revision that renames the element deletes every check *by name* and adds a
    not-evaluated gap in their place. Nothing "moved for the worse" under a name-by-name
    rule, so `diff` exited 0 while the part went from screened to unscreened — and a merge
    gate reading that exit code was told nothing had got worse.

    A different set of checks is still not a worse set; that decision stands. A different
    verdict is a worse verdict, and `Scorecard.status` is defined for exactly this
    comparison.
    """
    from anvilate.spec import dump_spec_yaml
    from test_screening import _lug_spec

    before = tmp_path / "before.yaml"
    after = tmp_path / "after.yaml"
    before.write_text(dump_spec_yaml(_lug_spec()), encoding="utf-8")
    after.write_text(dump_spec_yaml(_lug_spec(element_type="lifting_lugg")), encoding="utf-8")

    code, out, err = _run("diff", str(before), str(after))
    assert "VERDICT  pass → not_evaluated" in out
    assert "the card: pass → not_evaluated" in err
    assert code == EXIT_NOT_EVALUATED

    # And a revision that changes nothing about the verdict still exits 0, or every edit
    # would fail a merge gate.
    same = tmp_path / "same.yaml"
    same.write_text(
        dump_spec_yaml(_lug_spec(description="A lifting padeye, revised.")), encoding="utf-8"
    )
    code, out, _err = _run("diff", str(before), str(same))
    assert code == EXIT_OK
    assert "VERDICT  pass → pass" in out


_MALFORMED_ENVELOPES = {
    "not json at all": "{not json",
    "json that is not an object": "[1, 2, 3]",
    "an object with no envelope fields": "{}",
    "a payload that is not base64": json.dumps(
        {"payload": "!!!", "payloadType": "application/vnd.in-toto+json", "signatures": []}
    ),
    "a payload that is base64 over non-JSON": json.dumps(
        {
            "payload": "Z2FyYmFnZQ==",
            "payloadType": "application/vnd.in-toto+json",
            "signatures": [],
        }
    ),
    "signatures of the wrong type": json.dumps(
        {"payload": "e30=", "payloadType": "x", "signatures": {}}
    ),
    "a null payload": json.dumps({"payload": None, "payloadType": "x", "signatures": []}),
    # The envelope is well-formed and the payload decodes and parses — and is not a
    # statement. Everything above this line is a malformed *envelope*; the corpus stopped
    # there while the premise it is named for is "an envelope arrives from somewhere else",
    # which does not stop at the outer object. `verify_attestation` had already been
    # hardened for a payload of `[1,2,3]` and says so in its own comment, and the shell
    # crashed rendering that report.
    **{
        f"a payload that is a JSON {label}": json.dumps(
            {
                "payload": base64.b64encode(body).decode(),
                "payloadType": "application/vnd.in-toto+json",
                "signatures": [],
            }
        )
        for label, body in {
            "list": b"[1, 2, 3]",
            "string": b'"a statement"',
            "number": b"42",
            "null": b"null",
        }.items()
    },
    "a statement whose subjects are bare strings": json.dumps(
        {
            "payload": base64.b64encode(
                json.dumps(
                    {
                        "_type": "https://in-toto.io/Statement/v1",
                        "subject": ["padeye.dxf", "padeye.step"],
                        "predicateType": "https://anvilate.dev/evidence-bundle/v1",
                        "predicate": {},
                    }
                ).encode()
            ).decode(),
            "payloadType": "application/vnd.in-toto+json",
            "signatures": [],
        }
    ),
    "a statement whose predicate is a list": json.dumps(
        {
            "payload": base64.b64encode(
                json.dumps(
                    {
                        "_type": "https://in-toto.io/Statement/v1",
                        "subject": [],
                        "predicateType": "https://anvilate.dev/evidence-bundle/v1",
                        "predicate": [],
                    }
                ).encode()
            ).decode(),
            "payloadType": "application/vnd.in-toto+json",
            "signatures": [],
        }
    ),
}


@pytest.mark.parametrize("label", sorted(_MALFORMED_ENVELOPES))
@pytest.mark.parametrize("fmt", ["text", "json"])
def test_verify_refuses_a_malformed_envelope_rather_than_raising(label, fmt, tmp_path):
    """An envelope arrives from somewhere else. It is untrusted input, and a traceback is
    the one answer this command must not give to it.

    Six of the first seven were already clean refusals. The seventh — a payload that is valid
    base64 over bytes that are not JSON — produced the *right* report, saying the payload is
    not readable JSON, and then raised `JSONDecodeError` on the way to printing it: both
    renderings re-parse the payload to read the attested toolchain, and neither asked whether
    it parsed.

    **The corpus then stopped at the envelope, and the premise it is named for does not.**
    Every case above the divider is a malformed outer object; a payload that decodes, parses,
    and is a JSON *list* is a well-formed envelope carrying something that is not a statement.
    `verify_attestation` was hardened for that one and names it in its own comment, so the
    library reported it correctly — and the shell called `.get` on the list while rendering
    that report and answered with an AttributeError traceback. The guard it had covered the
    exception `statement()` raises and not the value it returns.
    """
    path = tmp_path / "envelope.json"
    path.write_text(_MALFORMED_ENVELOPES[label], encoding="utf-8")
    code, out, err = _run("verify", "--format", fmt, str(path))
    assert code in (EXIT_BAD_REQUEST, EXIT_FAILED, EXIT_NOT_EVALUATED), f"{label}: exit {code}"
    assert (out + err).strip(), f"{label}: said nothing"
    assert "Traceback" not in out and "Traceback" not in err


def test_the_command_table_lists_the_parsers_own_commands_and_flags():
    """The page is a reference, and a reference with a stale table is worse than none.

    A reader had to walk five sections to learn that `check` takes `--format` and `export`
    takes `--artifact`. The table that saves them is held against the parser in both
    directions: a command missing from it, and a flag it claims that does not exist.
    """
    import argparse
    import re
    from pathlib import Path

    from anvilate.cli import _build_parser

    page = (Path(__file__).resolve().parent.parent / "docs" / "headless-cli.md").read_text()
    start = page.index("| Command | Takes | Flags | 0 means |")
    rows = {}
    for line in page[start:].splitlines()[2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows[cells[0].strip("`")] = set(re.findall(r"`(--[\w-]+)`", cells[2]))

    parser = _build_parser()
    commands = next(
        dict(action.choices)
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    assert set(rows) == set(commands), (
        f"the table lists {sorted(rows)}; the parser has {sorted(commands)}"
    )
    for name, sub in commands.items():
        flags = {
            option
            for action in sub._actions
            for option in action.option_strings
            if option.startswith("--") and option != "--help"
        }
        assert rows[name] == flags, (
            f"{name}: the table says {sorted(rows[name])}, it takes {sorted(flags)}"
        )


def test_the_module_says_how_many_of_its_commands_are_backed():
    """A count in prose, on the module that owns the commands.

    It said "two of the four are backed" while four of five were: `diff` and `verify` had
    landed since somebody wrote it, and nothing compared the sentence to the parser. The
    same words are in `pyproject.toml` beside the console script, which is the first place a
    packager reads.
    """
    import argparse
    import re
    import tomllib

    import anvilate.cli as cli

    parser = cli._build_parser()
    commands = next(
        dict(action.choices)
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    backed = sorted(set(commands) - set(cli._UNBUILT))
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}

    claimed = re.search(r"\*\*(\w+) of the (\w+) are backed today\*\*", cli.__doc__)
    assert claimed is not None, "the module no longer says how many commands are backed"
    # The sentence counts the four `headless-automation` names; `verify` comes from the
    # attestation capability and is the "fifth" the next clause names.
    assert words[claimed.group(2).lower()] == len(commands) - 1
    assert words[claimed.group(1).lower()] == len([name for name in backed if name != "verify"])

    packaging = tomllib.loads((_REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert set(packaging["project"]["scripts"]) == {"anvilate", "anvilate-mcp"}
    comment = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
    stale = re.search(r"# The headless CLI\. (\w+) of its (\w+) commands are backed", comment)
    assert stale is not None, "the pyproject comment no longer states the split"
    assert words[stale.group(1).lower()] == len(backed)
    assert words[stale.group(2).lower()] == len(commands)


def test_show_work_prints_the_worked_calculation_the_json_already_carried():
    """The shell could not show the formula the library had already computed.

    `--format json` has always carried the whole derivation; the text rendering printed a
    safety factor and left a reader at the terminal to open Python to see where it came
    from. This is the same gap the clause, the repair hint and the governing check were
    each found in, and the same fix: print what the calculation report prints, through the
    report's own renderer, so the two cannot drift.
    """
    padeye = Path(__file__).resolve().parent.parent / "examples" / "padeye.spec.yaml"
    plain_code, plain, _err = _run("check", str(padeye))
    worked_code, worked, _err = _run("check", "--show-work", str(padeye))
    assert plain_code == worked_code == EXIT_OK

    # The default is unchanged: a flag that quietly reformats the ordinary output is a
    # flag that broke every script reading it.
    assert "σ_t = P / ((W − d) · t)" not in plain
    for line in plain.splitlines():
        assert line in worked, f"--show-work dropped a line the plain rendering had: {line!r}"

    # The three lines and the glossary, for a check that has them.
    assert "σ_t = P / ((W − d) · t)" in worked
    assert "σ_t = 60.0 kN / ((120.00 mm − 40.00 mm) · 20.00 mm)" in worked
    assert "where:" in worked
    assert "P = 60.0 kN  (lifted load)" in worked

    # And a check with no derivation says so, rather than being left out — a check missing
    # from the listing reads as one whose formula was not worth showing.
    assert "material resolution" in worked
    assert "[derivation not rendered]" in worked


def test_the_shell_and_the_report_render_one_derivation_through_one_renderer():
    """Two renderings of a derivation are two things to keep in step.

    The shell's block is the report's, indented. Held by comparing the stripped lines, so
    a change to either surface that is not a change to both fails here.
    """
    from anvilate.packs.structural import LiftingLug, screen_lifting_lug
    from anvilate.report import ReportSection
    from anvilate.units import Quantity

    lug = LiftingLug(
        name="padeye",
        width=Quantity.parse("80 mm"),
        hole_diameter=Quantity.parse("25 mm"),
        thickness=Quantity.parse("12 mm"),
        load=Quantity.parse("50 kN"),
        material="ASTM-A36",
    )
    card = screen_lifting_lug(lug, required_safety_factor=2.0)
    from anvilate.cli import _render

    shell = [line.strip() for line in _render("padeye", card, show_work=True).splitlines()]
    for entry in card.entries:
        for line in ReportSection(entry=entry).worked_lines():
            assert line.strip() in shell, line

    # And the flag is what turns it on.
    plain = _render("padeye", card)
    assert "where:" not in plain


def test_check_prints_the_work_in_the_units_the_spec_declares(tmp_path, capsys):
    """A Design Spec states the unit system its reader works in, and `check` ignored it.

    A document saying `units: US` had every worked calculation and every comparison printed
    back to it in millimetres and megapascals — the tool disregarding the one line of the
    document that says what the reader works in, on the surface most people meet first.

    Both directions, because a fix that converted everything would be the same defect with
    the systems swapped.
    """
    source = (Path(__file__).resolve().parent.parent / "examples" / "padeye.spec.yaml").read_text()
    assert "units: {value: SI" in source, "the fixture spec no longer declares SI"

    us = tmp_path / "padeye_us.spec.yaml"
    us.write_text(source.replace("units: {value: SI", "units: {value: US"), encoding="utf-8")
    assert run(["check", str(us), "--show-work"]) == EXIT_OK
    printed = capsys.readouterr().out
    assert "kip" in printed and "ksi" in printed, printed
    assert " mm" not in printed and "MPa" not in printed, printed

    si = tmp_path / "padeye_si.spec.yaml"
    si.write_text(source, encoding="utf-8")
    assert run(["check", str(si), "--show-work"]) == EXIT_OK
    printed = capsys.readouterr().out
    assert " mm" in printed and "MPa" in printed, printed
    assert "kip" not in printed and "ksi" not in printed, printed


def test_a_yaml_syntax_error_is_a_bad_request_with_a_line_number(tmp_path):
    """A tab in the indentation used to be a traceback through `yaml/scanner.py`.

    `yaml.YAMLError` descends from `Exception` and not from `ValueError`, so it fell through
    `_load`'s `(ValueError, TypeError, KeyError)` guard — and `anvilate check` answered one of
    the commonest things to get wrong in a YAML file with a stack trace and exit 1, the code
    that means a part FAILED. Five malformed shapes did it: a tab in the indentation, a tab
    after a colon, a stray tab mid-block, an unclosed bracket and an unbalanced quote.

    The same knowledge was already in this file 140 lines away — the directory scan catches
    `yaml.YAMLError` explicitly — which is what makes this a gap rather than an oversight
    about the exception hierarchy.
    """
    for label, text in (
        ("a tab in the indentation", "name: x\nacceptance:\n\ttiers: [T1_analytical]\n"),
        ("a tab after a colon", "name:\tx\ndescription: d\n"),
        ("an unclosed bracket", "name: x\nacceptance: {tiers: [T1_analytical\n"),
        ("an unbalanced quote", 'name: "x\ndescription: d\n'),
    ):
        path = tmp_path / "spec.yaml"
        path.write_text(text, encoding="utf-8")
        code, out, err = _run("check", str(path))
        assert code == EXIT_BAD_REQUEST, f"{label} answered {code}, not a bad request"
        assert out == ""
        assert "Traceback" not in err, f"{label} still answers with a stack trace"
        assert "not valid YAML" in err, f"{label}: {err!r}"
        # The line number is the whole point: "fix your YAML" without one is not help.
        assert re.search(r"line \d+, column \d+", err), f"{label} names no position: {err!r}"


def test_a_malformed_spec_in_a_searched_directory_is_not_quietly_skipped(tmp_path):
    """A repository sweep must not pass over a part nobody screened.

    `anvilate check specs/` is a merge gate. A file that will not parse cannot be told from
    "some other YAML file" by its keys — parsing is what reveals them — so a broken spec used
    to be reported as `not a Design Spec, skipped` and the run carried on to exit 0. The raw
    text still tells them apart: one that *says* `anvilate_spec` and will not parse is
    somebody's broken spec.
    """
    (tmp_path / "good.yaml").write_text(_SPEC, encoding="utf-8")
    stray = tmp_path / "notes.yaml"
    stray.write_text("unrelated: [\n", encoding="utf-8")  # malformed, and claims nothing

    # A stray malformed file is still just a stray file: skipped, reported, run continues.
    code, out, err = _run("check", str(tmp_path))
    assert code == EXIT_CODES[CheckStatus.NOT_EVALUATED], err
    assert "notes.yaml: not a Design Spec, skipped" in err
    assert "deck_plate" in out

    broken = tmp_path / "broken.yaml"
    broken.write_text('anvilate_spec: "1.3.0"\nname: b\nacceptance:\n\ttiers: [T1_analytical]\n')
    code, out, err = _run("check", str(tmp_path))
    assert code == EXIT_BAD_REQUEST, "a broken spec in the sweep did not stop the run"
    assert "broken.yaml: names anvilate_spec and is not valid YAML" in err
    assert "not a Design Spec, skipped" not in err.split("broken.yaml")[-1], (
        "the broken spec is still being described as some other YAML file"
    )


def test_a_key_declared_twice_stops_the_run_rather_than_screening_the_last_one(tmp_path):
    """The silent green this refusal exists to close, at the shell and in a sweep.

    A spec declaring `constraints` twice used to be screened against whichever copy was
    lower in the file, and **exit 0**: the first declaration was in no card, no stderr line
    and no bundle. The run has to stop on it, because the document does not say what its
    author wrote and no verdict computed from it means anything.
    """
    duplicated = _SPEC + "description: A mezzanine deck plate, actually.\n"
    spec = tmp_path / "deck.yaml"
    spec.write_text(duplicated, encoding="utf-8")

    code, out, err = _run("check", str(spec))
    assert code == EXIT_BAD_REQUEST, out
    assert "'description'" in err and "silently discards" in err

    # And in the sweep, where the alternative is worse: the file parses, so it is recognised
    # as a spec and refused by name rather than skipped as "some other YAML file".
    (tmp_path / "good.yaml").write_text(_SPEC, encoding="utf-8")
    code, _out, err = _run("check", str(tmp_path))
    assert code == EXIT_BAD_REQUEST
    assert "not a Design Spec, skipped" not in err


def test_every_documented_invocation_names_a_real_command_and_real_flags():
    """The examples, not just the reference table beside them.

    `test_the_flag_table_is_the_parsers_own` holds the *table* against the parser in both
    directions, which is the right check for a reference. It says nothing about the dozen
    `anvilate …` lines in the prose and the README — a block reading `--formt json` would
    pass it, and a copied command that argparse rejects is worse than a stale table, because
    the reader copied it in good faith.

    Every documented invocation is parsed here, with its placeholder paths swapped for a
    real spec so argparse gets as far as the flags.
    """
    import argparse
    import contextlib
    import io
    import re
    from pathlib import Path

    from anvilate.cli import _build_parser

    root = Path(__file__).resolve().parent.parent
    pages = sorted((root / "docs").rglob("*.md")) + [root / "README.md"]
    invocations: list[tuple[str, str]] = []
    for page in pages:
        for block in re.findall(r"```(?:bash|sh|console)\n(.*?)```", page.read_text(), re.S):
            for raw in block.splitlines():
                line = raw.split("#")[0].split("||")[0].strip().rstrip("\\").strip()
                if line.startswith("anvilate ") and not line.startswith("anvilate-mcp"):
                    invocations.append((page.name, line))
    assert len(invocations) >= 8, f"only {len(invocations)} documented invocations were found"

    parser = _build_parser()
    subcommands = next(
        dict(action.choices)
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    broken: list[str] = []
    for page_name, line in invocations:
        words = line.split()[1:]
        command = words[0] if words else ""
        if command not in subcommands:
            broken.append(f"{page_name}: {line!r} — {command!r} is not a command")
            continue
        # Placeholders stand in for paths the page does not ship; argparse only has to get
        # far enough to accept or reject the *flags*, so any real file will do. Only tokens
        # that LOOK like a path are swapped: substituting every non-flag word turned
        # `--format json` into `--format <a path>`, and the gate reported the page as broken
        # over a mangling of its own making.
        looks_like_a_path = re.compile(r"\.(?:ya?ml|json)$|/$")
        argv = [
            "examples/padeye.spec.yaml" if looks_like_a_path.search(word) else word
            for word in words
        ]
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                parser.parse_args(argv)
        except SystemExit:
            broken.append(f"{page_name}: {line!r} — the parser rejects it")

    assert not broken, (
        "these documented commands do not parse, so a reader who copies one is told it is a "
        "bad request:\n  " + "\n  ".join(broken)
    )


def test_the_run_summary_says_how_much_of_the_run_was_affected(tmp_path):
    """`Scorecard.__str__` argues this one level down and the run summary had the same gap.

    Its docstring: "a reader who sees `scorecard FAIL (2 checks)` knows something failed and
    not which check to fix". `60 specs: FAIL` over a run where 58 passed is the same
    sentence one level up — a reviewer scanning a CI log cannot tell two broken parts from
    sixty, and "60 specs" reads as sixty parts that failed.

    The `N specs: WORST` prefix is unchanged, because `docs/headless-cli.md` documents it and
    a log filter greps for it. The counts come after.
    """
    good = _LUG_SPEC
    for index in range(4):
        (tmp_path / f"p{index}.yaml").write_text(good.replace("padeye", f"p{index}"))
    # One part thinned until it fails.
    (tmp_path / "bad.yaml").write_text(
        good.replace("padeye", "bad").replace(
            "thickness: {magnitude: 20.0, unit: mm}", "thickness: {magnitude: 5.0, unit: mm}"
        )
    )

    code, out, _err = _run("check", str(tmp_path))
    summary = out.strip().splitlines()[-1]
    assert code == EXIT_FAILED
    assert summary.startswith("5 specs: FAIL"), summary
    assert "1 failed" in summary and "4 passed" in summary, summary

    # An all-passing run stays short: no zero counts to read past.
    (tmp_path / "bad.yaml").unlink()
    code, out, _err = _run("check", str(tmp_path))
    clean = out.strip().splitlines()[-1]
    assert code == EXIT_OK
    assert clean == "4 specs: PASS — 4 passed", clean
    assert "failed" not in clean and "not evaluated" not in clean


def test_a_file_that_is_not_utf8_is_a_bad_request_at_every_door(tmp_path):
    """The bytes-to-text boundary, one layer above the YAML syntax error above.

    `load_spec_yaml` catches everything `yaml.safe_load` can raise, and the guard around the
    *read* catches `OSError`. `UnicodeDecodeError` is neither: it descends from `ValueError`
    and is raised by `path.read_text` before any parser sees a character, so it fell through
    both and `anvilate check` answered a non-UTF-8 file with a stack trace through
    `<frozen codecs>` and exit 1 — the code that means a part FAILED. Four doors did it:
    `check` on a file, `check` on a directory, `diff` on either side, and `verify`.

    The commonest way to arrive at one is not a hostile file. It is a spec saved as "Unicode"
    from Notepad, which writes UTF-16 with a byte-order mark, so the refusal names the
    encoding that wrote it and what to re-save it as.
    """
    spec = tmp_path / "good.yaml"
    spec.write_text(_SPEC, encoding="utf-8")

    binary = tmp_path / "binary.yaml"
    binary.write_bytes(b"\x00\xff\xfe not text \x80\x81")
    utf16 = tmp_path / "utf16.yaml"
    utf16.write_bytes(_SPEC.encode("utf-16"))

    for label, argv, named in (
        ("check, binary", ("check", str(binary)), binary),
        ("check, utf-16", ("check", str(utf16)), utf16),
        ("diff, second argument", ("diff", str(spec), str(binary)), binary),
        ("diff, first argument", ("diff", str(binary), str(spec)), binary),
        ("verify", ("verify", str(utf16)), utf16),
    ):
        code, out, err = _run(*argv)
        assert code == EXIT_BAD_REQUEST, f"{label} answered {code}, not a bad request"
        assert out == ""
        assert "Traceback" not in err, f"{label} still answers with a stack trace"
        assert "UTF-8" in err, f"{label} does not say what encoding it wanted: {err!r}"
        # The file, not just the complaint: a sweep names several and "not UTF-8" alone
        # would not say which one.
        assert named.name in err, f"{label} names no file: {err!r}"

    # A byte-order mark is a fact about the file, and saying which encoding wrote it is the
    # difference between a remedy and a riddle.
    _code, _out, err = _run("check", str(utf16))
    assert "UTF-16 (little-endian)" in err, err
    assert "Re-save it as UTF-8" in err, err
    # Without one there is nothing to name, so the offending byte and its offset are.
    _code, _out, err = _run("check", str(binary))
    assert "0xff" in err and "offset 1" in err, err


def test_a_non_utf8_spec_in_a_searched_directory_is_not_quietly_skipped(tmp_path):
    """The same merge-gate hole as the malformed-YAML one, through a different exception.

    The sweep decides "somebody's broken spec" from "a stray file" on whether the raw text
    says `anvilate_spec` — and a file that will not decode has no text to search. Falling
    back to the empty string reports a UTF-16 spec as `not a Design Spec, skipped` and the
    run exits 0 over a part nobody screened. Decoding with `errors="replace"` would not
    answer it either: UTF-16 interleaves a NUL after every ASCII byte, so the token comes
    back as `a?n?v?...`. The claim is looked for in the bytes instead.
    """
    (tmp_path / "good.yaml").write_text(_SPEC, encoding="utf-8")

    # A stray binary file claims nothing: skipped, reported, and the run carries on.
    stray = tmp_path / "thumbnail.yaml"
    stray.write_bytes(b"\x89PNG\r\n\x1a\n\xff\xd8not a document")
    code, out, err = _run("check", str(tmp_path))
    assert code == EXIT_CODES[CheckStatus.NOT_EVALUATED], err
    assert "thumbnail.yaml: not a Design Spec, skipped" in err
    assert "deck_plate" in out
    assert "Traceback" not in err

    # One that says so in UTF-16 is somebody's spec, and stops the run by name.
    (tmp_path / "windows.yaml").write_bytes(_SPEC.encode("utf-16"))
    code, out, err = _run("check", str(tmp_path))
    assert code == EXIT_BAD_REQUEST, "a UTF-16 spec in the sweep did not stop the run"
    assert "windows.yaml: names anvilate_spec and is not valid UTF-8 text" in err
    assert "not a Design Spec, skipped" not in err.split("windows.yaml")[-1], (
        "the UTF-16 spec is still being described as some other YAML file"
    )


def test_every_spec_document_this_repository_ships_is_found_by_a_directory_sweep(tmp_path):
    """Two surfaces disagreed about what a Design Spec is, and one of them is the merge gate.

    A file the caller *names* is a spec if `DesignSpec` validates it, and `anvilate_spec` is
    optional there deliberately: `spec-screening` calls it "a record, not an assertion", so a
    document declaring no version is a current one. The sweep recognised a spec by that key
    alone — so a spec written without it screened when named and came back
    `not a Design Spec, skipped` when found.

    `examples/padeye.spec.yaml` is one, and it is the document the README tells a reader to
    run. `anvilate check examples/` reported it skipped and went on. Worse than the skip is
    what it did to the roll-up: over a directory of a passing spec, a failing spec and an
    unevaluated one, all three written this way, the sweep found one and the run exited 2 —
    a merge gate blocking on 1 would have let a failed part through, and the failure never
    appeared in the output at all.

    So this is held over the repository's own specs, which is where the counterexample was.
    """
    shipped = sorted((_REPO / "examples").glob("*.spec.yaml"))
    assert shipped, "no shipped spec documents found; this gate has stopped matching"

    code, out, err = _run("check", str(_REPO / "examples"))
    assert "not a Design Spec, skipped" not in err, err
    # The sweep's own count, which is the one thing that says every one of them was screened
    # rather than merely not complained about.
    assert f"{len(shipped)} specs:" in out, (
        f"the sweep screened fewer than the {len(shipped)} specs this repository ships: {out}"
    )
    # And the sweep's roll-up is never better than the worst verdict those specs reach alone.
    from anvilate.cli import _EXIT_SEVERITY

    worst = max(
        (_run("check", str(spec))[0] for spec in shipped),
        key=_EXIT_SEVERITY.index,
    )
    assert code == worst, f"the sweep answered {code}; the specs it swept are worst {worst}"


def test_a_spec_that_declares_no_version_is_screened_by_a_sweep_and_a_stray_file_is_not(
    tmp_path,
):
    """The recognition rule in both directions, on documents built for it.

    The sweep asks the loader now, so the risk moves from missing a spec to claiming a file
    that is not one. `DesignSpec` forbids unknown keys and requires five, so a CI config and a
    lockfile fail it — and a *broken* spec that declares no version is still indistinguishable
    from a stray file, which is the residual the docs state rather than paper over.
    """
    versionless = (_REPO / "examples" / "padeye.spec.yaml").read_text(encoding="utf-8")
    assert "anvilate_spec" not in versionless, (
        "the counterexample now declares a version; pick another versionless spec or this "
        "test no longer exercises the rule it was written for"
    )
    (tmp_path / "part.yaml").write_text(versionless, encoding="utf-8")
    (tmp_path / "ci-config.yaml").write_text(
        "name: ci\non: {push: {branches: [main]}}\n", encoding="utf-8"
    )
    (tmp_path / "lock.yaml").write_text("packages:\n  - name: pyyaml\n", encoding="utf-8")

    code, out, err = _run("check", str(tmp_path))
    assert code == EXIT_OK, err
    assert "padeye" in out
    assert "part.yaml: not a Design Spec, skipped" not in err
    for stray in ("ci-config.yaml", "lock.yaml"):
        assert f"{stray}: not a Design Spec, skipped" in err, f"{stray} was taken for a spec"

    # And a directory of a passing, a failing and an unevaluated spec rolls up to the worst,
    # which is what the sweep could not see when it found only the one declaring a version.
    (tmp_path / "over.yaml").write_text(
        versionless.replace("magnitude: 60.0, unit: kN", "magnitude: 600.0, unit: kN").replace(
            "name: padeye", "name: overloaded", 1
        ),
        encoding="utf-8",
    )
    code, out, err = _run("check", str(tmp_path))
    assert code == EXIT_FAILED, f"a failing spec in the sweep answered {code}: {err}"
    assert "2 specs: FAIL" in out, out


def test_a_file_the_sweep_cannot_read_stops_the_run_rather_than_reading_as_a_stray(tmp_path):
    """The third arm of the same silent green, and the one left behind twice.

    A candidate the sweep cannot open used to become `text = ""` and be reported
    `not a Design Spec, skipped` — so `anvilate check specs/` exited 0 over a part nobody
    screened, and it did so for a spec that *declares* `anvilate_spec`, because the byte probe
    that rescues an undecodable file cannot read an unreadable one either. Two ordinary ways
    to arrive here: a file mode nobody meant to set, and a symlink whose target was deleted.

    The sweep does not know what the file is, so it must not say it is something else. The
    caller asked for every part under the directory, and the answer would not be about all of
    them.
    """
    (tmp_path / "ok.yaml").write_text(_SPEC, encoding="utf-8")

    unreadable = tmp_path / "declared.yaml"
    unreadable.write_text(_SPEC, encoding="utf-8")
    assert "anvilate_spec" in _SPEC, "the point is a file that claims to be a spec"
    unreadable.chmod(0o000)
    try:
        code, out, err = _run("check", str(tmp_path))
    finally:
        unreadable.chmod(0o644)
    assert code == EXIT_BAD_REQUEST, f"an unreadable spec in the sweep answered {code}"
    assert "declared.yaml: could not be read" in err, err
    assert "not a Design Spec" not in err, "an unreadable file is not some other YAML file"
    assert "Permission denied" in err, "the refusal does not say what went wrong"

    # A symlink whose target is gone reads the same way, and is how a spec goes missing.
    (tmp_path / "declared.yaml").unlink()
    (tmp_path / "dangling.yaml").symlink_to("deleted.yaml")
    code, _out, err = _run("check", str(tmp_path))
    assert code == EXIT_BAD_REQUEST, f"a broken symlink in the sweep answered {code}"
    assert "dangling.yaml: could not be read" in err, err
    assert "No such file or directory" in err, err


def test_a_directory_the_sweep_cannot_enter_is_named_rather_than_yielding_nothing(tmp_path):
    """`rglob` swallows the error, so this one was not even a misdescription — it was silence.

    A specs subdirectory the sweep had no permission to read yielded no candidates and no line
    anywhere in the output, and the run went green over every part in it. From the outside a
    directory that is empty and one that cannot be opened are indistinguishable in the result,
    which is what made this invisible. The sweep does its own walk now so that `onerror` has
    somewhere to report to.
    """
    (tmp_path / "ok.yaml").write_text(_SPEC, encoding="utf-8")
    private = tmp_path / "private"
    private.mkdir()
    (private / "hidden.yaml").write_text(_SPEC, encoding="utf-8")
    private.chmod(0o000)
    try:
        code, out, err = _run("check", str(tmp_path))
    finally:
        private.chmod(0o755)
    assert code == EXIT_BAD_REQUEST, f"an unsearchable directory answered {code}"
    assert "private: could not be searched" in err, err
    assert "hidden.yaml" not in out, "the hidden spec cannot have been screened"
    # Readable again, the part inside is found — the refusal was about access, not about it.
    code, out, _err = _run("check", str(tmp_path))
    assert code != EXIT_BAD_REQUEST
    assert "2 specs:" in out, out


def test_a_self_referential_symlink_in_a_swept_directory_terminates(tmp_path):
    """`latest -> .` is an ordinary thing to find in a versioned directory, and the walk must
    not follow it forever. `rglob` did not follow directory symlinks and neither does this."""
    (tmp_path / "part.yaml").write_text(_SPEC, encoding="utf-8")
    (tmp_path / "latest").symlink_to(tmp_path)
    code, out, err = _run("check", str(tmp_path))
    assert code != EXIT_BAD_REQUEST, err
    # One part, counted once: the same file reached twice is not two parts.
    assert out.startswith("deck_plate: "), out


def test_deleting_a_failing_check_is_not_an_improvement(tmp_path):
    """`anvilate diff` exited 0 — "nothing regressed" — over a change that deleted two
    FAILING checks and left the tier unevaluated.

    The card comparison used `_BLOCKING_ORDER`, which sorts FAIL above NOT_EVALUATED because a
    failure is the thing to look at first. Read as an ordering of badness that makes
    `fail → not_evaluated` an *improvement*. The diff's own rendering printed
    `- padeye net tension: removed (was fail)` three lines above the exit code that
    contradicted it.

    Two ordinary edits do it, and both are what somebody reaches for when a check is in the
    way: delete the `element_type` so no pack screen is selected, or delete the `constraints`
    the checks are judged against. Deleting the thing being checked is *the* way to silence a
    failing gate, so it is the one change a merge gate must never call an improvement.
    """
    padeye = (_REPO / "examples" / "padeye.spec.yaml").read_text(encoding="utf-8")
    failing = padeye.replace("magnitude: 60.0, unit: kN", "magnitude: 600.0, unit: kN")
    before = tmp_path / "before.yaml"
    before.write_text(failing, encoding="utf-8")
    assert _run("check", str(before))[0] == EXIT_FAILED, "the 'before' spec must fail"

    silenced = {
        "the element deleted": re.sub(
            r"element_type: lifting_lug\nelement_params:\n(?:  .*\n)+", "", failing
        ),
        "the constraint deleted": re.sub(r"constraints:.*\n", "", failing),
    }
    for label, text in silenced.items():
        after = tmp_path / "after.yaml"
        after.write_text(text, encoding="utf-8")
        assert _run("check", str(after))[0] == EXIT_NOT_EVALUATED, label

        code, out, err = _run("diff", str(before), str(after))
        assert code == EXIT_NOT_EVALUATED, (
            f"{label}: diff answered {code}; a part that stopped being screened has not "
            f"improved on one that failed"
        )
        assert "the card: fail → not_evaluated" in err, f"{label}: {err!r}"
        # The rendering already said the checks went away; the exit code now agrees with it.
        assert "removed (was fail)" in out, out

    # The genuine improvement still reads as one, so this is not "every change is a regression".
    fixed = tmp_path / "fixed.yaml"
    fixed.write_text(padeye, encoding="utf-8")
    assert _run("diff", str(before), str(fixed))[0] == EXIT_OK, "fail → pass must be exit 0"


def test_no_transition_into_not_evaluated_is_ever_an_improvement():
    """Every ordered pair of statuses, stated as properties rather than as a second copy of
    the rungs — a table of expected answers derived from the code under test pins nothing.

    The last assertion is the scope of the change: exactly one pair moved, and naming it is
    what says this widened the rule by the one case it was written for rather than making
    every edit a regression.
    """
    from anvilate.cli import _BLOCKING_ORDER, _moved_for_the_worse

    statuses = list(CheckStatus)
    assert set(statuses) == set(_BLOCKING_ORDER), (
        "a status outside the blocking order would compare by an index that raises"
    )

    for status in statuses:
        assert not _moved_for_the_worse(status, status), f"{status} did not move at all"

    # Antisymmetric everywhere except one pair, and that exception is the design statement:
    # FAIL and NOT_EVALUATED are not two points on one axis of badness. Going from "it fails"
    # to "we do not know" loses the check; going the other way reveals a failure. Neither is
    # an improvement, so both directions are reported, and a single ordering cannot say that —
    # which is exactly how the blocking order came to be read as one.
    incomparable = {frozenset({CheckStatus.FAIL, CheckStatus.NOT_EVALUATED})}
    for was in statuses:
        for now in statuses:
            if was is now:
                continue
            both = _moved_for_the_worse(was, now) and _moved_for_the_worse(now, was)
            assert both == (frozenset({was, now}) in incomparable), (
                f"{was.value} → {now.value}: worse in both directions is only right for the "
                f"pair that is genuinely incomparable"
            )

    # The rule this exists for: losing the check is never an improvement.
    for was in statuses:
        if was is CheckStatus.NOT_EVALUATED:
            continue
        assert _moved_for_the_worse(was, CheckStatus.NOT_EVALUATED), (
            f"{was} → not_evaluated read as no regression; a screen that could not run is "
            f"not a screen that passed, and it has not improved on one that failed"
        )

    def by_blocking_order(was, now):
        return _BLOCKING_ORDER.index(now) > _BLOCKING_ORDER.index(was)

    moved = {
        (was.value, now.value)
        for was in statuses
        for now in statuses
        if _moved_for_the_worse(was, now) != by_blocking_order(was, now)
    }
    assert moved == {("fail", "not_evaluated")}, (
        f"this rule differs from the blocking order on {sorted(moved)}; it is meant to differ "
        f"on exactly the transition that deleted a failing check"
    )


def test_a_check_that_keeps_its_name_and_stops_being_evaluated_is_a_regression():
    """The per-check half of the same rule, constructed rather than screened.

    `_regressions` and the card comparison both read `_moved_for_the_worse`, and only the card
    comparison is reachable from a spec today: the two ways to silence a failing check delete
    it by name, and a check that goes `fail → not_evaluated` while *keeping* its name needs a
    screen that can report both under one name, which no pack does yet.

    That makes the per-check line unpinned by the end-to-end case above rather than correct by
    construction — restoring the blocking order there passes every other test in this file. So
    it is exercised directly. A pack that gains such a screen inherits the right answer, and if
    somebody reverts the line this fails.
    """
    from anvilate.cli import _regressions
    from anvilate.scorecard import Scorecard, ScorecardEntry

    def card(*pairs):
        return Scorecard(
            entries=tuple(
                ScorecardEntry(name=name, status=status, detail="d") for name, status in pairs
            )
        )

    before = card(
        ("bolt shear", CheckStatus.FAIL),
        ("weld throat", CheckStatus.PASS),
        ("bearing", CheckStatus.FAIL),
    )
    after = card(
        ("bolt shear", CheckStatus.NOT_EVALUATED),  # the check was silenced, not fixed
        ("weld throat", CheckStatus.PASS),  # unchanged
        ("bearing", CheckStatus.PASS),  # genuinely fixed
    )
    moved = _regressions(before, after)
    assert [name for name, _was, _now in moved] == ["bolt shear"], moved
    assert moved[0][1:] == (CheckStatus.FAIL, CheckStatus.NOT_EVALUATED)

    # And the reverse is reported too, because the two are incomparable rather than ordered.
    # ("bearing" comes along for the ride: pass → fail is a regression by any reading.)
    moved_back = {name: (was, now) for name, was, now in _regressions(after, before)}
    assert moved_back["bolt shear"] == (CheckStatus.NOT_EVALUATED, CheckStatus.FAIL)
    assert set(moved_back) == {"bolt shear", "bearing"}, moved_back


def test_a_directory_given_to_a_command_that_takes_a_file_says_which_command_takes_one(
    tmp_path,
):
    """`[Errno 21] Is a directory: 'specs'` is true and useless.

    It names the path and says nothing to act on — least of all the thing that would explain
    the mistake, which is that `check` and `export` *do* search a directory and `diff` and
    `verify` do not. Somebody hands a directory to `diff` because they learned it works for
    `check`, so the refusal names the asymmetry.
    """
    directory = tmp_path / "specs"
    directory.mkdir()
    spec = tmp_path / "part.yaml"
    spec.write_text(_SPEC, encoding="utf-8")
    (directory / "part.yaml").write_text(_SPEC, encoding="utf-8")

    for label, argv in (
        ("diff, first argument", ("diff", str(directory), str(spec))),
        ("diff, second argument", ("diff", str(spec), str(directory))),
        ("verify", ("verify", str(directory))),
    ):
        code, out, err = _run(*argv)
        assert code == EXIT_BAD_REQUEST, label
        assert out == ""
        assert "is a directory" in err, f"{label}: {err!r}"
        assert "Errno" not in err, f"{label} still leaks an errno: {err!r}"
        # The way out, which is the half an errno cannot carry.
        for searching in ("anvilate check", "anvilate export"):
            assert searching in err, f"{label} does not name {searching}: {err!r}"

    # And the commands it names really do take one, or the advice sends the reader in circles.
    for command in ("check", "export"):
        code, out, err = _run(command, str(directory))
        assert code != EXIT_BAD_REQUEST, f"{command} was named as taking a directory: {err}"
        assert "deck_plate" in out, out


def test_an_empty_search_is_still_a_bad_request(tmp_path):
    """The sweep does its own walk now, and "nothing found, nothing failed, exit 0" is the
    silent green the directory form exists to avoid — so the empty case is checked where the
    walk was replaced rather than assumed to have survived it."""
    (tmp_path / "deeper").mkdir()
    code, out, err = _run("check", str(tmp_path))
    assert code == EXIT_BAD_REQUEST, "an empty search read as a pass"
    assert "no Design Spec found" in err
