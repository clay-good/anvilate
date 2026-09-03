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
import tempfile
from pathlib import Path

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


@pytest.mark.parametrize("label", sorted(_hostile_documents()))
def test_a_hostile_document_exports_the_same_bundle_on_both_surfaces(label, tmp_path):
    """The same corpus, one door further along, because export added a join to cross.

    Screening parity is a claim about one function reached two ways. Export is not: over MCP
    the card is serialised to JSON, written to the subject store, read back and revalidated
    before a bundle is built from it, and at the shell it goes straight from `screen_spec`
    into `BundleSections`. That round-trip is a real opportunity for the two documents to
    differ — a field that dumps to JSON and does not come back, a quantity that reads back
    as a string — and it is invisible on a clean spec whose card holds nothing interesting.

    These thirteen hold something interesting: refusal details quoting a pack's own message,
    near-miss lists, a fit designation past the end of a table. If the round-trip loses
    anything, it loses it here first.
    """
    import yaml

    document = _hostile_documents()[label]
    path = tmp_path / "part.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    code, out, _err = _cli("export", "--artifact", "evidence-bundle", "--format", "json", str(path))
    at_the_shell = json.loads(out)["bundles"][0]["bundle"]

    handle = _mcp("run_validation", {"spec": document})["result"]["structuredContent"]["subject"]
    result = _mcp("export_artifact", {"subject": handle, "format": "evidence_bundle"})
    assert "error" not in result, f"{label}: MCP refused an export the shell served"
    over_mcp = result["result"]["structuredContent"]["bundle"]

    assert over_mcp == at_the_shell, label
    # And neither surface withheld the document for the part being bad, which is the case
    # the ruling turns on: these all fail, and all thirteen still produce their evidence.
    assert over_mcp["status"] != CheckStatus.PASS.value, f"{label}: this must not pass"
    assert over_mcp["disclaimer"], label
    assert code == EXIT_CODES[CheckStatus(over_mcp["status"])], label


def test_a_reviewer_holding_only_the_bundle_can_reproduce_the_card():
    """`artifact-export`'s own scenario, which nothing in this repo could make until now.

    "**WHEN** a senior engineer receives only the evidence bundle and the Anvilate release
    named in it, **THEN** they can re-run the identical analysis and obtain the same
    scorecard." That was quoted in the spec and untestable, because a bundle carried its
    verdicts and not the inputs they were computed from: there was nothing to re-run.

    So this is the scenario performed rather than described. The spec is written to a file,
    exported through each surface, and then **dropped** — everything after that line works
    from the bundle document alone: rebuild the spec out of it, screen the rebuilt spec, and
    require the card to come back identical to the one the bundle carries.

    The equality is the whole assertion. A spec that round-trips into something *similar*
    reproduces a similar analysis, which is the failure this test exists to catch and the
    one a "does it parse" check would pass.
    """
    from anvilate.screening import screen_spec
    from anvilate.spec import parse_spec

    document = _document()

    # --- at the shell
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "deck.yaml"
        path.write_text(_SPEC, encoding="utf-8")
        _code, out, _err = _cli(
            "export", "--artifact", "evidence-bundle", "--format", "json", str(path)
        )
    at_the_shell = json.loads(out)["bundles"][0]["bundle"]

    # --- over MCP
    handle = _mcp("run_validation", {"spec": document})["result"]["structuredContent"]["subject"]
    over_mcp = _mcp("export_artifact", {"subject": handle, "format": "evidence_bundle"})["result"][
        "structuredContent"
    ]["bundle"]

    del document  # only the bundle from here down

    for label, bundle in (("shell", at_the_shell), ("mcp", over_mcp)):
        assert bundle["spec"] is not None, f"{label}: the bundle carries no spec to re-run"
        reproduced = screen_spec(parse_spec(bundle["spec"])).model_dump(mode="json")
        assert reproduced == bundle["scorecard"], (
            f"{label}: re-running the analysis from the bundle alone produced a different "
            f"card than the bundle reports"
        )


