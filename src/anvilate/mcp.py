"""The pipeline as MCP tool definitions: typed contracts, and the sync/task split.

The MCP 2026-07-28 revision takes full JSON Schema 2020-12 for tool input and output
schemas, which means Anvilate's published contracts can *be* the tool contract rather than
a paraphrase of it. That is the whole reason this module is small: a tool that consumes a
spec does not describe a spec, it ``$ref``s
``https://anvilate.dev/schemas/design-spec/<version>.json``, and a tool that returns a
scorecard ``$ref``s the scorecard schema at its version. Two enforcement points — the tool
contract an agent reads and the structured-output constraint a compiler is decoded under —
resolve to one artifact, so they cannot drift apart.

The reference is by **versioned identifier**, not by name, and :func:`catalog_issues`
compares it against what :mod:`anvilate.contracts` generates today. Bumping a schema version
without moving the tool contracts is therefore a build failure rather than an agent
discovering at run time that the document it was promised is not the document it got.

**Nothing here executes anything.** This is the contract half of the server, which is the
half worth pinning before the server exists — the cheapest possible time to fix a tool
surface is before a client has integrated against it. Every tool that is not yet backed by
shipping code says so in one place (:attr:`ToolDefinition.backing` is ``None``), and every
tool that *is* backed names the symbol, which CI resolves against the live importable
surface. A renamed function fails the build instead of shipping as a promise.

## Which operations are tasks

The rule is stated once and enforced, rather than assigned tool by tool. An operation whose
runtime is bounded by the size of its input — parsing a spec, running the closed-form T1
checks, reading a scorecard, writing an export — is a synchronous call. An operation whose
runtime is bounded by a convergence criterion or by user code — a full build, an FEA-class
validation run — is dispatched through the Tasks extension: handle, progress, cancellation.

The trap this avoids is the plausible one: exposing everything as a task "for consistency",
which makes an agent poll for a result that was ready before the first poll, or exposing
everything synchronously, which makes an agent's client time out on the one operation that
matters most. So :class:`Cost` is declared and cross-checked: a tool covering T3 that claims
bounded cost is refused by the model, because T3 is the tier whose cost is a convergence
tolerance, and a convergence tolerance is not a bound on wall time.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from copy import deepcopy
from enum import StrEnum
from typing import Any, TextIO

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import JSON_SCHEMA_DIALECT, scorecard_json_schema, spec_json_schema
from .spec import ValidationTier

__all__ = [
    "Cost",
    "Dispatch",
    "Gate",
    "REQUIRED_OPERATIONS",
    "ToolDefinition",
    "catalog_issues",
    "handle_request",
    "serve_stdio",
    "main",
    "stateless_gaps",
    "PROTOCOL_REVISION",
    "tool_catalog",
    "wire_definitions",
]


class Cost(StrEnum):
    """What bounds an operation's runtime, which is what decides its dispatch.

    ``BOUNDED`` means the work is a function of the input's size and finishes at
    interactive latency: a parse, a table lookup, a closed-form check. ``UNBOUNDED`` means
    the work is a function of a convergence criterion or of code the caller supplied, and
    has no wall-clock bound that can be promised in a synchronous reply.
    """

    BOUNDED = "bounded"
    UNBOUNDED = "unbounded"


class Dispatch(StrEnum):
    """How a client receives the result. Derived from :class:`Cost`, never declared."""

    SYNCHRONOUS = "synchronous"
    TASK = "task"


class Gate(StrEnum):
    """A rule the MCP surface inherits rather than re-implements.

    The MCP surface grants no bypass, which is a claim that has to be visible in the tool
    definitions or it is only a sentence in a spec. These are derived from what an
    operation does — executing caller-supplied code needs the sandbox, emitting an artifact
    needs the validation gate and the watermark — so a tool cannot acquire a capability and
    forget the rule that goes with it.
    """

    SANDBOX = "sandbox"
    VALIDATION = "validation"
    WATERMARK = "watermark"


# The operations the headless-automation spec requires the server to expose, at minimum.
# `catalog_issues` checks the catalog against this set in both directions: a missing
# operation is an unmet requirement, and an extra one is a surface nobody specified.
REQUIRED_OPERATIONS = frozenset(
    {
        "compile_spec",
        "build_part",
        "render_viewport",
        "measure_geometry",
        "run_validation",
        "run_fea_validation",
        "read_scorecard",
        "export_artifact",
    }
)

# Written out, not read from `contracts`. Deriving these would make the check below
# vacuous: a reference computed from the same call it is compared against agrees with
# itself at every version, including the one where the tool surface should have moved and
# did not. Spelled as literals, a schema bump fails here until someone re-reads the tool
# contracts and decides what a client pinned to the old one is owed.
_SPEC_REF = "https://anvilate.dev/schemas/design-spec/1.1.0.json"
_SCORECARD_REF = "https://anvilate.dev/schemas/scorecard/1.0.0.json"

# Tiers whose cost is a convergence criterion rather than the size of the input. Anything
# covering one of these is task-dispatched; see the module docstring.
_UNBOUNDED_TIERS = frozenset({ValidationTier.T3_FEA})


def _object_schema(properties: dict[str, Any], *, required: list[str]) -> dict[str, Any]:
    """One tool schema as a 2020-12 object document.

    ``additionalProperties: false`` because a tool schema is also the shape a constrained
    decoder is held to, and a permissive schema there means a model can emit a misspelled
    field name and be told it was accepted.
    """
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


class ToolDefinition(BaseModel):
    """One pipeline operation as an MCP tool contract.

    Frozen, so no field can be rebound after the validators approved it. That is not the
    whole story and the honest version is worth writing down: pydantic's ``frozen`` does
    not reach inside a mutable field, so the schema dictionaries themselves can still be
    written to. Two things keep that from mattering. :func:`tool_catalog` builds fresh
    definitions on every call, so a mutation cannot outlive the caller that made it and
    cannot reach the gate; and :meth:`to_wire` deep-copies, so a client editing the payload
    it was handed is editing its own copy.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    cost: Cost
    tiers: tuple[ValidationTier, ...] = ()
    executes_caller_code: bool = False
    emits_artifacts: bool = False
    # The dotted path of the symbol that implements this operation today, or None when the
    # operation is specified but not built. Resolved against the live surface in CI, so
    # this is a claim that can fail rather than a comment.
    backing: str | None = None
    # The *required* input property that carries the thing this operation acts on — the
    # document to compile, the spec to validate. ``None`` means the operation acts on
    # something the caller does not hand it, which is server-side state. Declared rather
    # than inferred, and cross-checked against the schema below so it cannot drift.
    subject: str | None = None

    @property
    def dispatch(self) -> Dispatch:
        """Task or synchronous, decided by cost alone."""
        return Dispatch.TASK if self.cost is Cost.UNBOUNDED else Dispatch.SYNCHRONOUS

    @property
    def is_stateless(self) -> bool:
        """Whether a server with no memory between calls can serve this operation.

        True exactly when the tool names a :attr:`subject`: everything it acts on arrives
        in the call. A tool without one is asking the server to remember what the last
        call produced, which is a different server from the stateless skeleton the
        headless-automation spec describes — and the difference is a design decision, not
        an implementation detail.
        """
        return self.subject is not None

    @property
    def gates(self) -> frozenset[Gate]:
        """The rules this operation inherits, derived from what it does."""
        gates: set[Gate] = set()
        if self.executes_caller_code:
            gates.add(Gate.SANDBOX)
        if self.emits_artifacts:
            gates.update({Gate.VALIDATION, Gate.WATERMARK})
        return frozenset(gates)

    @model_validator(mode="after")
    def _subject_is_a_required_input(self) -> ToolDefinition:
        if self.subject is None:
            return self
        properties = self.input_schema.get("properties", {})
        if self.subject not in properties:
            raise ValueError(
                f"{self.name} declares {self.subject!r} as the thing it acts on, and its "
                f"input schema has no such property. A subject the caller cannot send is "
                f"state by another name"
            )
        if self.subject not in self.input_schema.get("required", []):
            raise ValueError(
                f"{self.name} declares {self.subject!r} as the thing it acts on, and its "
                f"input schema does not require it. An optional subject is one the caller "
                f"can omit, which puts the operation back on server-side state for exactly "
                f"the calls that omit it"
            )
        return self

    @model_validator(mode="after")
    def _cost_matches_the_work(self) -> ToolDefinition:
        if len(set(self.tiers)) != len(self.tiers):
            raise ValueError(f"{self.name} lists a validation tier twice: {self.tiers}")
        unbounded = sorted(t.value for t in self.tiers if t in _UNBOUNDED_TIERS)
        if unbounded and self.cost is not Cost.UNBOUNDED:
            raise ValueError(
                f"{self.name} covers {unbounded} but declares bounded cost. A tier whose "
                "stopping condition is a convergence tolerance has no wall-clock bound to "
                "promise a synchronous caller; it belongs on the Tasks extension"
            )
        if self.executes_caller_code and self.cost is not Cost.UNBOUNDED:
            raise ValueError(
                f"{self.name} executes caller-supplied code but declares bounded cost. "
                "Nothing bounds the runtime of code this library did not write"
            )
        return self

    def to_wire(self) -> dict[str, Any]:
        """The definition as the object an MCP client receives in ``tools/list``.

        Anvilate's own fields live under ``_meta``, namespaced, which is where the protocol
        puts implementation detail that is not part of the tool call itself. A client that
        understands none of them still gets a complete, valid tool definition.
        """
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": deepcopy(self.input_schema),
            "outputSchema": deepcopy(self.output_schema),
            "_meta": {
                "dev.anvilate/dispatch": self.dispatch.value,
                "dev.anvilate/cost": self.cost.value,
                "dev.anvilate/tiers": [tier.value for tier in self.tiers],
                "dev.anvilate/gates": sorted(gate.value for gate in self.gates),
                "dev.anvilate/backing": self.backing,
                "dev.anvilate/subject": self.subject,
            },
        }


