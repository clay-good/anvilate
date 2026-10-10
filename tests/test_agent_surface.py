"""The agent surface as a client meets it: limits met by a gate, and hints that are true.

audit-agent-surface, groups 2 and 3. Claude Code keeps 2,048 characters of a tool's
description and Codex gives a call sixty seconds; neither says so when it cuts. These hold
the catalog inside those limits, and hold each tool's read-only hint to what a call
actually leaves behind.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvilate import _outputs
from anvilate.mcp import (
    CATALOG_OPERATIONS,
    CLIENT_INSTRUCTIONS_LIMIT,
    COMBINATION_OPERATIONS,
    CONTEXT_OPERATIONS,
    REQUIRED_OPERATIONS,
    handle_request,
    tool_catalog,
    wire_definitions,
)

_REPO = Path(__file__).resolve().parents[1]

# The shortest limit either target client puts on one tool's description.
_DESCRIPTION_LIMIT = 2048


def test_every_description_fits_the_shortest_client_limit_and_says_enough():
    tools = tool_catalog()
    assert len(tools) == 12
    for tool in tools:
        assert 80 <= len(tool.description) <= _DESCRIPTION_LIMIT, (
            tool.name,
            len(tool.description),
        )
        assert len(tool.title) <= 60 and not tool.title.endswith("."), tool.name
        # One line, so a client that shows a list of tools shows a sentence and not a wall.
        assert "\n" not in tool.description, tool.name
    assert CLIENT_INSTRUCTIONS_LIMIT == _DESCRIPTION_LIMIT


def test_every_argument_an_agent_fills_says_what_it_takes():
    """A property with no description is one the agent fills by guessing."""
    undescribed = []
    for tool in tool_catalog():
        for name, schema in tool.input_schema["properties"].items():
            if "$ref" in schema:
                continue  # a published contract, described by the schema it names
            if not schema.get("description") and "enum" not in schema:
                undescribed.append(f"{tool.name}.{name}")
    assert undescribed == [], undescribed


def test_every_tool_belongs_to_one_group_and_the_groups_are_the_catalog():
    groups = (REQUIRED_OPERATIONS, CATALOG_OPERATIONS, CONTEXT_OPERATIONS, COMBINATION_OPERATIONS)
    names = [tool.name for tool in tool_catalog()]
    for name in names:
        assert sum(name in group for group in groups) == 1, name
    assert set().union(*groups) == set(names)


def test_the_hints_are_on_the_wire_and_say_nothing_reaches_out_or_destroys():
    for definition in wire_definitions():
        hints = definition["annotations"]
        assert set(hints) == {
            "title",
            "readOnlyHint",
            "destructiveHint",
            "idempotentHint",
            "openWorldHint",
        }
        assert hints["title"] == definition["title"]
        assert (hints["destructiveHint"], hints["openWorldHint"]) == (False, False)
        assert hints["idempotentHint"] is True
    read_only = {d["name"] for d in wire_definitions() if d["annotations"]["readOnlyHint"]}
    assert read_only == {
        "describe_part",
        "list_context",
        "measure_geometry",
        "read_cad_file",
        "read_scorecard",
    }


def _snapshot(*folders: Path) -> dict[str, int]:
    return {
        str(path): path.stat().st_size
        for folder in folders
        if folder.exists()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def _call(name: str, arguments: dict) -> dict:
    return handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )


@pytest.mark.parametrize("tool", [t for t in tool_catalog() if not t.writes], ids=lambda t: t.name)
def test_a_tool_that_says_it_is_read_only_leaves_nothing_behind(tool, tmp_path):
    """The hint is a claim about the world, so it is checked against the world: the output
    folder, the subject store and the context folder, before and after the call."""
    pytest.importorskip("build123d")
    import os

    from test_mcp import _dispatched_arguments

    out = tmp_path / "out"
    _outputs.set_output_folder(out)
    arguments = _dispatched_arguments(tool.name)  # may build a part or publish a card first
    store = Path(os.environ["ANVILATE_SUBJECT_STORE"])
    from anvilate.context import context_roots

    before = _snapshot(out, store, *context_roots())
    reply = _call(tool.name, arguments)
    assert "result" in reply, reply
    assert _snapshot(out, store, *context_roots()) == before


@pytest.mark.parametrize(
    "name", ["build_part", "run_validation", "compile_spec", "build_combination"]
)
def test_a_tool_that_says_it_writes_does_publish_a_handle(name, tmp_path):
    """The other direction: a writer marked read-only would be run without asking."""
    pytest.importorskip("build123d")
    import os

    from test_mcp import _dispatched_arguments

    store = Path(os.environ["ANVILATE_SUBJECT_STORE"])
    arguments = _dispatched_arguments(name)
    before = _snapshot(store)
    reply = _call(name, arguments)
    assert "subject" in json.dumps(reply["result"]["structuredContent"])
    assert _snapshot(store) != before or before, name
    assert next(t for t in tool_catalog() if t.name == name).writes


def test_the_budget_names_every_command_a_user_waits_on():
    """A command added without a budget is a wait nobody measures."""
    import argparse

    from anvilate.cli import _build_parser

    budget = json.loads(
        (_REPO / "tools" / "responsiveness" / "budget.json").read_text(encoding="utf-8")
    )["operations"]
    commands = next(
        set(action.choices)
        for action in _build_parser()._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    budgeted = {name.removeprefix("cli ") for name in budget if name.startswith("cli ")}
    # The ones with no budget, each for a stated reason, so a new command is not one of them.
    unbudgeted = {
        "doctor": "a diagnostic run once, not part of a working loop",
        "fetch": "a download, as long as the network makes it",
        "verify": "bounded by the attestation's size, not by a part",
        "diff": "two checks, each already budgeted as one",
        "export": "a check and a serialisation of its result",
        "interfaces": "bounded by the STEP file it is given",
    }
    assert budgeted | set(unbudgeted) == commands
    assert not budgeted & set(unbudgeted)
    assert budgeted == {"check", "build", "view", "parts", "read", "combine"}
    measure = (_REPO / "tools" / "responsiveness" / "measure.py").read_text(encoding="utf-8")
    for name in budget:
        assert f'"{name}"' in measure, f"{name} is budgeted and never measured"


def _audit():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "audit_inventory", _REPO / "tools" / "audit" / "inventory.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_audit_page_is_what_the_live_surface_generates():
    audit = _audit()
    assert audit.PAGE == _REPO / "docs" / "agent-surface-audit.md"
    assert audit.PAGE.read_text(encoding="utf-8") == audit.page()
    assert audit.main(["--check"]) == 0
    page = audit.page()
    for tool in tool_catalog():
        assert f"| `{tool.name}` |" in page
    # Every finding says what became of it.
    import re

    findings = re.findall(r"^\| \d+ \|.*$", page, flags=re.MULTILINE)
    assert len(findings) >= 15
    outcomes = ("**Fixed.**", "**Proposed, not applied.**", "**Open")
    for line in findings:
        assert any(word in line for word in outcomes), line


def _arguments(tool: str, state: dict, folder: Path) -> dict:
    """What an agent would send for one step, given what earlier steps returned."""
    import yaml

    if tool == "describe_part":
        return {"element_type": "mounting_plate"}
    if tool == "list_context":
        return {"folder": "."}
    if tool == "read_cad_file":
        return {"source": "plate.dxf"}
    if tool in ("run_validation", "build_part"):
        # The example spec describe_part returned, as an agent would edit and send it.
        spec = state.get("example") or yaml.safe_load(
            (_REPO / "examples" / "parts" / "mounting_plate.spec.yaml").read_text("utf-8")
        )
        return {"spec": spec}
    if tool == "build_combination":
        text = (
            _REPO / "examples" / "combinations" / "bracket_on_plate.combination.yaml"
        ).read_text("utf-8")
        return {"combination": yaml.safe_load(text)}
    if tool == "render_viewport":
        return {"subject": state["subject"], "view": "overview"}
    if tool == "export_artifact":
        return {"subject": state["subject"], "format": "step"}
    raise AssertionError(f"the journey test does not know how to call {tool}")


@pytest.mark.parametrize("journey", _audit().JOURNEYS, ids=lambda journey: journey[0])
def test_each_journey_completes_in_the_calls_the_audit_states(journey, tmp_path):
    """Each call is given only what the calls before it returned, and none may fail."""
    pytest.importorskip("build123d")
    pytest.importorskip("ezdxf")
    import shutil

    from anvilate import context

    _key, _ask, steps = journey
    out, folder = tmp_path / "out", tmp_path / "project"
    folder.mkdir()
    shutil.copy(_REPO / "examples" / "context" / "plate.dxf", folder / "plate.dxf")
    _outputs.set_output_folder(out)
    context.set_context_roots([folder])
    state: dict = {}
    assert 2 <= len(steps) <= 5
    for tool in steps:
        reply = _call(tool, _arguments(tool, state, folder))
        assert "result" in reply and not reply["result"].get("isError"), (tool, reply)
        body = reply["result"].get("structuredContent") or {}
        if "subject" in body:
            state["subject"] = body["subject"]
        if tool == "describe_part":
            state["example"] = body["catalog"]["parts"][0]["example"]
        if tool == "read_cad_file":
            # The seed is the part's parameters and the sources that cite the drawing; the
            # agent adds what the drawing cannot give and sends the spec.
            seed = body["seed"]
            assert seed["missing"] == ["name", "thickness"]
            state["example"] = {
                "name": "from-drawing",
                "description": "A plate started from plate.dxf.",
                "units": {"value": "SI", "origin": "user_stated"},
                "material": {"ref": "ASTM-A36"},
                "manufacturing": {"process": "cnc_milling"},
                "element_type": seed["element_type"],
                "element_params": {
                    **seed["element_params"],
                    "name": "from-drawing",
                    "thickness": {"magnitude": 6.0, "unit": "mm"},
                },
                "sources": seed["sources"],
                "acceptance": {"tiers": ["T1_analytical"]},
            }
    if "export_artifact" in steps:
        assert [path.suffix for path in out.iterdir() if path.suffix == ".step"] == [".step"]
    if "render_viewport" in steps:
        assert any(path.suffix == ".png" for path in out.iterdir())


def _refusal_list():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "audit_refusals", _REPO / "tools" / "audit" / "refusals.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_refusal_list_is_what_the_source_says_today():
    """Every message either surface can show, in one file to read through (audit 1.3).

    Held to the source so it cannot describe a message that has moved on. The floors are
    there because a walk that found nothing would write a short file and agree with it.
    """
    tool = _refusal_list()
    assert tool.PAGE == _REPO / "docs" / "api" / "refusal-messages.txt"
    assert tool.PAGE.read_text(encoding="utf-8") == tool.page()
    assert tool.main(["--check"]) == 0
    listed, analysis = tool.refusals()
    assert sum(len(rows) for rows in listed.values()) > 1000 and analysis > 4000
    assert {"cli.py", "mcp.py", "combination.py", "spec/validate.py"} <= set(listed)
    # Both kinds are found: a raise, and a line the command line prints to standard error.
    assert ("_read", "anvilate read: {refused}") in listed["cli.py"]
    assert any(text.startswith("mate '{self.id}' is") for _f, text in listed["combination.py"])
    built_elsewhere = sum(
        text == "<built elsewhere>" for rows in listed.values() for _f, text in rows
    )
    assert built_elsewhere < 120, "more messages are assembled where this cannot read them"


def test_a_validation_failure_is_stated_as_its_fields_and_their_reasons():
    """What five refusals passed through whole: the model's name, a dump, and a URL."""
    from pydantic import BaseModel, ValidationError

    from anvilate._models import _reason

    class Pair(BaseModel):
        first: int
        second: int

    with pytest.raises(ValidationError) as failed:
        Pair.model_validate({"first": "one"})
    said = _reason(failed.value)
    assert said.startswith("first: Input should be a valid integer")
    assert said.endswith("second: Field required")
    assert "Pair" not in said and "pydantic" not in said and "input_value" not in said
    assert _reason(ValueError("as it was")) == "as it was"


