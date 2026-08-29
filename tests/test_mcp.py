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
import pathlib

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
    """The required arguments of a tool, filled with values its own schema accepts.

    Enum-aware on purpose: a filler of "x" for an enum'd string is refused by the argument
    check before the call can reach the refusal this helper exists to provoke, and the
    test would then be asserting the wrong error.
    """
    tool = {t.name: t for t in tool_catalog()}[name]
    properties = tool.input_schema["properties"]

    def value(key: str) -> object:
        schema = properties[key]
        if schema.get("enum"):
            return schema["enum"][0]
        filler = {
            "object": {},
            "array": [],
            "string": "x",
            "number": 1.0,
            "integer": schema.get("minimum", 1),
            "boolean": True,
        }
        return filler[schema.get("type", "object")]

    return {key: value(key) for key in tool.input_schema.get("required", [])}


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


def test_every_servable_tool_is_dispatched_and_the_refusal_stays_as_a_net():
    """The "not dispatched yet" branch is now unreachable by any tool in the catalog.

    That is worth asserting in both directions. A handler returning a plausible result for
    an operation nobody wired would be indistinguishable from a real one, so the refusal
    stays — and a tool that becomes servable without a handler must hit it rather than
    404. But an unreachable branch nobody notices is the dead guard this library hunts
    everywhere else, so the reachable half is exercised directly, on a tool the catalog
    does not contain.
    """
    from anvilate import mcp

    servable = [
        tool
        for tool in tool_catalog()
        if tool.dispatch is mcp.Dispatch.SYNCHRONOUS and tool.is_stateless
    ]
    assert servable, "the catalog has no servable tool at all"
    undispatched = [tool.name for tool in servable if tool.name not in mcp._DISPATCH]
    assert undispatched == [], f"servable and unwired: {undispatched}"

    # The branch itself, reached by removing the handler for a tool that has one. Patching
    # the map rather than the catalog keeps the tool's published contract untouched, which
    # is the state a half-shipped operation would actually be in.
    original = dict(mcp._DISPATCH)
    try:
        del mcp._DISPATCH["run_validation"]
        error = _call("run_validation", {"spec": _spec_document()})["error"]
    finally:
        mcp._DISPATCH.clear()
        mcp._DISPATCH.update(original)
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


# --- Found auditing the handler an hour after writing it ---------------------------------


def test_a_notification_takes_no_response_however_malformed_it_is():
    """The first draft validated the JSON-RPC version *before* noticing there was no id,
    so a notification with a missing or wrong ``jsonrpc`` produced an error line — a
    spurious response in a stream the client reads one response per request.

    A message with no id has nothing to answer to, so the notification check has to come
    first. A request *with* an id and a bad version is still an error, which is the half
    that must not be lost to the fix.
    """
    for message in (
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "1.0", "method": "notifications/initialized"},
        {"method": "notifications/initialized"},
        {},
    ):
        assert handle_request(message) is None

    assert (
        handle_request({"jsonrpc": "1.0", "id": 5, "method": "tools/list"})["error"]["code"]
        == -32602
    )


def test_a_value_outside_its_declared_enum_or_bounds_is_refused():
    """``render_viewport``'s schema names four views and a width between 64 and 4096, and
    the first draft of the argument check enforced none of it — a `view` of "sideways"
    and a `width_px` of 1 both got as far as the stateless refusal, which reports the
    wrong problem."""
    enum_error = _call("render_viewport", {"view": "sideways"})["error"]
    assert enum_error["code"] == -32602
    assert "must be one of" in enum_error["message"]

    for width, wording in ((1, "at least 64"), (9999, "at most 4096")):
        error = _call("render_viewport", {"view": "iso", "width_px": width})["error"]
        assert error["code"] == -32602
        assert wording in error["message"]

    # In range, the argument check passes and the honest refusal comes back instead.
    assert _call("render_viewport", {"view": "iso", "width_px": 800})["error"]["code"] == -32000


def test_an_exclusive_bound_is_exclusive():
    """``convergence_tol`` declares ``exclusiveMinimum: 0``: a tolerance of exactly zero is
    a solver that never converges, and ``>=`` would have accepted it."""
    error = _call("run_fea_validation", {"spec": {}, "convergence_tol": 0})["error"]
    assert error["code"] == -32602
    assert "above 0" in error["message"]
    # Above it, the call reaches the task-dispatch refusal.
    assert (
        _call("run_fea_validation", {"spec": {}, "convergence_tol": 1e-6})["error"]["code"]
        == -32000
    )


