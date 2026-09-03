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
import re
import sys
from collections.abc import Mapping
from copy import deepcopy
from enum import StrEnum
from typing import Any, TextIO

from pydantic import ConfigDict, Field, model_validator

from ._models import Named, RevalidatedModel
from .attestation import canonical_json, sha256_hex
from .contracts import JSON_SCHEMA_DIALECT, scorecard_json_schema, spec_json_schema
from .spec import ValidationTier
from .store import SUBJECT_PATTERN, UnknownSubject, subject_store

__all__ = [
    "Cost",
    "Dispatch",
    "Gate",
    "REQUIRED_OPERATIONS",
    "ToolDefinition",
    "catalog_issues",
    "handle_request",
    "result_issues",
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
_SPEC_REF = "https://anvilate.dev/schemas/design-spec/1.3.0.json"
# Moved to 1.6.0 when a check that compares two quantities gained `comparison`, so a
# report can state the comparison in its own units instead of the ones it was screened
# in. Additive; `detail` is still written from it and still says what it always said.
#
# Moved to 1.5.0 when a symbol gained `unit_is_required` — the one case where a display
# unit is arithmetic rather than taste. An added optional property, so a 1.4.0 client reads
# a 1.5.0 document; the version moves because a changed artifact carries a moved version.
#
# Moved to 1.4.0 when a derivation's preferred display unit stopped overriding a declared
# unit system. The shape is unchanged and only one field's description moved, so a client
# pinned to 1.3.0 reads every 1.4.0 document correctly — but the version moves anyway,
# because the gate's rule is that a changed artifact carries a moved version and "this
# change was small" is the judgement that rule exists to take away.
#
# Moved from 1.2.0 when `ScorecardEntry.underived` shipped. The tool surface has to move
# with it: the server now emits entries carrying a field 1.2.0 does not describe, and a
# client validating against the version this catalog names would be validating the wrong
# document. Nothing a 1.2.0 client already reads has changed — the addition is one optional
# property, and neither release closes `additionalProperties` — so an old client keeps
# working; it simply cannot see whether a check is owed a derivation.
_SCORECARD_REF = "https://anvilate.dev/schemas/scorecard/1.6.0.json"
# The evidence bundle, published at 1.0.0 so `export_artifact` can describe what it returns.
# It could not before: the tool declared its entire output as `{"type": "object"}`, because
# `contracts.py` generated a spec schema and a scorecard schema and no third one. A literal
# here for the same reason as the two above.
_BUNDLE_REF = "https://anvilate.dev/schemas/evidence-bundle/1.0.0.json"

# What a tool takes to say *what* it acts on: a handle into the content-addressed store, not
# a memory of the last call. This was chosen over carrying whole payloads and over a session
# in `openspec/changes/archive/2026-09-01-resolve-mcp-tool-subjects`; `anvilate.store` states
# the store's location, reach and retention, which is the cost the choice was made with open
# eyes about.
_SUBJECT_SCHEMA = {
    "type": "string",
    "pattern": SUBJECT_PATTERN,
    "description": (
        "A handle returned by an earlier call — 'sha256:' and the digest of the document it "
        "names. Resolved from the subject store; a handle that is not there is refused "
        "rather than guessed at."
    ),
}

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


class ToolDefinition(RevalidatedModel):
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

    name: Named = Field(pattern=r"^[a-z][a-z0-9_]*$")
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
                    "subject": _SUBJECT_SCHEMA,
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
                    "subject": _SUBJECT_SCHEMA,
                    "view": {
                        "type": "string",
                        "enum": ["iso", "front", "top", "right"],
                    },
                    "width_px": {"type": "integer", "minimum": 64, "maximum": 4096},
                },
                required=["subject", "view"],
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
            subject="subject",
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
                {"subject": _SUBJECT_SCHEMA, "query": {"type": "string", "minLength": 1}},
                required=["subject", "query"],
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
            subject="subject",
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
                {"scorecard": {"$ref": _SCORECARD_REF}, "subject": _SUBJECT_SCHEMA},
                required=["scorecard", "subject"],
            ),
            cost=Cost.BOUNDED,
            tiers=(
                ValidationTier.T0_GEOMETRY,
                ValidationTier.T1_ANALYTICAL,
                ValidationTier.T2_DFM,
            ),
            # The screen, not the bundle assembler: `backing` names what implements the
            # operation, and this one is dispatched to `screen_spec`. It read
            # `anvilate.bundle:assemble_evidence_bundle` while nothing was wired, and a
            # symbol that merely resolves goes on resolving after the handler calls
            # something else — so `test_a_dispatched_tool_calls_the_symbol_it_names`
            # replaces the named symbol and requires the call to go through it.
            backing="anvilate.screening:screen_spec",
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
            input_schema=_object_schema({"subject": _SUBJECT_SCHEMA}, required=["subject"]),
            output_schema=_object_schema(
                {"scorecard": {"$ref": _SCORECARD_REF}},
                required=["scorecard"],
            ),
            cost=Cost.BOUNDED,
            backing="anvilate.store:SubjectStore",
            subject="subject",
        ),
        ToolDefinition(
            name="export_artifact",
            title="Export an artifact",
            description=(
                "Return a downstream document — an evidence bundle today, a QIF results "
                "file or a DXF once there is built geometry — for the scorecard a handle "
                "names. The document is returned, not written: this surface names no path "
                "and touches no filesystem the caller chose, so a client saves it or does "
                "not. Export is gated on validation and the result carries the screening "
                "watermark; the MCP surface grants no bypass of either."
            ),
            input_schema=_object_schema(
                {
                    "subject": _SUBJECT_SCHEMA,
                    "format": {"type": "string", "enum": ["qif", "dxf", "evidence_bundle"]},
                },
                required=["subject", "format"],
            ),
            output_schema=_object_schema(
                {
                    "format": {"type": "string"},
                    # The bundle itself, as the primitives `BundleSections.to_document_dict`
                    # produces — the roll-up *and* the card, because a bundle whose checks a
                    # reviewer cannot read is not evidence. It was `{"type": "object"}`: the
                    # one thing this tool exists to hand a client was the one thing its
                    # published schema said nothing about, because there was no bundle
                    # contract to `$ref`. There is now, generated from
                    # `anvilate.bundle.BundleDocument`.
                    "bundle": {"$ref": _BUNDLE_REF},
                    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                },
                required=["format", "bundle", "sha256"],
            ),
            cost=Cost.BOUNDED,
            emits_artifacts=True,
            backing="anvilate.bundle:BundleSections",
            subject="subject",
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
        if ref not in {_SPEC_REF, _SCORECARD_REF, _BUNDLE_REF}:
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
INTERNAL_ERROR = -32603
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

    **A deliberately partial check, and the docstring says which part.** It enforces
    everything the published schemas constrain at the top level: every ``required``
    property is present, no property outside ``properties`` is sent
    (``additionalProperties`` is false on every one of them), each value matches its
    declared ``type``, and where a property declares an ``enum`` or a numeric bound the
    value is held to it, along with ``minLength`` and ``minItems``.

    It does **not** resolve the ``$ref``s to the published spec and scorecard schemas, and
    it does not descend into nested objects — so a structurally wrong spec passes here and
    is caught by the operation, which is where the spec schema actually lives.

    That boundary is the point rather than an omission: a handler that reported "valid"
    after checking three keys would be claiming the schema had been applied. The enum and
    bound checks arrived after an audit found ``view: "sideways"`` and a ``width_px`` of 1
    sailing through a surface whose own schema names four views and a floor of 64.
    """
    return _object_issues(tool.name, arguments, tool.input_schema, noun="argument")


def result_issues(tool: ToolDefinition, structured: Mapping[str, Any]) -> list[str]:
    """What is wrong with a handler's ``structuredContent`` against its *output* schema.

    The mirror of :func:`_argument_issues`, pointed the other way. The 2026-07-28 revision
    says a tool that publishes an ``outputSchema`` returns structured content conforming to
    it, and until this existed nothing in the server held a result to the document the
    catalog hands every client. The two dispatched handlers happened to conform; a gate that
    is written while it is already green is the only kind that can stay green.

    **A non-conforming result is refused rather than sent.** A client that validates against
    the published ``outputSchema`` — which is the point of publishing one — would reject the
    payload anyway, and it would reject it without knowing whether the server or its own
    pin was wrong. INTERNAL_ERROR naming the offending property says which.

    The same deliberate boundary as the input check applies, and for the same reason: this
    does not resolve the ``$ref``s to the published spec and scorecard schemas, so a
    malformed scorecard *inside* a conforming envelope passes here. That half is checked in
    CI, where ``jsonschema`` resolves both references against the released artifacts and
    validates a real result of every dispatched tool — a check with a network-shaped
    dependency does not belong on the path a caller waits on.
    """
    return _object_issues(tool.name, structured, tool.output_schema, noun="result property")


def _object_issues(
    label: str, document: Mapping[str, Any], schema: Mapping[str, Any], *, noun: str
) -> list[str]:
    """One JSON object against one closed 2020-12 object schema, top level only.

    Shared by the input and output checks so a constraint taught to one is understood by
    the other; ``noun`` is what an unexpected property is called in the message, because
    "takes no argument" is wrong about something the server sent.
    """
    properties: dict[str, Any] = schema.get("properties", {})
    issues: list[str] = []
    for name in schema.get("required", []):
        if name not in document:
            issues.append(f"{label} requires {name!r}")
    for name in document:
        if name not in properties:
            issues.append(f"{label} takes no {noun} {name!r}")
    for name, value in document.items():
        if name in properties:
            issues.extend(_typed_issues(f"{label}.{name}", value, properties[name]))
    return issues


def _typed_issues(label: str, value: Any, schema: Mapping[str, Any]) -> list[str]:
    """One value against one schema: its declared ``type`` first, then its constraints.

    Split out from :func:`_object_issues` when ``items`` was implemented, because an array
    element is held to a type the same way a property is and the check was written in one
    place only. A schema with no ``type`` constrains nothing here — that is a ``$ref``,
    which is resolved by the operation rather than by this function.
    """
    declared = schema.get("type")
    if declared is None and "$ref" in schema:
        # A `$ref` here names one of the published schemas, and every one of them describes
        # a JSON *object*. The operation resolves the contents; what it cannot do is resolve
        # a string or a null, and `run_validation` proved it: `{"spec": "text"}` reached the
        # handler and raised `dict()`'s own message out of the server, where the client is
        # owed INVALID_PARAMS. Holding the shape here keeps the answer in one place.
        if not isinstance(value, Mapping):
            return [f"{label} must be a JSON object; got {type(value).__name__}"]
        return []
    expected = _JSON_TYPES.get(declared) if declared is not None else None
    if expected is None:
        return []
    if declared in ("number", "integer") and isinstance(value, bool):
        # `isinstance(True, int)` is True in Python and a boolean is not a number in
        # JSON, so the generic check below would accept `width_px: true` as a pixel
        # count. Both numeric type names need the exception, not just "number".
        return [f"{label} must be a JSON {declared}; got a boolean"]
    if not isinstance(value, expected):
        return [f"{label} must be a JSON {declared}; got {type(value).__name__}"]
    return _value_issues(label, value, schema)


def _value_issues(label: str, value: Any, schema: Mapping[str, Any]) -> list[str]:
    """The ``enum``, length and numeric-bound constraints a single property declares.

    Kept in step with the published schemas by a test that fails when a tool declares a
    constraint this does not know — otherwise the docstring above would go on claiming
    everything top-level is checked while a new ``pattern`` went unenforced.
    """
    issues: list[str] = []
    allowed = schema.get("enum")
    if allowed is not None and value not in allowed:
        issues.append(f"{label} must be one of {sorted(allowed)}; got {value!r}")
    if isinstance(value, str):
        floor = schema.get("minLength")
        if floor is not None and len(value) < floor:
            issues.append(f"{label} must be at least {floor} character(s); got {value!r}")
        expression = schema.get("pattern")
        # `search`, not `fullmatch`: JSON Schema's `pattern` is an unanchored match, and
        # treating it as anchored would reject values the published schema accepts. The
        # one pattern in the surface anchors itself with ^ and $, which is the reason to
        # get this right rather than a reason it does not matter.
        if expression is not None and re.search(expression, value) is None:
            issues.append(f"{label} must match {expression!r}; got {value!r}")
        return issues
    if isinstance(value, list):
        floor = schema.get("minItems")
        if floor is not None and len(value) < floor:
            issues.append(f"{label} must list at least {floor} item(s); got {len(value)}")
        element = schema.get("items")
        if element is not None:
            for index, item in enumerate(value):
                issues.extend(_typed_issues(f"{label}[{index}]", item, element))
        return issues
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return issues
    for key, ok, wording in (
        ("minimum", lambda v, b: v >= b, "at least"),
        ("maximum", lambda v, b: v <= b, "at most"),
        ("exclusiveMinimum", lambda v, b: v > b, "above"),
        ("exclusiveMaximum", lambda v, b: v < b, "below"),
    ):
        bound = schema.get(key)
        if bound is not None and not ok(value, bound):
            issues.append(f"{label} must be {wording} {bound}; got {value}")
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


class _InvalidArguments(ValueError):
    """A handler's own refusal of arguments the published schema could not check itself.

    :func:`_argument_issues` validates what a tool's input schema states inline — types,
    enums, bounds. It does not follow a ``$ref``, so a property declared as "a Design Spec"
    is checked by the handler that has to parse one, and this is how that refusal reaches
    the client as INVALID_PARAMS rather than as a traceback.
    """

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__("; ".join(issues))


class _Unavailable(RuntimeError):
    """A handler's refusal of a *part* of its surface that is specified and not built.

    Distinct from :class:`_InvalidArguments` because the two are different facts and a
    client acts on them differently: invalid arguments are the caller's to fix and worth
    retrying, an unbuilt operation is not. ``export_artifact`` is the case that needs it —
    the tool is dispatched, and two of the three formats it publishes still wait on built
    geometry. Reaching TOOL_UNAVAILABLE rather than INVALID_PARAMS is what makes the MCP
    answer the same fact the CLI reports with its own ``EXIT_UNBUILT``.
    """


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

    **A stated divergence, not an oversight.** JSON-RPC 2.0 §5 says an *Invalid Request* is
    answered with a ``-32600`` error carrying ``"id": null``, and the spec's own §7 example
    does exactly that for ``{"jsonrpc": "2.0", "method": 1, "params": "bar"}`` — a message
    with no ``id``. This handler answers nothing to *any* message that has no ``id``,
    malformed or not, because the two mistakes do not cost the same: a spurious line in a
    stream a client reads one-for-one desynchronizes it, and an error dropped for a message
    the client was never waiting on does not. A message that is not an object at all has no
    ``id`` member to be missing, so that one is answered rather than dropped.

    Three methods are served. ``initialize`` reports the protocol revision and the
    capabilities this surface has. ``tools/list`` returns :func:`wire_definitions`.
    ``tools/call`` validates the arguments against the tool's published input schema,
    dispatches the operations that are wired — everything in :data:`_DISPATCH` — and holds
    what comes back to the tool's published *output* schema before sending it.

    **A call is checked at both ends against the same document the client was handed.**
    Arguments in by :func:`_argument_issues`, structured content out by
    :func:`result_issues`; a result the published ``outputSchema`` rejects is an
    INTERNAL_ERROR naming the property, not a payload sent for the client to choke on.

    An operation with no handler is refused with that reason rather than answered, because
    a plausible-looking result for something nobody wired is indistinguishable from a real
    one. Two further refusals are structural rather than "not built yet", and they are the
    ones worth reading:

    * **An unbounded tool cannot be called here at all.** ``build_part`` and
      ``run_fea_validation`` are task-dispatched by declared cost; a synchronous
      ``tools/call`` for one is refused with the reason rather than blocked on.
    * **Every tool names what it acts on.** :func:`stateless_gaps` is empty and stays
      empty: a tool that named nothing was asking the server to remember its last call,
      which is a session, and four of them did. They take subject handles now — see
      :mod:`anvilate.store` — and the refusal is still here for the tool that stops
      declaring one.
    """
    # "Is this an object at all" comes first, and it belongs HERE rather than in the stdio
    # loop that used to hold it. This function is documented as the one place every
    # transport drives, and the check living in one caller made that false: called with a
    # list or a string, `"id" not in request` is a membership test that happens to be True,
    # so the message vanished and the client waited forever; called with a number or None
    # it raised TypeError out of the handler.
    if not isinstance(request, Mapping):
        return _error(None, INVALID_REQUEST, "a JSON-RPC request is an object")
    # The notification check comes before the version check, and the order is the point: a
    # message with no `id` has nothing to answer to, so an error response would be a line
    # the client is not expecting and cannot match to anything. The first draft validated
    # the version first and emitted an error for a notification whose `jsonrpc` was missing
    # or wrong — a spurious line in a stream a client reads one-for-one.
    if "id" not in request:
        return None
    request_id = request.get("id")
    if request.get("jsonrpc") != "2.0":
        return _error(request_id, INVALID_PARAMS, "not a JSON-RPC 2.0 request")
    method = request.get("method")

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
        # Naming what each one waits on, because "not implemented" is not an answer a client
        # can act on — the same rule the CLI follows for its unbuilt command. Until the
        # subjects landed these three were refused for having nothing to act on, which hid
        # the real reason behind a contract problem that has since been fixed.
        waiting = _UNBUILT.get(tool.name, "the operation behind the contract")
        return _error(
            request_id,
            TOOL_UNAVAILABLE,
            f"{tool.name} is not dispatched yet: {waiting}. The contract and this handler "
            f"are built and the operation is not; a result invented here would be "
            f"indistinguishable from a real one",
        )
    try:
        structured = handler(arguments)
    except _InvalidArguments as refusal:
        return _error(request_id, INVALID_PARAMS, str(refusal))
    except _Unavailable as refusal:
        return _error(request_id, TOOL_UNAVAILABLE, str(refusal))
    except Exception as unexpected:  # noqa: BLE001 - the last resort, argued below
        # Anything a handler did not anticipate becomes a response rather than an exception,
        # because the alternative is not "the client sees a traceback" — it is that
        # `serve_stdio`'s `for line in source` ends and **the server stops**. The request that
        # raised gets no reply at all and every message queued behind it is lost, so a client
        # reading one response per request blocks forever. A malformed record in the subject
        # store did exactly that.
        #
        # That is the outcome this loop's own docstring rules out — "a stream is not a
        # session: one client sending rubbish must not take the server down for the message
        # after it" — and the reasoning stopped at the JSON parse error, which is the only
        # failure it was written about.
        #
        # It is here rather than in the stdio loop for the reason the object check above is:
        # this function is the one place every transport drives, so a guard in one caller is
        # a guard the next transport does not get.
        #
        # INTERNAL_ERROR, and the type is named: this is a bug in this package every time it
        # fires, and a message that hid which one would trade a dead server for an
        # undiagnosable one. It never reports the operation as having succeeded.
        return _error(
            request_id,
            INTERNAL_ERROR,
            f"{tool.name} raised {type(unexpected).__name__}: {unexpected}. That is a defect "
            f"in anvilate rather than a problem with the request; the server is still up and "
            f"the call did not complete",
        )
    wrong = result_issues(tool, structured)
    if wrong:
        return _error(
            request_id,
            INTERNAL_ERROR,
            f"{tool.name} produced a result its own published outputSchema rejects: "
            + "; ".join(wrong),
        )
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": json.dumps(structured, sort_keys=True)}],
            "structuredContent": structured,
            "isError": bool(structured.get("errors")),
        },
    }