# Every refusal that offers a value in place of the one it refused, with why the offer
# cannot loosen anything (audit 4.2). A new one fails the test below until it is read.
_OFFERS_A_VALUE = {
    ("_patterns_screened.py", "build_rolling_bearing"): (
        "lists catalog bearings by name; the ratings the screen uses are the caller's own"
    ),
    ("_patterns_screened.py", "build_pipe_run"): (
        "lists catalog pipes by name; the drawing is then refused unless the bore agrees"
    ),
    ("patterns.py", "describe_part"): "lists element names; a name carries no requirement",
    ("units/quantity.py", "_validate_unit"): "names one unit, and only above a 0.8 match",
}


def test_every_refusal_that_offers_a_value_has_been_read_for_what_it_offers():
    """A refusal's suggestion is an instruction an agent follows.

    The fatigue record's offered the two nearest detail categories, one of them stronger
    than the value it refused. It now offers the rung below. These are the others that
    put a value in a refusal, each read and found to offer a name and not a requirement.
    """
    import re

    listed, _analysis = _refusal_list().refusals()
    offers = {
        (module, function)
        for module, rows in listed.items()
        for function, text in rows
        if re.search(r"closest:|did you mean|the nearest|_nearest_", text)
    }
    assert offers == set(_OFFERS_A_VALUE), sorted(offers ^ set(_OFFERS_A_VALUE))
    assert all(len(cause.split()) >= 6 for cause in _OFFERS_A_VALUE.values())