# Every keyword the published schemas use, paired with a value it accepts and every value
# it must refuse. Naming a keyword in a set is not evidence anything enforces it — `pattern` and
# `items` both sat in the old known-set unenforced, and the mutation that deleted each
# check killed no test. A keyword with no probe here fails the gate below.
_CONSTRAINT_PROBES: dict[str, tuple[dict, object, tuple]] = {
    "type": ({"type": "string"}, "text", (7, True, [])),
    "enum": ({"type": "string", "enum": ["iso", "front"]}, "iso", ("sideways",)),
    "minimum": ({"type": "integer", "minimum": 64}, 64, (63,)),
    "maximum": ({"type": "integer", "maximum": 4096}, 4096, (4097,)),
    "exclusiveMinimum": ({"type": "number", "exclusiveMinimum": 0}, 1e-9, (0,)),
    "exclusiveMaximum": ({"type": "number", "exclusiveMaximum": 1}, 0.5, (1,)),
    "minLength": ({"type": "string", "minLength": 1}, "x", ("",)),
    "minItems": ({"type": "array", "minItems": 1}, ["x"], ([],)),
    "pattern": ({"type": "string", "pattern": "^[0-9a-f]{64}$"}, "a" * 64, ("deadbeef",)),
    # The element's *type*, with no enum on it. A first draft gave the element an enum and
    # refused `[7]`, which the enum catches on its own — so swapping the element check for
    # a constraints-only one, the mutation that lets `tiers: [7]` through, killed no test.
    # The enum-inside-items half is held against the published schema below instead.
    "items": ({"type": "array", "items": {"type": "string"}}, ["a"], ([7], [None])),
}

# Keywords that constrain nothing this check could enforce, each with the reason. `$ref` is
# the deliberate boundary the docstrings describe: resolving it is the operation's job.
_NOT_CONSTRAINTS = {"description", "$ref"}


def _declared_keywords(schema, seen: set[str]) -> set[str]:
    """Every keyword used anywhere in a schema document, nested schemas included."""
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in ("properties",):
                for nested in value.values():
                    _declared_keywords(nested, seen)
                continue
            seen.add(key)
            if key == "items":
                _declared_keywords(value, seen)
    return seen


@pytest.mark.parametrize(("keyword", "probe"), sorted(_CONSTRAINT_PROBES.items()))
def test_each_constraint_the_check_claims_to_know_is_one_it_enforces(keyword, probe):
    """The half a set of keyword names cannot give you: proof each one says no.

    Twice now a keyword has been added to the known-set while nothing enforced it, and both
    times the coverage test went on passing. So every keyword is probed with a value its
    schema accepts and one it forbids, and the refusal has to name the label.
    """
    from anvilate.mcp import _typed_issues

    schema, accepted, refusals = probe
    assert _typed_issues("probe", accepted, schema) == [], keyword
    for refused in refusals:
        complaints = _typed_issues("probe", refused, schema)
        assert complaints and all("probe" in complaint for complaint in complaints), (
            f"{keyword} accepted {refused!r}, which its own schema forbids"
        )


def test_every_constraint_the_published_schemas_declare_is_one_the_check_knows():
    """Both directions of the surface, at every depth.

    The first version walked only a schema's top-level ``properties`` — which is where every
    constraint in today's catalog happens to sit, so it agreed with the catalog it was
    written against and would have gone on reporting clean the moment one moved inside an
    ``items``.
    """
    known = (
        set(_CONSTRAINT_PROBES) | _NOT_CONSTRAINTS | {"$schema", "required", "additionalProperties"}
    )
    seen: set[str] = set()
    for tool in tool_catalog():
        for schema in (tool.input_schema, tool.output_schema):
            _declared_keywords(schema, seen)
    unhandled = sorted(seen - known)
    assert not unhandled, (
        f"the tool schemas declare {unhandled}, which the argument and result checks do not "
        "enforce. Either enforce it or narrow the docstrings' claim"
    )
    assert {"enum", "pattern", "items"} <= seen, (
        "the gate is comparing against a set with nothing interesting in it"
    )


