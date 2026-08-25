"""The MCP tool contracts, and an attack on the gate that guards them.

A catalog check that only ever runs against the catalog it ships with is a check nobody
has seen fail. So half of this file is the adversary: a stale schema reference, a
permissive schema, a required field that does not exist, an operation added or dropped —
each mutated deliberately, each asserted to produce a complaint naming it.
"""

from __future__ import annotations

import importlib
import io
import json

import pytest
from pydantic import ValidationError

from anvilate.contracts import (
    JSON_SCHEMA_DIALECT,
    scorecard_json_schema,
    spec_json_schema,
)
from anvilate.mcp import (
    PROTOCOL_REVISION,
    REQUIRED_OPERATIONS,
    Cost,
    Dispatch,
    Gate,
    ToolDefinition,
    _schema_issues,
    catalog_issues,
    handle_request,
    serve_stdio,
    stateless_gaps,
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


def test_the_wire_payload_is_the_clients_own_copy():
    """What `frozen` does not cover, covered.

    Pydantic's frozen reaches the fields, not inside them: a schema dictionary handed
    straight to a client is one a client can write to, and the next reader of that
    definition would get the edit. Two things stop it — a deep copy here, and a catalog
    rebuilt on every call, so nothing a caller mutates survives to reach the gate.
    """
    definition = wire_definitions()[0]
    definition["inputSchema"]["additionalProperties"] = True
    assert tool_catalog()[0].input_schema["additionalProperties"] is False
    assert catalog_issues() == []


@pytest.mark.parametrize(
    "nesting",
    [
        {"items": {"$ref": "https://example.invalid/other.json"}},
        {"oneOf": [{"type": "null"}, {"$ref": "https://example.invalid/other.json"}]},
        {"properties": {"inner": {"$ref": "https://example.invalid/other.json"}}},
    ],
)
def test_a_reference_below_the_top_level_is_still_checked(nesting):
    """The gate's own blind spot, closed.

    Walking only the top-level properties agrees with the catalog it shipped with, because
    that is where every reference in it happens to sit. A reference one level down — inside
    an items, a oneOf, a nested object — is the ordinary way a tool schema grows.
    """
    tool = _tool()
    broken = {**tool.input_schema, "properties": {"a": {"type": "object", **nesting}}}
    issues = _schema_issues(tool, "input_schema", broken)
    assert any("example.invalid" in issue for issue in issues), issues


# --- The stateless request handler ----------------------------------------------------
#
# What is being pinned is mostly what the handler *refuses*. Two of its refusals are
# structural rather than "not built yet", and those are the ones that matter: an unbounded
# tool cannot be called synchronously at all, and four of the eight published tools name
# nothing in their input to act on, so a server with no memory between calls cannot serve
# them however complete its implementation is.


def _call(name: str, arguments: dict | None = None, request_id: int = 1) -> dict:
    return handle_request(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments if arguments is not None else {}},
        }
    )


def test_initialize_reports_the_revision_the_contracts_were_written_to():
    result = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})["result"]
    assert result["protocolVersion"] == PROTOCOL_REVISION
    assert result["capabilities"]["tools"]["listChanged"] is False, (
        "a stateless surface cannot notify a client that its tool list moved"
    )


def test_tools_list_serves_the_published_catalog_and_nothing_else():
    tools = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    assert [t["name"] for t in tools] == [t.name for t in tool_catalog()]
    assert tools == wire_definitions()


def test_a_notification_gets_no_response_at_all():
    """Including no error response — the protocol says a request without an id takes none,
    and an error is still a response."""
    assert handle_request({"jsonrpc": "2.0", "method": "tools/list"}) is None
    assert handle_request({"jsonrpc": "2.0", "method": "nonsense"}) is None


def test_an_unknown_method_or_tool_is_a_method_not_found():
    assert (
        handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/run"})["error"]["code"]
        == -32601
    )
    assert _call("polish_the_part")["error"]["code"] == -32601