def _catalog() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition(
            name="compile_spec",
            title="Compile a spec document",
            description=(
                "Validate a Design Spec document into the typed IR, resolving material and "
                "standard-component references and reporting every refusal with its reason. "
                "Prose is compiled into a candidate document by the caller's own model — "
                "this server initiates no sampling — and this tool is where that candidate "
                "is held to the published schema."
            ),
            input_schema=_object_schema(
                {
                    "document": {
                        "type": "object",
                        "description": "A candidate spec document, YAML- or JSON-derived.",
                    }
                },
                required=["document"],
            ),
            output_schema=_object_schema(
                {
                    "spec": {"$ref": _SPEC_REF},
                    "errors": {"type": "array", "items": {"type": "string"}},
                },
                required=["errors"],
            ),
            cost=Cost.BOUNDED,
            backing="anvilate.spec:parse_spec",
            subject="document",
        ),
        ToolDefinition(
            name="build_part",
            title="Build or regenerate the part",
            description=(
                "Execute the part's generating program and return a geometry summary. The "
                "program is caller-supplied code, so it runs sandboxed and its runtime is "
                "bounded by nothing this library controls: the call returns a task handle."
            ),
            input_schema=_object_schema(
                {"spec": {"$ref": _SPEC_REF}},
                required=["spec"],
            ),
            output_schema=_object_schema(
                {
                    "geometry": {"type": "object"},
                    "warnings": {"type": "array", "items": {"type": "string"}},
                },
                required=["geometry", "warnings"],
            ),
            cost=Cost.UNBOUNDED,
            tiers=(ValidationTier.T0_GEOMETRY,),
            executes_caller_code=True,
            subject="spec",
        ),
        ToolDefinition(
            name="render_viewport",
            title="Render a viewport image",
            description=(
                "Render the built part from a named view, so an agent can see what it made "
                "before proposing the next edit. Returns the image as an attachment "
                "alongside the structured view metadata."
            ),
            input_schema=_object_schema(
                {
                    "view": {
                        "type": "string",
                        "enum": ["iso", "front", "top", "right"],
                    },
                    "width_px": {"type": "integer", "minimum": 64, "maximum": 4096},
                },
                required=["view"],
            ),
            output_schema=_object_schema(
                {
                    "view": {"type": "string"},
                    "width_px": {"type": "integer"},
                    "height_px": {"type": "integer"},
                },
                required=["view", "width_px", "height_px"],
            ),
            cost=Cost.BOUNDED,
        ),
        ToolDefinition(
            name="measure_geometry",
            title="Measure the built geometry",
            description=(
                "Read a dimension, mass property, or tagged feature off the built part, so "
                "a repair proposal is based on what the geometry is rather than on what the "
                "spec asked for."
            ),
            input_schema=_object_schema(
                {"query": {"type": "string", "minLength": 1}},
                required=["query"],
            ),
            output_schema=_object_schema(
                {
                    "value": {"type": "number"},
                    "unit": {"type": "string"},
                    "feature": {"type": "string"},
                },
                required=["value", "unit"],
            ),
            cost=Cost.BOUNDED,
        ),
        ToolDefinition(
            name="run_validation",
            title="Run the synchronous validation tiers",
            description=(
                "Run the T0 geometry, T1 analytical, and T2 manufacturability checks and "
                "return the typed scorecard. Every one of these is closed-form or a table "
                "lookup, so the answer comes back in the reply rather than through a handle."
            ),
            input_schema=_object_schema(
                {
                    "spec": {"$ref": _SPEC_REF},
                    "tiers": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                ValidationTier.T0_GEOMETRY.value,
                                ValidationTier.T1_ANALYTICAL.value,
                                ValidationTier.T2_DFM.value,
                            ],
                        },
                        "minItems": 1,
                    },
                },
                required=["spec"],
            ),
            output_schema=_object_schema(
                {"scorecard": {"$ref": _SCORECARD_REF}},
                required=["scorecard"],
            ),
            cost=Cost.BOUNDED,
            tiers=(
                ValidationTier.T0_GEOMETRY,
                ValidationTier.T1_ANALYTICAL,
                ValidationTier.T2_DFM,
            ),
            backing="anvilate.bundle:assemble_evidence_bundle",
            subject="spec",
        ),
        ToolDefinition(
            name="run_fea_validation",
            title="Run the FEA-class validation tier",
            description=(
                "Run the T3 converged finite-element checks. The run stops on a convergence "
                "tolerance, not on a clock, so the call returns a task handle: progress is "
                "reportable, cancellation terminates the solver subprocesses, and a "
                "cancelled run reports its affected checks as not evaluated rather than as "
                "passing."
            ),
            input_schema=_object_schema(
                {
                    "spec": {"$ref": _SPEC_REF},
                    "convergence_tol": {"type": "number", "exclusiveMinimum": 0},
                },
                required=["spec"],
            ),
            output_schema=_object_schema(
                {"scorecard": {"$ref": _SCORECARD_REF}},
                required=["scorecard"],
            ),
            cost=Cost.UNBOUNDED,
            tiers=(ValidationTier.T3_FEA,),
            subject="spec",
        ),
        ToolDefinition(
            name="read_scorecard",
            title="Read the scorecard",
            description=(
                "Return the current scorecard as structured content. The status is a "
                "four-valued enumeration and not_evaluated is not a pass, which is why this "
                "is a typed document rather than a summary sentence."
            ),
            input_schema=_object_schema({}, required=[]),
            output_schema=_object_schema(
                {"scorecard": {"$ref": _SCORECARD_REF}},
                required=["scorecard"],
            ),
            cost=Cost.BOUNDED,
            backing="anvilate.scorecard:Scorecard",
        ),
        ToolDefinition(
            name="export_artifact",
            title="Export an artifact",
            description=(
                "Write a downstream document — a QIF results file, a DXF, an evidence "
                "bundle — from the validated state. Export is gated on validation and the "
                "result carries the screening watermark; the MCP surface grants no bypass "
                "of either."
            ),
            input_schema=_object_schema(
                {
                    "format": {"type": "string", "enum": ["qif", "dxf", "evidence_bundle"]},
                    "destination": {"type": "string", "minLength": 1},
                },
                required=["format", "destination"],
            ),
            output_schema=_object_schema(
                {
                    "format": {"type": "string"},
                    "path": {"type": "string"},
                    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                },
                required=["format", "path", "sha256"],
            ),
            cost=Cost.BOUNDED,
            emits_artifacts=True,
            backing="anvilate.export.qif:export_qif_results",
        ),
    )


