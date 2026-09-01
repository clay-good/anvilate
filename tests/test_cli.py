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
    assert text.splitlines()[-1] == f"2 specs: {payload['status'].upper()}"

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
    assert text.splitlines()[-1] == "2 bundles: FAIL"
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
