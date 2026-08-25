"""The MCP tool contracts, and an attack on the gate that guards them.

A catalog check that only ever runs against the catalog it ships with is a check nobody
has seen fail. So half of this file is the adversary: a stale schema reference, a
permissive schema, a required field that does not exist, an operation added or dropped —
each mutated deliberately, each asserted to produce a complaint naming it.
"""

from __future__ import annotations

import importlib

import pytest
from pydantic import ValidationError

from anvilate.contracts import (
    JSON_SCHEMA_DIALECT,
    scorecard_json_schema,
    spec_json_schema,
)
from anvilate.mcp import (
    REQUIRED_OPERATIONS,
    Cost,
    Dispatch,
    Gate,
    ToolDefinition,
    _schema_issues,
    catalog_issues,
    tool_catalog,
    wire_definitions,
)
from anvilate.spec import ValidationTier


def test_the_catalog_is_clean():
    assert catalog_issues() == []


def test_the_catalog_covers_exactly_the_specified_operations():
    # Named, and counted. A gate that iterates an accidentally-empty collection passes
    # while checking nothing; asserting the number means an emptied catalog fails here.
    names = [tool.name for tool in tool_catalog()]
    assert len(names) == 8
    assert set(names) == REQUIRED_OPERATIONS
    assert len(set(names)) == len(names)


def test_every_tool_returns_typed_output():
    # "structuredContent, never prose-only" is the requirement. A tool with an empty
    # output schema satisfies the letter of "has an outputSchema" and none of the point.
    for tool in tool_catalog():
        assert tool.output_schema["properties"], f"{tool.name} returns nothing typed"


def test_the_published_contracts_are_referenced_rather_than_paraphrased():
    refs = set()
    for tool in tool_catalog():
        for schema in (tool.input_schema, tool.output_schema):
            for subschema in schema["properties"].values():
                if "$ref" in subschema:
                    refs.add(subschema["$ref"])
    assert spec_json_schema()["$id"] in refs
    assert scorecard_json_schema()["$id"] in refs


def test_a_moved_schema_version_fails_the_gate(monkeypatch):
    """The whole reason the references are written out as literals.

    Bumping a published contract's version has to break the tool surface, because a tool
    schema pointing at a version that no longer exists promises a client a document it
    will not receive.
    """
    import anvilate.mcp as mcp

    moved = dict(spec_json_schema())
    moved["$id"] = "https://anvilate.dev/schemas/design-spec/9.9.9.json"
    monkeypatch.setattr(mcp, "spec_json_schema", lambda: moved)
    issues = mcp.catalog_issues()
    assert any("9.9.9" in issue for issue in issues), issues


def test_a_dropped_operation_fails_the_gate(monkeypatch):
    import anvilate.mcp as mcp

    kept = tuple(t for t in tool_catalog() if t.name != "run_fea_validation")
    monkeypatch.setattr(mcp, "_catalog", lambda: kept)
    assert any("run_fea_validation" in issue for issue in mcp.catalog_issues())


def test_an_unspecified_operation_fails_the_gate(monkeypatch):
    """A surface can grow silently as easily as it can shrink. An operation nobody wrote
    down is one no spec, no gate, and no doc page covers."""
    import anvilate.mcp as mcp

    extra = ToolDefinition(
        name="delete_everything",
        title="x",
        description="x",
        input_schema={
            "$schema": JSON_SCHEMA_DIALECT,
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
        output_schema={
            "$schema": JSON_SCHEMA_DIALECT,
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
        cost=Cost.BOUNDED,
    )
    grown = (*tool_catalog(), extra)
    monkeypatch.setattr(mcp, "_catalog", lambda: grown)
    assert any("delete_everything" in issue for issue in mcp.catalog_issues())


def _tool(**overrides) -> ToolDefinition:
    base = {
        "name": "probe",
        "title": "probe",
        "description": "probe",
        "input_schema": {
            "$schema": JSON_SCHEMA_DIALECT,
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
            "additionalProperties": False,
        },
        "output_schema": {
            "$schema": JSON_SCHEMA_DIALECT,
            "type": "object",
            "properties": {"b": {"type": "string"}},
            "required": ["b"],
            "additionalProperties": False,
        },
        "cost": Cost.BOUNDED,
    }
    base.update(overrides)
    return ToolDefinition(**base)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ({"$schema": "https://json-schema.org/draft-07/schema#"}, "dialect"),
        ({"type": "array"}, "not an object schema"),
        ({"additionalProperties": True}, "additional properties"),
        ({"required": ["nonexistent"]}, "which it does not define"),
        ({"properties": {"a": {"$ref": "https://example.invalid/other.json"}}}, "not a published"),
    ],
)
def test_each_schema_defect_is_caught(mutation, expected):
    tool = _tool()
    broken = {**tool.input_schema, **mutation}
    issues = _schema_issues(tool, "input_schema", broken)
    assert any(expected in issue for issue in issues), (mutation, issues)