def test_arguments_are_checked_against_the_published_input_schema():
    assert _call("compile_spec", {})["error"]["code"] == -32602
    assert "requires 'document'" in _call("compile_spec", {})["error"]["message"]
    assert (
        "takes no argument"
        in _call("compile_spec", {"document": {}, "extra": 1})["error"]["message"]
    )
    assert "JSON object" in _call("compile_spec", {"document": "a string"})["error"]["message"]
    # A well-formed call gets past the schema check and is dispatched — an empty document
    # is a document, and its refusal comes back as a result rather than a transport error.
    dispatched = _call("compile_spec", {"document": {}})
    assert "error" not in dispatched
    assert dispatched["result"]["isError"] is True


def test_a_boolean_is_not_a_number():
    """`isinstance(True, int)` is True in Python and a boolean is not a number in JSON, so
    a bare isinstance check would accept `width_px: true` as a pixel count."""
    message = _call("render_viewport", {"view": "iso", "width_px": True})["error"]["message"]
    assert "must be a JSON integer" in message and "boolean" in message
    # The argument check runs before the stateless refusal, so a bad argument is reported
    # as a bad argument even on a tool the server could not serve anyway.
    assert _call("render_viewport", {"view": "iso", "width_px": True})["error"]["code"] == -32602


def test_an_unbounded_tool_is_refused_synchronously_rather_than_waited_on():
    for name in ("build_part", "run_fea_validation"):
        error = _call(name, {"spec": {}})["error"]
        assert error["code"] == -32000
        assert "task-dispatched" in error["message"]
    # And the refusal follows the declared cost, not a list of names.
    unbounded = {t.name for t in tool_catalog() if t.dispatch is Dispatch.TASK}
    assert unbounded == {"build_part", "run_fea_validation"}


def test_the_four_tools_a_stateless_server_cannot_serve_are_derived_not_listed():
    """The finding this handler exists to surface.

    Four published tools name nothing in their input to act on. That is a contradiction
    between the contracts and the stateless skeleton the spec describes, and it shows up
    the moment someone tries to serve them — which is the whole reason for publishing the
    contracts before the server.
    """
    assert stateless_gaps() == (
        "render_viewport",
        "measure_geometry",
        "read_scorecard",
        "export_artifact",
    )
    for name in stateless_gaps():
        error = _call(name, _minimum_arguments(name))["error"]
        assert error["code"] == -32000
        assert "no memory between calls" in error["message"]
    # Derived from the declaration, not from the tuple above.
    assert set(stateless_gaps()) == {t.name for t in tool_catalog() if t.subject is None}


def _minimum_arguments(name: str) -> dict:
    """The required arguments of a tool, filled with values of the declared type."""
    tool = {t.name: t for t in tool_catalog()}[name]
    filler = {
        "object": {},
        "array": [],
        "string": "x",
        "number": 1.0,
        "integer": 1,
        "boolean": True,
    }
    properties = tool.input_schema["properties"]
    return {
        key: filler[properties[key].get("type", "object")]
        for key in tool.input_schema.get("required", [])
    }


def test_a_declared_subject_must_be_a_required_input():
    """The cross-check that stops the declaration drifting from the contract: a subject the
    caller cannot send, or can omit, is server-side state under another name."""
    base = {t.name: t for t in tool_catalog()}["compile_spec"]
    with pytest.raises(ValidationError, match="no such property"):
        ToolDefinition(
            **{**base.model_dump(), "subject": "blueprint"},
        )
    optional = {
        "$schema": base.input_schema["$schema"],
        "type": "object",
        "properties": {"document": {"type": "object"}},
        "required": [],
        "additionalProperties": False,
    }
    with pytest.raises(ValidationError, match="does not require it"):
        ToolDefinition(**{**base.model_dump(), "input_schema": optional})


def test_nothing_is_dispatched_yet_and_the_handler_says_so():
    """A handler that returned a plausible result for an operation nobody wired would be
    indistinguishable from a real one, which is the failure mode a tool contract makes
    most likely."""
    error = _call("run_validation", {"spec": {}})["error"]
    assert error["code"] == -32000
    assert "not dispatched yet" in error["message"]
    assert "invented" in error["message"]


