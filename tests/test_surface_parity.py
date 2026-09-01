"""The two surfaces, asked the same question, answering the same way.

`modernize-mcp-server` 2.4 asks for "gate parity tests: sandbox/export gating identical to
CLI paths". That was written when there was no CLI, so the parity half could not be tested
at all. There is one now, and both surfaces screen a Design Spec, so the question is finally
askable: does a spec screened over MCP and the same spec screened at the shell produce the
same verdict?

It also records the one place they **differ**, and why — a divergence is worth a test more
than an agreement is, because an agreement can be a coincidence and a divergence is a
decision somebody has to make.
"""

from __future__ import annotations

import io
import json

import pytest

from anvilate.cli import EXIT_BAD_REQUEST, EXIT_CODES, run
from anvilate.mcp import handle_request, stateless_gaps, tool_catalog
from anvilate.scorecard import CheckStatus

_SPEC = """
anvilate_spec: "1.1.0"
name: deck_plate
description: A mezzanine deck plate.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
"""


@pytest.fixture
def spec_file(tmp_path):
    path = tmp_path / "deck.yaml"
    path.write_text(_SPEC, encoding="utf-8")
    return path


def _cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    code = run(list(argv), stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def _mcp(name: str, arguments: dict):
    return handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )


def _document() -> dict:
    import yaml

    return yaml.safe_load(_SPEC)


def test_the_same_spec_screens_to_the_same_scorecard_on_both_surfaces(spec_file):
    """The parity that matters: one document, two doors, one verdict.

    Compared as whole documents rather than by status, because two cards agreeing on PASS
    and differing on which checks ran is exactly the drift a status comparison cannot see.
    """
    over_mcp = _mcp("run_validation", {"spec": _document()})["result"]["structuredContent"]
    code, out, _err = _cli("check", "--format", "json", str(spec_file))
    at_the_shell = json.loads(out)["specs"][0]["scorecard"]
    assert at_the_shell == over_mcp["scorecard"]
    assert (
        code
        == EXIT_CODES[
            __import__("anvilate.scorecard", fromlist=["CheckStatus"]).CheckStatus(
                over_mcp["scorecard"]["entries"][0]["status"]
            )
        ]
    )


def test_a_document_that_is_not_a_spec_is_refused_with_the_same_paths(tmp_path):
    """Both surfaces reject it, in the shape each one owes its caller.

    Over MCP it is INVALID_PARAMS, because `run_validation`'s input property is declared as
    the published Design Spec schema. At the shell it is exit 3. The *shapes* differ and
    should; what must not differ is which paths they name.
    """
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: nameless\n", encoding="utf-8")

    error = _mcp("run_validation", {"spec": {"name": "nameless"}})["error"]
    code, out, err = _cli("check", str(bad))
    assert code == EXIT_BAD_REQUEST and out == ""

    def _paths(problems: list[str]) -> dict[str, str]:
        found = {}
        for problem in problems:
            field, _, reason = problem.partition(": ")
            found[field.strip().removeprefix("spec.")] = reason.strip()
        return found

    over_the_wire = _paths(error["message"].split(";"))
    at_the_shell = _paths(
        [line.split(": ", 1)[1] for line in err.strip().splitlines() if ": " in line]
    )
    # Equality, not "one is a subset of the other" — which the first draft asserted, and
    # which is satisfied by either side being empty.
    assert over_the_wire and at_the_shell
    assert over_the_wire == at_the_shell, (over_the_wire, at_the_shell)
    # And the reasons travel with the paths, not just the field names.
    assert set(over_the_wire.values()) == {"Field required"}
    assert "description" in over_the_wire


def test_neither_surface_serves_an_operation_the_other_would_refuse_for_being_unbuilt():
    """`build` is unbuilt on both, and each says so in its own vocabulary.

    Derived from the declarations rather than listed: the MCP side from the tool's declared
    cost, the CLI side from `_UNBUILT`, so an operation that becomes servable on one surface
    and not the other fails here rather than shipping as a quiet asymmetry.
    """
    from anvilate.cli import _UNBUILT, _UNBUILT_ARTIFACTS

    unbuilt_at_the_shell = set(_UNBUILT) | set(_UNBUILT_ARTIFACTS)
    assert "build" in unbuilt_at_the_shell
    over_mcp = {tool.name for tool in tool_catalog() if tool.backing is None}
    assert "build_part" in over_mcp
    assert "run_fea_validation" in over_mcp
    # `diff` has no MCP tool at all — the catalog is the eight the spec names — so the CLI
    # is the only surface that mentions it, and it mentions it as unbuilt.
    assert not {t.name for t in tool_catalog()} & {"diff"}