def tool_catalog() -> tuple[ToolDefinition, ...]:
    """Every pipeline operation the MCP server exposes, in a stable order."""
    return _catalog()


def wire_definitions() -> list[dict[str, Any]]:
    """The catalog as the ``tools/list`` payload an MCP client receives."""
    return [tool.to_wire() for tool in tool_catalog()]


def _refs(node: Any) -> set[str]:
    """Every ``$ref`` anywhere in a schema, at any depth.

    The first version of this walked only the top-level ``properties``, which is where
    every reference in today's catalog happens to sit. That is a gate that agrees with the
    catalog it shipped with: the moment a reference moves inside an ``items``, a
    ``oneOf``, or a nested object — the ordinary way a tool schema grows — it stops being
    checked, and the check goes on reporting clean.
    """
    found: set[str] = set()
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            found.add(ref)
        for value in node.values():
            found |= _refs(value)
    elif isinstance(node, list):
        for value in node:
            found |= _refs(value)
    return found


def _schema_issues(tool: ToolDefinition, label: str, schema: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    where = f"{tool.name}.{label}"
    if schema.get("$schema") != JSON_SCHEMA_DIALECT:
        issues.append(f"{where} declares dialect {schema.get('$schema')!r}, not 2020-12")
    if schema.get("type") != "object":
        issues.append(f"{where} is not an object schema; MCP tool schemas must be objects")
    if schema.get("additionalProperties") is not False:
        issues.append(f"{where} accepts additional properties, so a misspelled field passes")
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        issues.append(f"{where} declares no properties")
        return issues
    for required in schema.get("required", []):
        if required not in properties:
            issues.append(f"{where} requires {required!r}, which it does not define")
    for ref in sorted(_refs(schema)):
        if ref not in {_SPEC_REF, _SCORECARD_REF}:
            issues.append(
                f"{where} references {ref!r}, which is not a published anvilate contract "
                "at its current version"
            )
    return issues


def catalog_issues() -> list[str]:
    """Everything wrong with the tool catalog, as a list of complaints.

    The empty list is the claim CI makes on every push. What it covers: the specified
    operations are all present and nothing extra is, every schema is a closed 2020-12
    object schema whose required fields exist, every contract reference resolves to a
    published schema **at the version generated today**, and every tool returns typed
    output rather than prose.
    """
    issues: list[str] = []
    catalog = tool_catalog()
    names = [tool.name for tool in catalog]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        issues.append(f"the catalog defines these tools more than once: {duplicates}")
    missing = sorted(REQUIRED_OPERATIONS - set(names))
    if missing:
        issues.append(f"the spec requires operations the catalog does not expose: {missing}")
    extra = sorted(set(names) - REQUIRED_OPERATIONS)
    if extra:
        issues.append(
            f"the catalog exposes operations nothing specified: {extra}. Add them to "
            "REQUIRED_OPERATIONS and to the headless-automation spec, or drop them"
        )

    # The literal references, checked against what contracts.py generates today. This is
    # the half that makes a schema version bump a build failure here rather than a
    # discovery an agent makes at run time.
    for label, literal, generated in (
        ("design-spec", _SPEC_REF, spec_json_schema()["$id"]),
        ("scorecard", _SCORECARD_REF, scorecard_json_schema()["$id"]),
    ):
        if literal != generated:
            issues.append(
                f"the tool contracts reference the {label} schema at {literal!r}, but the "
                f"published contract is now {generated!r}. Re-read the tool schemas against "
                "the new version and move the reference deliberately"
            )

    referenced: set[str] = set()
    for tool in catalog:
        issues.extend(_schema_issues(tool, "input_schema", tool.input_schema))
        issues.extend(_schema_issues(tool, "output_schema", tool.output_schema))
        referenced |= _refs(tool.input_schema) | _refs(tool.output_schema)
    for contract in (_SPEC_REF, _SCORECARD_REF):
        if contract not in referenced:
            issues.append(
                f"no tool references {contract!r}. A published contract the tool surface "
                "does not use is a contract the surface has paraphrased instead"
            )
    return issues


# JSON-RPC 2.0 error codes the handler uses. -32601 and -32602 are the protocol's own;
# -32000 is the reserved implementation-defined range, where a refusal that is about
# Anvilate rather than about the request belongs.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
TOOL_UNAVAILABLE = -32000

PROTOCOL_REVISION = "2026-07-28"


def stateless_gaps() -> tuple[str, ...]:
    """The operations a server with no memory between calls cannot serve, in catalog order.

    Derived from each tool's declared :attr:`ToolDefinition.subject` rather than listed, so
    giving a tool an input that carries what it acts on takes it off this list and nothing
    else has to be edited. The constructor already refuses a subject that is not a required
    property of the input schema, which is what stops the declaration drifting from the
    contract it describes.
    """
    return tuple(tool.name for tool in tool_catalog() if not tool.is_stateless)


def _argument_issues(tool: ToolDefinition, arguments: Mapping[str, Any]) -> list[str]:
    """What is wrong with ``arguments`` against ``tool``'s input schema.

    **A deliberately partial check, and the docstring says which part.** It enforces the
    three things the published schemas actually constrain at the top level: every
    ``required`` property is present, no property outside ``properties`` is sent
    (``additionalProperties`` is false on every one of them), and each value matches its
    declared top-level ``type``. It does **not** resolve the ``$ref``s to the published
    spec and scorecard schemas, so a structurally wrong spec passes here and is caught by
    the operation itself.

    That boundary is the point rather than an omission: a handler that reported "valid"
    after checking three keys would be claiming the schema had been applied.
    """
    schema = tool.input_schema
    properties: dict[str, Any] = schema.get("properties", {})
    issues: list[str] = []
    for name in schema.get("required", []):
        if name not in arguments:
            issues.append(f"{tool.name} requires {name!r}")
    for name in arguments:
        if name not in properties:
            issues.append(f"{tool.name} takes no argument {name!r}")
    for name, value in arguments.items():
        declared = properties.get(name, {}).get("type")
        if declared is None:
            continue
        expected = _JSON_TYPES.get(declared)
        if expected is None:
            continue
        if declared in ("number", "integer") and isinstance(value, bool):
            # `isinstance(True, int)` is True in Python and a boolean is not a number in
            # JSON, so the generic check below would accept `width_px: true` as a pixel
            # count. Both numeric type names need the exception, not just "number".
            issues.append(f"{tool.name}.{name} must be a JSON {declared}; got a boolean")
        elif not isinstance(value, expected):
            issues.append(
                f"{tool.name}.{name} must be a JSON {declared}; got {type(value).__name__}"
            )
    return issues


# The JSON Schema type names the published tool schemas use, and what each admits in
# Python. `integer` is not `int` alone because a bool is an int in Python and is not an
# integer in JSON; the check above handles that pair explicitly.
_JSON_TYPES: dict[str, Any] = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
}


