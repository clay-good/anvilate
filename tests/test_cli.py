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