def test_the_docs_page_inventory_is_current_and_no_page_names_something_gone():
    """Each page with its index section, what links to it and what it names (audit 1.4).

    A page that names a command, an option or an MCP tool that no longer exists, or links
    to a file that is gone, fails here by name. The attack below holds that it would.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "audit_pages", _REPO / "tools" / "audit" / "pages.py"
    )
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    assert tool.PAGE.read_text(encoding="utf-8") == tool.page() and tool.main(["--check"]) == 0
    rows = tool.inventory()
    assert len(rows) >= 60
    assert not [name for name, section, _l, _g in rows if section == "not in the index"]
    assert not {name: gone for name, _s, _l, gone in rows if gone}
    by_name = {name: linked for name, _s, linked, _g in rows}
    assert "README" in by_name["parts-catalog.md"] and "combinations" in by_name["parts-catalog.md"]
    # The attack: a page naming a command, an option, a tool and a file that do not exist.
    commands, options, tools = tool._surface()
    assert {"check", "build", "read"} <= commands and "--unvalidated" in options
    assert "build_part" in tools and "frobnicate" not in commands
    (tool.DOCS / "zz-probe.md").write_text(
        "Run `anvilate frobnicate --sideways`, call the `make_part` tool, see [x](gone.md).\n",
        encoding="utf-8",
    )
    try:
        (probe,) = [gone for name, _s, _l, gone in tool.inventory() if name == "zz-probe.md"]
    finally:
        (tool.DOCS / "zz-probe.md").unlink()
    assert probe == ["link gone.md", "command frobnicate", "option --sideways", "tool make_part"]