# What `run_validation` publishes and what the two tools that read a screening result ask
# for. Spelled once, because a publisher and a resolver that name the kind separately are two
# strings that can disagree — and the store's whole job is to refuse the wrong sort of
# document by name rather than fail three layers down in a schema nobody sent.
#
# It is *not* `"scorecard"`, and the rename is deliberate rather than cosmetic: the record
# stopped being a card the day it started carrying the spec beside it, and a handle whose
# kind still said `scorecard` would resolve for a caller expecting only a card and hand them
# a document with a different shape. A handle published by a build before this change is
# refused by the store naming both kinds, which is the honest answer — see `_screening`.
_SCREENING = "screening"


def _screening(handle: str) -> Mapping[str, Any]:
    """The ``{spec, scorecard}`` record a handle names, or :class:`UnknownSubject`.

    One reader for both tools that take a screening result, so ``read_scorecard`` and
    ``export_artifact`` cannot come to differ about what a handle is allowed to be.

    The store's own kind mismatch already says "names a 'scorecard', and a 'screening' was
    asked for", which is exactly right for a handle from an older build and says nothing
    about *why*. This adds the why, because that message is the only thing a client holding
    a stale handle receives.
    """
    try:
        record = subject_store().resolve(handle, kind=_SCREENING)
    except UnknownSubject as unknown:
        message = str(unknown.args[0])
        if "'scorecard'" in message:
            raise UnknownSubject(
                f"{message}. A handle used to name the scorecard alone; it names the spec "
                f"and the scorecard together now, so that an exported evidence bundle "
                f"carries the inputs its verdicts were computed from. Call run_validation "
                f"again to publish a handle of the current shape"
            ) from unknown
        raise

    # A record that resolves is not yet a record this build can read, and the difference is a
    # false claim rather than a crash. `read_scorecard` returned `record["scorecard"]`
    # verbatim, and its published outputSchema `$ref`s the versioned scorecard contract — so a
    # card an older release stored crossed as a *successful* result, `isError` false, with
    # three violations of the document the catalog handed the client. `result_issues` cannot
    # see it: it stops at the envelope, and that boundary is deliberate and documented.
    #
    # A client that validates against the published schema — which is the point of publishing
    # one — then rejects the payload without knowing whether the server or its own pin is
    # wrong. That is the exact sentence `result_issues` exists for, one layer in.
    #
    # Checked here rather than in either handler, because this function is the one reader for
    # both tools that take a screening result and exists so they cannot come to differ about
    # what a handle is allowed to be. The models are built and thrown away: the check is
    # whether this build can read the record, and the document a caller gets is still the one
    # the handle names rather than a re-serialization of it.
    from .scorecard import Scorecard
    from .spec import parse_spec

    try:
        Scorecard.model_validate(record["scorecard"])
        parse_spec(record["spec"])
    except (ValueError, TypeError, KeyError) as unreadable:
        raise UnknownSubject(
            f"{handle} resolves to a screening record this build cannot read "
            f"({unreadable}). The subject store outlives a release, so this is an entry an "
            f"older version published or something outside this library wrote. Call "
            f"run_validation again to publish a handle of the current shape"
        ) from unreadable
    return record


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
    # Published, so the next call has something to name. A compiled document is the subject
    # `run_validation` and the geometry tools act on, and a handle is what keeps the payload
    # off the wire without giving the server a memory between calls.
    document_json = spec.model_dump(mode="json")
    handle = subject_store().publish("design-spec", document_json)
    return {"spec": document_json, "errors": [], "subject": handle}