# --- The result half of the contract -----------------------------------------------
#
# A published `outputSchema` is a promise about what comes back. Until `result_issues`
# existed the server made that promise and checked nothing, so these tests are written
# from the client's side: what a client pinned to the artifact would do with the payload.


def _released(name: str) -> dict:
    path = pathlib.Path(__file__).resolve().parents[1] / "docs/api/schemas/released" / name
    return json.loads(path.read_text())


def _released_registry():
    """The two published artifacts, addressable by the ``$id`` the tool schemas ``$ref``.

    Deliberately the **released files**, not `spec_json_schema()`. A client resolves the
    versioned URL, which is what those files are; validating against the live model instead
    would check the result against the same code that produced it and agree by construction.
    """
    from referencing import Registry, Resource

    return Registry().with_resources(
        [
            (document["$id"], Resource.from_contents(document))
            for document in (
                _released("design-spec-1.1.0.json"),
                _released("scorecard-1.0.0.json"),
            )
        ]
    )


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("compile_spec", {"document": None}),
        ("run_validation", {"spec": None}),
    ],
)
def test_a_dispatched_result_validates_against_the_released_schemas(tool_name, arguments):
    """The full check the runtime gate deliberately is not: ``$ref``s resolved.

    :func:`result_issues` stops at the envelope, so a scorecard that had drifted from the
    published document would cross an in-process check untouched and be rejected by the
    first client that validated it. Here the references are resolved against the released
    artifacts and a real result of every dispatched tool is validated whole.
    """
    jsonschema = pytest.importorskip("jsonschema")
    document = _spec_document()
    arguments = dict.fromkeys(arguments, document)
    result = _call(tool_name, arguments)["result"]
    tool = {tool.name: tool for tool in tool_catalog()}[tool_name]
    registry = _released_registry()
    validator = jsonschema.Draft202012Validator(tool.output_schema, registry=registry)
    errors = [
        f"{list(error.absolute_path)}: {error.message}"
        for error in validator.iter_errors(result["structuredContent"])
    ]
    assert not errors, errors
    # The reference has to actually be followed, or this passes on an envelope check.
    assert "$ref" in json.dumps(tool.output_schema)


def test_the_result_gate_refuses_what_the_published_output_schema_rejects(monkeypatch):
    """Three shapes a handler could return, each one the published schema forbids.

    The mutations are the point: `result_issues` was written while both handlers already
    conformed, so without an adversary it would be a function nobody has seen say no.
    """
    from anvilate import mcp

    document = _spec_document()
    for returned, expected in (
        ({"errors": [], "surprise": 1}, "takes no result property 'surprise'"),
        ({"spec": {}}, "requires 'errors'"),
        ({"errors": "not a list"}, "must be a JSON array"),
    ):
        monkeypatch.setitem(mcp._DISPATCH, "compile_spec", lambda _arguments, out=returned: out)
        error = _call("compile_spec", {"document": document})["error"]
        assert error["code"] == mcp.INTERNAL_ERROR
        assert "its own published outputSchema rejects" in error["message"]
        assert expected in error["message"], error["message"]


def test_the_result_gate_passes_what_the_handlers_really_return():
    """The other half of the mutation test: the gate is not refusing everything."""
    from anvilate.mcp import result_issues

    tools = {tool.name: tool for tool in tool_catalog()}
    document = _spec_document()
    for name, arguments in (
        ("compile_spec", {"document": document}),
        ("compile_spec", {"document": {"name": "nameless"}}),
        ("run_validation", {"spec": document}),
    ):
        structured = _call(name, arguments)["result"]["structuredContent"]
        assert result_issues(tools[name], structured) == []


@pytest.mark.parametrize(
    ("tool_name", "arguments", "module_name", "attribute"),
    [
        ("compile_spec", "document", "anvilate.spec", "parse_spec"),
        ("run_validation", "spec", "anvilate.screening", "screen_spec"),
    ],
)
def test_a_dispatched_tool_calls_the_symbol_it_names(
    monkeypatch, tool_name, arguments, module_name, attribute
):
    """``backing`` resolving is not evidence the handler goes anywhere near it.

    `run_validation` named `anvilate.bundle:assemble_evidence_bundle` for as long as
    nothing was dispatched, and went on resolving after the handler was wired to
    `anvilate.screening:screen_spec` — the import check cannot see the difference. So the
    named symbol is replaced with one that raises, and the call has to raise through it.
    """

    class _Reached(Exception):
        pass

    def _raise(*_args, **_kwargs):
        raise _Reached

    tool = {tool.name: tool for tool in tool_catalog()}[tool_name]
    assert tool.backing == f"{module_name}:{attribute}"
    monkeypatch.setattr(importlib.import_module(module_name), attribute, _raise)
    with pytest.raises(_Reached):
        _call(tool_name, {arguments: _spec_document()})