def test_the_spec_the_rendered_bundle_prints_is_one_the_parser_reads_back():
    """The text bundle's spec block, round-tripped through the front door.

    The JSON bundle above hands a machine `model_dump(mode="json")`, which pydantic is
    always going to rebuild. The rendered bundle is what a person receives, and it prints
    YAML — so the question is the one that matters for a text-first tool: can
    `anvilate check` read back what `anvilate export` wrote? A spec block that renders
    beautifully and does not parse is a reproducibility claim that fails the first time
    somebody acts on it.
    """
    import textwrap

    from anvilate.screening import screen_spec
    from anvilate.spec import load_spec_yaml

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "deck.yaml"
        path.write_text(_SPEC, encoding="utf-8")
        _code, rendered, _err = _cli("export", "--artifact", "evidence-bundle", str(path))

    assert "spec:" in rendered, "the rendered bundle prints no spec block"
    block = rendered.split("spec:\n", 1)[1].rsplit("These are closed-form", 1)[0]

    # Every line of it is nested under the heading. That is what makes the block a block:
    # unindented, the spec's own top-level keys sit at column 0 beside `checks:` and
    # `assumptions:`, and there is no longer anything in the text saying where the spec
    # starts and the bundle resumes. Asserted because dedent-then-parse cannot see it —
    # dedenting an already-flush block is a no-op, so the round-trip below passed happily
    # on a rendering that had lost the indent entirely.
    indented = [line for line in block.splitlines() if line.strip()]
    assert indented, "the spec block is empty"
    assert all(line.startswith("  ") for line in indented), (
        "the rendered spec block is not nested under its heading, so nothing in the "
        "document marks where the spec ends"
    )
    recovered = load_spec_yaml(textwrap.dedent(block))

    original = screen_spec(load_spec_yaml(_SPEC)).model_dump(mode="json")
    assert screen_spec(recovered).model_dump(mode="json") == original


def test_the_two_surfaces_name_the_same_artifacts_in_their_own_spelling():
    """The vocabularies differ by a separator, and that is a decision, not an accident.

    The CLI takes `--artifact evidence-bundle`; the MCP tool takes
    `{"format": "evidence_bundle"}`. Each is idiomatic for its surface — a shell flag is
    kebab-case, a JSON enum member is snake_case — and the MCP refusal names the valid
    values, so a client that guesses wrong is told exactly what to send.

    What was missing is any statement that the split is intentional. It lived as two string
    literals in the test above, and two literals are indistinguishable from one of them
    being a typo. So the sets are compared here, normalised, which also catches the case a
    separator convention cannot excuse: an artifact added to one surface and not the other,
    or added to both under names that are not the same word.
    """
    from anvilate.cli import _ARTIFACTS

    tool = {tool.name: tool for tool in tool_catalog()}["export_artifact"]
    over_mcp = set(tool.input_schema["properties"]["format"]["enum"])
    at_the_shell = set(_ARTIFACTS)
    assert over_mcp and at_the_shell, "one surface offers no artifacts at all"

    def normalised(names: set[str]) -> set[str]:
        return {name.replace("-", "_") for name in names}

    assert normalised(over_mcp) == normalised(at_the_shell), (
        f"the surfaces offer different artifacts: only at the shell "
        f"{sorted(normalised(at_the_shell) - normalised(over_mcp))}, only over MCP "
        f"{sorted(normalised(over_mcp) - normalised(at_the_shell))}. Adding one to a single "
        "surface is how a capability becomes reachable from one door and not the other"
    )
    # And each keeps its own spelling, so this is a parity check and not a rename waiting
    # to happen: `evidence-bundle` at the shell, `evidence_bundle` over MCP.
    assert "evidence-bundle" in at_the_shell and "evidence-bundle" not in over_mcp
    assert "evidence_bundle" in over_mcp and "evidence_bundle" not in at_the_shell