def _run_validation(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """``run_validation``, dispatched to :func:`anvilate.screening.screen_spec`.

    **A document that is not a Design Spec is a malformed request here, unlike in
    ``compile_spec``.** That tool's input property is declared as "a candidate spec
    document, YAML- or JSON-derived", so a document that fails validation is the answer it
    exists to give. This tool's input property is declared as the published Design Spec
    schema, so a document that does not match it does not satisfy the contract the client
    was handed — and the honest code for that is INVALID_PARAMS with the paths.

    ``tiers`` **replaces** the spec's own acceptance tiers rather than intersecting them. A
    caller asking for a tier the document did not demand is asking a question, and the
    answer — for T0 and T1 today, a named gap — is more useful than a silent omission. It
    is applied by re-validating the whole document, because ``model_copy`` does not re-run
    validators and the tier list has one.
    """
    from .screening import screen_spec
    from .spec import SpecValidationError, parse_spec

    # `dict()` on a string raises ValueError and on None a TypeError, and both used to
    # happen here rather than in the try below. The schema check above holds the shape now;
    # this stays inside the guarded block so a direct caller gets the same answer.
    requested = arguments.get("tiers")
    try:
        document = dict(arguments["spec"])
        if requested is not None:
            document = {
                **document,
                "acceptance": {
                    **dict(document.get("acceptance") or {}),
                    "tiers": list(requested),
                },
            }
        spec = parse_spec(document)
    except SpecValidationError as failure:
        raise _InvalidArguments(
            [f"spec.{e['loc']}: {e['msg']}" for e in failure.errors]
        ) from failure
    except (ValueError, TypeError, KeyError) as failure:
        raise _InvalidArguments([f"spec: {failure}"]) from failure
    card = screen_spec(spec).model_dump(mode="json")
    # The card is returned *and* published: returned because it is closed-form and the answer
    # fits in the reply, published because `read_scorecard` and `export_artifact` need a name
    # for it that is not "the last thing you asked me".
    #
    # **The record is the pair, not the card.** `artifact-export` asks the evidence bundle to
    # carry the spec as well as the scorecard, for a reviewer holding only the bundle. At the
    # shell the spec is in hand; here the only thing `export_artifact` is given is a handle,
    # so what the handle names has to be both. The alternative — a second, optional spec
    # handle on the export call — would make a bundle reproducible or not depending on how a
    # client happened to be written, and a bundle that is *sometimes* reproducible is one a
    # reviewer cannot rely on. This way the screen that produced the verdicts publishes the
    # document that produced them, together, and neither surface can emit the lesser bundle.
    handle = subject_store().publish(
        _SCREENING, {"spec": spec.model_dump(mode="json"), "scorecard": card}
    )
    return {"scorecard": card, "subject": handle}


def _read_scorecard(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """``read_scorecard``, resolved from the subject store.

    This tool used to take nothing at all: it returned "the" scorecard, which is only an
    operation if the server remembers which one. With a handle it is a real read — of the
    document that handle names, from a store any instance can reach, and a handle the store
    does not hold is refused by name rather than answered with whatever is most recent.
    """
    handle = arguments["subject"]
    try:
        return {"scorecard": _screening(handle)["scorecard"]}
    except UnknownSubject as unknown:
        raise _InvalidArguments([f"subject: {unknown.args[0]}"]) from unknown


def _export_artifact(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """``export_artifact``, dispatched to :class:`anvilate.bundle.BundleSections`.

    **The document is returned and nothing is written.** That was the open question —
    `openspec/changes/archive/2026-09-01-export-over-mcp` sets out the three shapes — and
    the answer is the one that grants no capability: the tool has no ``destination``, names
    no path, and creates no file. A client that wants one saves what it was handed. The
    alternatives each asked an operator to decide how far to trust an MCP client with the
    server's filesystem, and this asks nobody anything.

    **The subject is a scorecard, not a spec.** A bundle is a document *about a screening
    result*, and ``BundleSections`` takes exactly that — the card is its one required
    section. Taking a spec handle instead would mean re-screening, and a re-screen is a
    second answer: the same document, run against tables that may have moved, can produce a
    bundle that disagrees with the card the client was already holding. So this exports the
    card that was screened.

    **A failing card still gets a bundle, and that is the gate working rather than being
    skipped.** ``artifact-export`` gates *CAD artifacts* on the acceptance checks passing —
    a DXF somebody cuts from, a QIF somebody measures against. The evidence bundle is the
    evidence, including the evidence that a part did not pass: it renders ``status: fail``
    and carries ``SCREENING_DISCLAIMER`` unconditionally, which is what the watermark rule
    asks of it. ``anvilate export`` does the same thing at the shell — it prints the bundle
    and reports the verdict in its exit code — and a surface that refused here would answer
    a question the other surface answers.
    """
    from .bundle import BundleSections

    # The CLI's own table of what each artifact waits on, imported rather than restated.
    # Two surfaces cannot report an artifact as unbuilt in one place and buildable in the
    # other if they read the same dict, and the keys are already the format names this
    # tool's enum publishes.
    from .cli import _UNBUILT_ARTIFACTS
    from .scorecard import Scorecard
    from .spec import parse_spec

    artifact = arguments["format"]
    if artifact in _UNBUILT_ARTIFACTS:
        raise _Unavailable(
            f"export_artifact cannot produce {artifact}: {_UNBUILT_ARTIFACTS[artifact]} "
            f"The evidence bundle needs no geometry and is served."
        )

    handle = arguments["subject"]
    try:
        record = _screening(handle)
    except UnknownSubject as unknown:
        raise _InvalidArguments([f"subject: {unknown.args[0]}"]) from unknown

    try:
        document = BundleSections(
            scorecard=Scorecard.model_validate(record["scorecard"]),
            # Never `None` on this path. The record holds the pair, so the bundle a client
            # gets over MCP carries its inputs exactly as the one `anvilate export` prints
            # does — the parity is by construction rather than by both surfaces remembering.
            spec=parse_spec(record["spec"]),
        ).to_document_dict()
    except (ValueError, TypeError, KeyError) as unreadable:
        # A handle that resolves to a record this build cannot read is the same fact as one
        # the store does not hold — the client gets no bundle either way — and it is the
        # third layer of the trap `store.resolve` guards at the first two. `run_validation`
        # writes these records, so the shapes that reach here are a store an *older* release
        # populated, or an entry something outside this library wrote. Unguarded, pydantic's
        # `ValidationError` left the tool dispatch entirely: it is not `_InvalidArguments`,
        # and nothing above catches a plain `ValueError`.
        raise _InvalidArguments(
            [
                f"subject: {handle} resolves to a screening record this build cannot read "
                f"({unreadable}). Publish the screening again with this release and export "
                f"the handle it returns"
            ]
        ) from unreadable
    # The digest of the bundle's own canonical JSON, which is the same content addressing
    # the store and the attestation layer use — so the sha256 a client is handed names the
    # bytes it was handed, and two calls that produce the same bundle produce the same
    # digest. The published output declared one when the tool wrote a file; it means the
    # document rather than the file now, and it still means the same kind of thing.
    return {
        "format": artifact,
        "bundle": document,
        "sha256": sha256_hex(canonical_json(document).encode("utf-8")),
    }


# What each undispatched tool is waiting on. A census in tests/test_mcp.py holds this against
# the dispatch map, so a tool that stops being served, or starts, cannot leave a stale reason
# behind — and one that is neither dispatched nor named here fails the build.
_UNBUILT: dict[str, str] = {
    "render_viewport": (
        "rendering an image needs built geometry, and no geometry is generated from a spec "
        "today (see https://github.com/clay-good/anvilate/tree/main/openspec/specs/geometry-generation)"
    ),
    "measure_geometry": (
        "measuring a feature needs built geometry, and no geometry is generated from a spec "
        "today (see https://github.com/clay-good/anvilate/tree/main/openspec/specs/geometry-generation)"
    ),
}

# The operations wired to real code today. A tool absent from this map is refused with the
# reason rather than answered — see the refusal above.
_DISPATCH: dict[str, Any] = {
    "compile_spec": _compile_spec,
    "export_artifact": _export_artifact,
    "read_scorecard": _read_scorecard,
    "run_validation": _run_validation,
}


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
            # No non-object check here any more: `handle_request` holds it, so every
            # transport gets it rather than only the one that remembered to write it.
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