def test_a_clean_schema_produces_no_complaint():
    # The other half of the mutation test: a check that complains about everything is as
    # useless as one that complains about nothing.
    tool = _tool()
    assert _schema_issues(tool, "input_schema", tool.input_schema) == []


def test_an_fea_tier_cannot_claim_bounded_cost():
    with pytest.raises(ValidationError, match="convergence tolerance"):
        _tool(tiers=(ValidationTier.T3_FEA,), cost=Cost.BOUNDED)


def test_caller_code_cannot_claim_bounded_cost():
    with pytest.raises(ValidationError, match="code this library did not write"):
        _tool(executes_caller_code=True, cost=Cost.BOUNDED)


def test_a_tier_listed_twice_is_refused():
    with pytest.raises(ValidationError, match="twice"):
        _tool(tiers=(ValidationTier.T1_ANALYTICAL, ValidationTier.T1_ANALYTICAL))


def test_the_dispatch_split_is_the_one_the_spec_states():
    """T0-T2 synchronous, FEA-class through the Tasks extension."""
    by_name = {tool.name: tool for tool in tool_catalog()}
    assert by_name["run_validation"].dispatch is Dispatch.SYNCHRONOUS
    assert by_name["run_validation"].tiers == (
        ValidationTier.T0_GEOMETRY,
        ValidationTier.T1_ANALYTICAL,
        ValidationTier.T2_DFM,
    )
    assert by_name["run_fea_validation"].dispatch is Dispatch.TASK
    assert by_name["run_fea_validation"].tiers == (ValidationTier.T3_FEA,)
    # And the rule holds across the catalog, not only for the two validation tools.
    for tool in tool_catalog():
        expected = Dispatch.TASK if tool.cost is Cost.UNBOUNDED else Dispatch.SYNCHRONOUS
        assert tool.dispatch is expected
        if ValidationTier.T3_FEA in tool.tiers:
            assert tool.dispatch is Dispatch.TASK, tool.name


def test_the_synchronous_tools_are_the_ones_that_finish():
    # The failure this guards is an agent polling for a result that was ready before the
    # first poll, and its mirror: a client timing out on the one call that matters.
    synchronous = {t.name for t in tool_catalog() if t.dispatch is Dispatch.SYNCHRONOUS}
    assert synchronous == {
        "compile_spec",
        "render_viewport",
        "measure_geometry",
        "run_validation",
        "read_scorecard",
        "export_artifact",
    }


def test_the_gates_the_surface_inherits_are_declared_on_the_tools_that_need_them():
    by_name = {tool.name: tool for tool in tool_catalog()}
    assert Gate.SANDBOX in by_name["build_part"].gates
    assert by_name["export_artifact"].gates == frozenset({Gate.VALIDATION, Gate.WATERMARK})
    # Every gate is carried by at least one tool. A gate no tool declares is a rule the
    # MCP surface has quietly stopped inheriting.
    carried = set().union(*(tool.gates for tool in tool_catalog()))
    assert carried == set(Gate)


def test_a_definition_cannot_be_edited_after_it_is_approved():
    tool = tool_catalog()[0]
    with pytest.raises(ValidationError):
        tool.name = "something_else"


def test_every_backing_symbol_resolves_on_the_live_surface():
    """The claim that an operation is built, held against the code.

    A dotted path in a table is a comment until something imports it. Four of the eight
    operations are backed today; the other four say so with None rather than naming a
    symbol that does not exist.
    """
    backed = {tool.name: tool.backing for tool in tool_catalog() if tool.backing}
    assert len(backed) == 4, backed
    for name, path in backed.items():
        module_name, _, attribute = path.partition(":")
        module = importlib.import_module(module_name)
        assert hasattr(module, attribute), f"{name} names {path}, which does not exist"


def test_the_wire_format_is_what_a_client_receives():
    definitions = wire_definitions()
    assert len(definitions) == len(tool_catalog())
    for definition in definitions:
        assert set(definition) == {
            "name",
            "title",
            "description",
            "inputSchema",
            "outputSchema",
            "_meta",
        }
        assert definition["inputSchema"]["$schema"] == JSON_SCHEMA_DIALECT
        assert definition["outputSchema"]["$schema"] == JSON_SCHEMA_DIALECT
        # Namespaced, so nothing here can collide with a protocol key of the same name.
        assert all(key.startswith("dev.anvilate/") for key in definition["_meta"])