def test_a_request_that_is_not_json_rpc_2_is_refused():
    assert handle_request({"id": 1, "method": "tools/list"})["error"]["code"] == -32602
    assert (
        handle_request({"jsonrpc": "1.0", "id": 1, "method": "tools/list"})["error"]["code"]
        == -32602
    )


# --- The first operation an agent can actually call -------------------------------------


def _spec_document() -> dict:
    from anvilate.spec import (
        AcceptanceCriteria,
        DesignSpec,
        Manufacturing,
        ManufacturingProcess,
        MaterialRef,
        Provenanced,
        ValidationTier,
    )
    from anvilate.units import UnitSystem

    return DesignSpec(
        name="deck_plate",
        description="A mezzanine deck plate.",
        units=Provenanced.stated(UnitSystem.SI),
        material=MaterialRef(ref="ASTM-A36"),
        manufacturing=Manufacturing(process=ManufacturingProcess.SHEET_METAL),
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
    ).model_dump(mode="json")


def test_compile_spec_round_trips_a_real_document():
    result = _call("compile_spec", {"document": _spec_document()})["result"]
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["errors"] == []
    assert structured["spec"]["name"] == "deck_plate"
    # The text content and the structured content are the same answer, not two answers.
    assert json.loads(result["content"][0]["text"]) == structured


def test_a_document_that_does_not_validate_is_a_result_and_not_a_transport_error():
    """The output schema requires `errors` and makes `spec` optional for exactly this: a
    refusal crosses as paths the caller can act on. A JSON-RPC error would tell the client
    its *request* was malformed, which it was not — the document was."""
    response = _call("compile_spec", {"document": {"name": "nameless"}})
    assert "error" not in response
    result = response["result"]
    assert result["isError"] is True
    errors = result["structuredContent"]["errors"]
    assert errors and all(":" in e for e in errors), "each error names the path it is about"
    assert "spec" not in result["structuredContent"]


def test_is_error_and_the_error_list_cannot_disagree():
    """A client that reads only the protocol flag and one that reads the structured content
    have to reach the same verdict."""
    for document, expected in ((_spec_document(), False), ({"name": "x"}, True)):
        result = _call("compile_spec", {"document": document})["result"]
        assert result["isError"] is expected
        assert bool(result["structuredContent"]["errors"]) is expected


def test_a_document_the_parser_cannot_even_attempt_is_still_a_result():
    """`parse_spec` raises SpecValidationError for a schema failure; anything else would
    otherwise escape into the transport loop and take the connection down with it."""
    response = _call("compile_spec", {"document": {"anvilate_spec": "0.0.0"}})
    assert "error" not in response
    assert response["result"]["isError"] is True


# --- The transport ----------------------------------------------------------------------


def _serve(*messages: str) -> list[dict]:
    out = io.StringIO()
    serve_stdio(io.StringIO("\n".join(messages) + "\n"), out)
    return [json.loads(line) for line in out.getvalue().splitlines()]


def test_the_stdio_loop_answers_one_line_per_request_and_none_per_notification():
    responses = _serve(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
    )
    assert [r["id"] for r in responses] == [1, 2], (
        "a client waiting for one response per request stalls if a notification produces one"
    )


def test_a_line_that_is_not_json_does_not_take_the_stream_down():
    """A stream is not a session: one client sending rubbish must not stop the server
    answering the message after it."""
    responses = _serve(
        "{not json at all",
        json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/list"}),
    )
    assert responses[0]["error"]["code"] == -32700
    assert responses[0]["id"] is None
    assert responses[1]["id"] == 7 and "result" in responses[1]


def test_a_json_value_that_is_not_an_object_is_an_invalid_request():
    responses = _serve("[1, 2, 3]", "42")
    assert [r["error"]["code"] for r in responses] == [-32600, -32600]


def test_blank_lines_are_skipped_rather_than_answered():
    responses = _serve("", "   ", json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}))
    assert len(responses) == 1


def test_the_transport_carries_a_real_compile_end_to_end():
    """The milestone: one operation an agent can call over the wire and get an answer to."""
    responses = _serve(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "compile_spec", "arguments": {"document": _spec_document()}},
            }
        )
    )
    assert responses[0]["result"]["structuredContent"]["spec"]["name"] == "deck_plate"