def _error(request_id: Any, code: int, message: str, **data: Any) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def handle_request(request: Mapping[str, Any]) -> dict[str, Any] | None:
    """One JSON-RPC request to one JSON-RPC response, with no state between calls.

    A pure function, not a server: it takes the decoded request object and returns the
    object to encode back, so a stdio loop, an HTTP handler and a test all drive the same
    code. ``None`` is returned for a notification (a request with no ``id``), which the
    protocol says takes no response.

    Three methods are served. ``initialize`` reports the protocol revision and the
    capabilities this surface has. ``tools/list`` returns
    :func:`wire_definitions`. ``tools/call`` validates the arguments against the tool's
    published input schema and then refuses, because **no operation is dispatched here
    yet** — the four bounded tools that are backed still need their handlers written, and
    a handler that returned a plausible-looking result for an operation nobody had wired
    would be the worst possible thing to ship behind a tool contract.

    Two refusals are structural rather than "not built yet", and they are the ones worth
    reading:

    * **An unbounded tool cannot be called here at all.** ``build_part`` and
      ``run_fea_validation`` are task-dispatched by declared cost; a synchronous
      ``tools/call`` for one is refused with the reason rather than blocked on.
    * **Four tools cannot be served by a stateless server.** ``render_viewport``,
      ``measure_geometry``, ``read_scorecard`` and ``export_artifact`` name nothing in
      their input to act on — see :func:`stateless_gaps`. That is a real contradiction
      between the published contracts and the stateless skeleton the spec describes, and
      it is surfaced here rather than resolved by inventing an argument.
    """
    if request.get("jsonrpc") != "2.0":
        return _error(request.get("id"), INVALID_PARAMS, "not a JSON-RPC 2.0 request")
    method = request.get("method")
    request_id = request.get("id")
    is_notification = "id" not in request
    if is_notification:
        # A notification takes no response, including no error response.
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_REVISION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "anvilate", "title": "Anvilate"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": wire_definitions()}}
    if method != "tools/call":
        return _error(request_id, METHOD_NOT_FOUND, f"unknown method {method!r}")

    params = request.get("params") or {}
    name = params.get("name")
    tools = {tool.name: tool for tool in tool_catalog()}
    tool = tools.get(name)
    if tool is None:
        return _error(request_id, METHOD_NOT_FOUND, f"unknown tool {name!r}")

    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return _error(request_id, INVALID_PARAMS, "arguments must be a JSON object")
    issues = _argument_issues(tool, arguments)
    if issues:
        return _error(request_id, INVALID_PARAMS, "; ".join(issues))

    if tool.dispatch is Dispatch.TASK:
        return _error(
            request_id,
            TOOL_UNAVAILABLE,
            f"{tool.name} is task-dispatched because its cost is {tool.cost.value}; a "
            f"synchronous tools/call cannot promise a reply for work bounded by a "
            f"convergence criterion or by caller-supplied code",
        )
    if not tool.is_stateless:
        return _error(
            request_id,
            TOOL_UNAVAILABLE,
            f"{tool.name} names nothing in its input to act on, so a server with no memory "
            f"between calls cannot serve it. Either the tool takes what it acts on as an "
            f"argument or the server holds a session; the contract does not yet say which",
        )
    handler = _DISPATCH.get(tool.name)
    if handler is None:
        return _error(
            request_id,
            TOOL_UNAVAILABLE,
            f"{tool.name} is not dispatched yet: the contract and this handler are built, "
            f"the operation behind them is not. A result invented here would be "
            f"indistinguishable from a real one",
        )
    structured = handler(arguments)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": json.dumps(structured, sort_keys=True)}],
            "structuredContent": structured,
            "isError": bool(structured.get("errors")),
        },
    }