def test_the_result_gate_enforces_the_digest_pattern_on_the_real_schema():
    """The keyword-coverage test above is a claim about a *set*, and that is not enough.

    Adding `"pattern"` to the known set satisfied it while `_value_issues` still ignored
    every pattern — the mutation that deleted the check killed nothing. The probe table now
    holds each keyword to a synthetic schema; this holds `pattern` to the *published* one,
    since a probe agreeing with itself is not evidence the catalog's own digest is checked.
    `export_artifact` is not dispatched, so its schema is exercised directly: a digest of
    the wrong length, the wrong alphabet, or the right shape buried in a longer string.
    """
    from anvilate.mcp import result_issues

    tool = {tool.name: tool for tool in tool_catalog()}["export_artifact"]
    good = "a" * 64
    assert result_issues(tool, {"format": "dxf", "path": "part.dxf", "sha256": good}) == []
    for bad in ("deadbeef", "A" * 64, "g" * 64, f"sha256:{good}"):
        issues = result_issues(tool, {"format": "dxf", "path": "part.dxf", "sha256": bad})
        assert any("must match" in issue for issue in issues), (bad, issues)


def test_the_tiers_argument_is_held_to_the_enum_its_own_schema_declares():
    """`run_validation.tiers` is the one place the surface puts a constraint inside `items`.

    Until the element check existed a bad tier reached the spec parser, which reported it as
    `spec.acceptance.tiers.0` — sending a client to look at its *document* for a problem in
    a different argument. And `T3_fea` was accepted outright: the schema names three tiers
    because the fourth is task-dispatched, which is the split the whole module is built on.
    """
    document = _spec_document()
    for tiers, expected in (
        (["not_a_tier"], "run_validation.tiers[0] must be one of"),
        (["T3_fea"], "run_validation.tiers[0] must be one of"),
        ([7], "run_validation.tiers[0] must be a JSON string"),
    ):
        error = _call("run_validation", {"spec": document, "tiers": tiers})["error"]
        assert error["code"] == -32602
        assert expected in error["message"], error["message"]
    accepted = _call("run_validation", {"spec": document, "tiers": ["T1_analytical"]})
    assert "error" not in accepted


# --- The check that lived in one transport ----------------------------------------------


@pytest.mark.parametrize(
    "not_an_object",
    [1.0, None, [], ["jsonrpc", "2.0"], "tools/list", True],
)
def test_a_request_that_is_not_an_object_is_answered_rather_than_dropped(not_an_object):
    """`handle_request` is documented as the one place every transport drives, and the
    "is this an object" check lived in the stdio loop instead — so the guarantee held for
    exactly the caller that had written it out.

    The two failures were different and both silent from the client's side. A list or a
    string reached `"id" not in request`, which is a membership test that happens to be
    True for both, so the message returned `None` and a client waiting on it waited
    forever. A number or `None` raised `TypeError` out of the handler.

    JSON-RPC 2.0 §5: an Invalid Request is `-32600` with `"id": null`. There is no `id`
    member to be missing here, so this is the one id-less case this handler answers — see
    the divergence stated in its docstring for the case it does not.
    """
    response = handle_request(not_an_object)
    assert response is not None, "a message that is not a request object was dropped"
    assert response["error"]["code"] == -32600
    assert response["id"] is None
    assert response["jsonrpc"] == "2.0"


def test_the_stdio_loop_and_the_handler_agree_on_a_non_object():
    """The parity the move was for, asserted rather than assumed.

    Before it, the loop answered `-32600` and a direct call did not — two transports, two
    behaviours, one documented contract. This fails if the check moves back into a caller.
    """
    responses = _serve(json.dumps([1, 2, 3]), json.dumps({"jsonrpc": "2.0", "id": 9}))
    assert responses[0] == handle_request([1, 2, 3])
    assert responses[0]["error"]["code"] == -32600
    # And the loop still serves the message after it, which is the reason it catches at all.
    assert responses[1]["id"] == 9