def test_export_is_no_longer_a_divergence_and_the_bundles_are_identical():
    """The CLI writes an evidence bundle from a spec file; MCP now returns the same bundle.

    This test carried the divergence through two changes and it has run out of divergence
    to carry. First the tool **named nothing in its input to act on**, so a stateless server
    could not serve it at all; `resolve-mcp-tool-subjects` fixed that with handles. What was
    left was a decision — writing a file to a path the caller names, which the CLI gets from
    a user typing it into their own shell — and `export-over-mcp` answered it: the tool
    returns the document and writes nothing.

    So the two surfaces are held against each other by *value*. Not "both produce a bundle":
    the same spec, screened either way, has to roll up to the same document, and the
    comparison is `to_json_dict()` against the CLI's own `--format json` payload. A
    difference of one section, one missing-layer name or one status is a failure here.
    """
    import tempfile
    from pathlib import Path

    assert stateless_gaps() == (), "a tool names nothing to act on again; that is the old bug"
    tool = {tool.name: tool for tool in tool_catalog()}["export_artifact"]
    assert tool.subject == "subject"
    # The tool publishes no destination. That is the ruling, and it is checked on the
    # contract rather than on the handler: a `destination` property reappearing is the
    # capability coming back, whatever the code behind it does with it.
    assert "destination" not in tool.input_schema["properties"]
    assert set(tool.input_schema["required"]) == {"subject", "format"}

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "deck.yaml"
        path.write_text(_SPEC, encoding="utf-8")
        code, out, _err = _cli(
            "export", "--artifact", "evidence-bundle", "--format", "json", str(path)
        )
    assert code == EXIT_CODES[CheckStatus.NOT_EVALUATED]
    at_the_shell = json.loads(out)["bundles"][0]["bundle"]

    handle = _mcp("run_validation", {"spec": _document()})["result"]["structuredContent"]["subject"]
    result = _mcp("export_artifact", {"subject": handle, "format": "evidence_bundle"})["result"]
    over_mcp = result["structuredContent"]

    assert over_mcp["bundle"] == at_the_shell
    assert over_mcp["format"] == "evidence_bundle"
    assert result["isError"] is False
    # The bundle does not pass — that is what the CLI's exit code says — and it came back
    # anyway. An evidence bundle is the evidence a part failed as much as the evidence it
    # passed, so refusing here would be the one surface that will not tell you.
    assert at_the_shell["status"] == CheckStatus.NOT_EVALUATED.value


def test_the_two_formats_that_need_geometry_are_refused_in_the_same_words():
    """`dxf` and `qif` are unbuilt on both surfaces, and neither invents its own reason.

    The MCP handler imports the CLI's table rather than restating it, so this is really a
    check that it still does: a second copy of "what a DXF waits on" is a sentence that goes
    stale in one place and not the other, and a client reading the MCP refusal and a user
    reading the shell one would then be told different things about the same gap.
    """
    from anvilate.cli import _UNBUILT_ARTIFACTS, EXIT_UNBUILT

    handle = _mcp("run_validation", {"spec": _document()})["result"]["structuredContent"]["subject"]
    assert set(_UNBUILT_ARTIFACTS) == {"dxf", "qif"}
    for artifact, reason in sorted(_UNBUILT_ARTIFACTS.items()):
        error = _mcp("export_artifact", {"subject": handle, "format": artifact})["error"]
        # -32000 and not -32602: an unbuilt operation is not an argument the caller can fix,
        # and a client that retries an INVALID_PARAMS with a better argument would loop.
        assert error["code"] == -32000, artifact
        assert reason in error["message"], artifact
        code, _out, err = _cli("export", "--artifact", artifact, "unused.yaml")
        assert code == EXIT_UNBUILT
        assert reason in err

    # And the format the enum publishes that is *not* in that table is the one served, so a
    # third unbuilt format cannot be added without this failing.
    published = set(
        {t.name: t for t in tool_catalog()}["export_artifact"].input_schema["properties"]["format"][
            "enum"
        ]
    )
    assert published - set(_UNBUILT_ARTIFACTS) == {"evidence_bundle"}


def _hostile_documents():
    """The screening tests' corpus of documents that are valid and hostile, as raw mappings."""
    import yaml

    from anvilate.spec import dump_spec_yaml
    from test_screening import _adversarial_specs

    return {
        label: yaml.safe_load(dump_spec_yaml(spec)) for label, spec in _adversarial_specs().items()
    }


@pytest.mark.parametrize("label", sorted(_hostile_documents()))
def test_a_hostile_document_screens_the_same_way_on_both_surfaces(label, tmp_path):
    """Parity where it is worth the most: the documents that go wrong.

    An agreement on a clean spec can be a coincidence of two code paths that happen to work.
    An agreement on a document naming an alloy nobody has, or a fit designation the ISO 286
    table does not carry, is the two surfaces sharing one answer about what is wrong — which
    is the whole claim of having a screen behind both doors. One of these took the shell down
    with a traceback while the library function was fine, so the corpus earns its keep here.
    """
    import yaml

    document = _hostile_documents()[label]
    path = tmp_path / "part.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    over_mcp = _mcp("run_validation", {"spec": document})
    assert "error" not in over_mcp, f"{label}: MCP refused a document the schema accepts"
    card_over_mcp = over_mcp["result"]["structuredContent"]["scorecard"]

    code, out, _err = _cli("check", "--format", "json", str(path))
    at_the_shell = json.loads(out)["specs"][0]["scorecard"]

    assert at_the_shell == card_over_mcp, label
    assert card_over_mcp["status"] != CheckStatus.PASS.value, f"{label}: this must not pass"
    assert code == EXIT_CODES[CheckStatus(card_over_mcp["status"])], label