def _compile_spec(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """``compile_spec``, dispatched to :func:`anvilate.spec.parse_spec`.

    **A spec that does not validate is a result, not a transport error.** The output
    schema requires ``errors`` and makes ``spec`` optional precisely so a refusal crosses
    as a list of paths the caller can act on. Raising a JSON-RPC error instead would tell
    a client its *request* was malformed, which it was not — the document was.

    The spec crosses as its own model dump, in JSON mode, which is what the published
    Design Spec schema describes. ``isError`` on the result rides on ``errors`` being
    non-empty, so a client that reads only the protocol flag and a client that reads the
    structured content reach the same verdict.
    """
    from .spec import SpecValidationError, parse_spec

    document = arguments["document"]
    try:
        spec = parse_spec(dict(document))
    except SpecValidationError as failure:
        return {"errors": [f"{e['loc']}: {e['msg']}" for e in failure.errors]}
    except (ValueError, TypeError, KeyError) as failure:
        # parse_spec raises SpecValidationError for a schema failure; anything else is a
        # document it could not even attempt, and it still belongs in `errors` rather than
        # crashing the loop that called it.
        return {"errors": [str(failure)]}
    return {"spec": spec.model_dump(mode="json"), "errors": []}


# The operations wired to real code today. A tool absent from this map is refused with the
# reason rather than answered — see the refusal above.
_DISPATCH: dict[str, Any] = {"compile_spec": _compile_spec}


def serve_stdio(stdin: TextIO | None = None, stdout: TextIO | None = None) -> None:
    """Read newline-delimited JSON-RPC from ``stdin`` and write responses to ``stdout``.

    The whole transport: one message per line in, one per line out, flushed each time so a
    client blocked on a read is not waiting on a buffer. Every message is handled by
    :func:`handle_request`, which holds no state, so restarting this loop loses nothing.

    A line that is not JSON is answered with a parse error and the loop continues, because
    a stream is not a session: one client sending rubbish must not take the server down for
    the message after it. A notification produces no line at all, which is what the
    protocol requires and what a client waiting for one response per request depends on.
    """
    source = sys.stdin if stdin is None else stdin
    sink = sys.stdout if stdout is None else stdout
    for line in source:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as bad:
            response: dict[str, Any] | None = _error(None, PARSE_ERROR, f"invalid JSON: {bad}")
        else:
            if not isinstance(request, dict):
                response = _error(None, INVALID_REQUEST, "a JSON-RPC request is an object")
            else:
                response = handle_request(request)
        if response is None:
            continue
        sink.write(json.dumps(response) + "\n")
        sink.flush()


def main() -> None:
    """Run the server on stdio. The console-script and ``python -m`` entry point.

    Nothing to configure: the surface is the published catalog, the transport is stdin and
    stdout, and there is no state to lose, so a client that restarts the process is in
    exactly the position it was in before.
    """
    serve_stdio()


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess in the tests
    main()
