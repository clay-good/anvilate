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

from copy import deepcopy
from enum import StrEnum
from typing import Any

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

    @property
    def dispatch(self) -> Dispatch:
        """Task or synchronous, decided by cost alone."""
        return Dispatch.TASK if self.cost is Cost.UNBOUNDED else Dispatch.SYNCHRONOUS

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
