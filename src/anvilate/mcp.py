"""The pipeline as MCP tool definitions: typed contracts, and the sync/task split.

The MCP 2026-07-28 revision takes full JSON Schema 2020-12 for tool input and output
schemas, which means Anvilate's published contracts can *be* the tool contract rather than
a paraphrase of it. That is the whole reason this module is small: a tool that consumes a
spec does not describe a spec, it ``$ref``s
``urn:anvilate:schema:design-spec:<version>``, and a tool that returns a
scorecard ``$ref``s the scorecard schema at its version. Two enforcement points — the tool
contract an agent reads and the structured-output constraint a compiler is decoded under —
resolve to one artifact, so they cannot drift apart.

The reference is by **versioned identifier**, not by name, and :func:`catalog_issues`
compares it against what :mod:`anvilate.contracts` generates today. Bumping a schema version
without moving the tool contracts is therefore a build failure rather than an agent
discovering at run time that the document it was promised is not the document it got.

The catalog and request handler live together so the executable surface is checked against
the contract it advertises. Every tool that is not yet backed by shipping code says so in
one place (:attr:`ToolDefinition.backing` is ``None``), and every tool that *is* backed
names the symbol, which CI resolves against the live importable surface. A renamed function
fails the build instead of shipping as a promise.

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
import math
import os
import re
import sys
from collections.abc import Mapping
from copy import deepcopy
from enum import StrEnum
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, TextIO

from pydantic import ConfigDict, Field, model_validator

from ._mcp_tasks import TASKS_EXTENSION
from ._models import Named, RevalidatedModel, _reason, _refusal_line, parse_json
from ._outputs import output_folder, safe_stem, set_output_folder, write_output
from .attestation import canonical_json, sha256_hex
from .contracts import JSON_SCHEMA_DIALECT, scorecard_json_schema, spec_json_schema
from .evidence import provenance_for
from .geometry import GeometrySummary
from .refusal import RefusalError, Remedy
from .spec import ValidationTier
from .store import SUBJECT_PATTERN, UnknownSubject, _WrongKind, subject_store

_REQUEST_SOURCE = "the MCP client's JSON-RPC request as sent over stdio"


class _McpRequestInputError(RefusalError, ValueError):
    """An MCP request input that cannot be used without correction."""


def _mcp_request_refusal(message: str, *, subject: str, source: str) -> _McpRequestInputError:
    return _McpRequestInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


__all__ = [
    "Cost",
    "Dispatch",
    "Gate",
    "CATALOG_OPERATIONS",
    "COMBINATION_OPERATIONS",
    "CONTEXT_OPERATIONS",
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

# The one tool that is not a pipeline operation: a lookup of what ships. It acts on no
# subject, produces no artifact and screens nothing, so the agent-driving corpus, which
# measures driving the pipeline, is not required to exercise it.
CATALOG_OPERATIONS = frozenset({"describe_part"})

# The two tools that read the user's own files: a listing of a context folder, and the
# measured facts of one CAD file in it. They act on files inside folders named at launch
# (`--context DIR`), never on server memory, and return measurements, never contents.
CONTEXT_OPERATIONS = frozenset({"list_context", "read_cad_file"})

# Several parts placed by the features they share. Its handle is rendered by
# render_viewport and exported by export_artifact, the verbs a single part uses.
COMBINATION_OPERATIONS = frozenset({"build_combination"})
_LOOKUPS = CATALOG_OPERATIONS | CONTEXT_OPERATIONS | COMBINATION_OPERATIONS

# Written out, not read from `contracts`. Deriving these would make the check below
# vacuous: a reference computed from the same call it is compared against agrees with
# itself at every version, including the one where the tool surface should have moved and
# did not. Spelled as literals, a schema bump fails here until someone re-reads the tool
# contracts and decides what a client pinned to the old one is owed.
_SPEC_REF = "urn:anvilate:schema:design-spec:1.20.0"
# 1.6.0 adds a counterbore locator kind and its required through diameter.
# 1.5.0 adds an optional concentric circular locator: a confirmed pilot bore or boss with
# its diameter and axial extent. Existing interface contracts remain valid unchanged.
# 1.4.0 adds optional interface frames and in-plane hole centers. Older contracts remain
# valid; a confirmed STEP pattern can now retain the coordinate data needed to reproduce
# its clocking instead of collapsing to diameter, count, and size.
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
# 1.12.0 adds the optional stable `check_id` that document-driven module checks receive.
_SCORECARD_REF = "urn:anvilate:schema:scorecard:1.14.0"
# The evidence bundle, published so `export_artifact` can describe what it returns. It could
# not before: the tool declared its entire output as `{"type": "object"}`, because
# `contracts.py` generated a spec schema and a scorecard schema and no third one. A literal
# here for the same reason as the two above.
#
# 1.1.0 adds `citations`, absent when the bundle carries none — the standards, certificates
# and database records the numbers were read from, which the signed attestation predicate has
# always carried and the document a reviewer receives did not. Nothing a 1.0.0 client already
# reads has changed and neither release closes `additionalProperties`, so an old client keeps
# working; it simply cannot see where the numbers came from.
# 1.2.0 follows Design Spec 1.4.0 because the bundle embeds that document and therefore
# carries the same optional interface-frame fields.
# 1.3.0 follows Design Spec 1.5.0 for the optional circular locator embedded in that spec.
# 1.4.0 follows Design Spec 1.6.0 for the counterbore's through diameter.
# 1.24.0 follows Scorecard 1.12.0 for stable module check ids embedded in the bundle.
_BUNDLE_REF = "urn:anvilate:schema:evidence-bundle:1.28.0"
_GEOMETRY_REF = "urn:anvilate:schema:geometry-summary:1.5.0"
_VIEWPORT_REF = "urn:anvilate:schema:viewport-image:1.3.0"
_MEASUREMENT_REF = "urn:anvilate:schema:geometry-measurement:1.2.0"
_PART_CATALOG_REF = "urn:anvilate:schema:part-catalog:1.0.0"
_CONTEXT_INVENTORY_REF = "urn:anvilate:schema:context-inventory:1.0.0"
_CAD_FACTS_REF = "urn:anvilate:schema:cad-file-facts:1.0.0"
_COMBINATION_REF = "urn:anvilate:schema:combination-summary:1.0.0"

# The size a tool result may reach, in characters of its JSON. Claude Code warns at about
# 10,000 tokens of tool output and caps at 25,000; Codex truncates to a token budget. A
# result stays well under both, and anything larger is a file in the output folder that the
# result names. Held over every document in the spec corpus by tests/test_mcp_outputs.py.
RESULT_BUDGET_CHARS = 60_000

# What `export_artifact` produces, and which handle each is made from: a screening result
# (the card and its spec) or a built part.
_FROM_SCREENING = ("evidence_bundle", "qif", "part_sheet")
_FROM_BUILT_PART = ("step", "3mf", "dxf")
_EXPORT_FORMATS = (*_FROM_SCREENING, *_FROM_BUILT_PART)

# One file written to the output folder, as every tool that writes one reports it.
_FILE_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "bytes": {"type": "integer"},
        "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    },
    "required": ["path", "bytes", "sha256"],
    "additionalProperties": False,
}

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


def _spec_input() -> dict[str, Any]:
    """The ``spec`` argument of the three tools that take a Design Spec document.

    The ``$ref`` alone is a URN that a client resolves through the embedded ``$defs``, and
    the model writing the call did not: measured through Claude Code 2.1 on 2026-10-09,
    every one of 16 runs sent ``spec`` as a JSON *string*, while ``compile_spec.document``,
    which says ``"type": "object"`` inline, arrived as an object every time. So the type
    and where the object comes from are stated beside the reference, which 2020-12 allows.
    """
    return {
        "$ref": _SPEC_REF,
        "type": "object",
        "description": (
            "The Design Spec document as a JSON object, not a string holding its JSON: the "
            "`spec` object compile_spec returned"
        ),
    }


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
    # ``None`` for a tool whose result is an image. The target clients (Claude Code, Codex)
    # forward only `structuredContent` to the model when a result carries it beside an image,
    # so the picture never arrived. A tool that returns an image therefore declares no output
    # schema and returns the image with a text summary and nothing structured.
    output_schema: dict[str, Any] | None
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
    # True for an operation that acts on what ships with the library, the element catalog,
    # which is the same for every call and every caller. It needs no subject and no memory:
    # there is nothing a previous call could have left behind for it to read.
    reads_shipped_catalog: bool = False
    # Whether a call leaves anything behind: a file in the output folder, or a record in the
    # subject store that a later call names. A tool that only answers is read-only, and a
    # client may run it without asking.
    writes: bool = False

    @property
    def dispatch(self) -> Dispatch:
        """Task or synchronous, decided by cost alone."""
        return Dispatch.TASK if self.cost is Cost.UNBOUNDED else Dispatch.SYNCHRONOUS

    @property
    def is_stateless(self) -> bool:
        """Whether a server with no memory between calls can serve this operation.

        True when the tool names a :attr:`subject`: everything it acts on arrives in the
        call. A tool without one is asking the server to remember what the last call
        produced, which is a different server from the stateless skeleton the
        headless-automation spec describes — and the difference is a design decision, not
        an implementation detail. The one other case is a tool that reads only what ships
        with the library (:attr:`reads_shipped_catalog`), which no call can have changed.
        """
        return self.subject is not None or self.reads_shipped_catalog

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
            "inputSchema": _with_embedded(self.input_schema),
            **(
                {}
                if self.output_schema is None
                else {"outputSchema": _with_embedded(self.output_schema)}
            ),
            # The protocol's hints, stated truthfully so a client can decide what to ask
            # about. Nothing here deletes or overwrites the user's own work: a tool that
            # writes adds a result to the folder the server was started with, replacing only
            # its own earlier result of the same name, so repeating a call is harmless. And
            # nothing here reaches the network: the server is local and reads only what ships
            # with it and the folders it was started with.
            "annotations": {
                "title": self.title,
                "readOnlyHint": not self.writes,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
            "_meta": {
                "dev.anvilate/dispatch": self.dispatch.value,
                "dev.anvilate/cost": self.cost.value,
                "dev.anvilate/tiers": [tier.value for tier in self.tiers],
                "dev.anvilate/gates": sorted(gate.value for gate in self.gates),
                "dev.anvilate/backing": self.backing,
                "dev.anvilate/subject": self.subject,
            },
        }


@cache
def _published_by_id() -> Mapping[str, str]:
    from .contracts import schema_artifacts

    # Cached, so immutable all the way down: each schema is held as its JSON text, and an
    # embedding parses its own copy.
    return MappingProxyType(
        {schema["$id"]: json.dumps(schema) for schema in schema_artifacts().values()}
    )


def _with_embedded(schema: dict[str, Any]) -> dict[str, Any]:
    """``schema`` with every published schema it references embedded under ``$defs``.

    A reference is a URN, a name and not a location, and nothing serves it: Anvilate is a
    local tool. Embedded with its ``$id``, a referenced schema resolves inside the tool
    definition (JSON Schema 2020-12 resolves an embedded ``$id``), so a client validating
    arguments needs nothing but the definition it was handed. They used to be
    ``https://anvilate.dev/...`` URLs, a domain that does not exist, and the official
    conformance suite could not compile a single tool schema.
    """
    wired = deepcopy(schema)
    published = _published_by_id()
    embedded: dict[str, Any] = {}
    pending = sorted(_refs(schema))
    while pending:
        ref = pending.pop()
        if ref in embedded or ref not in published:
            continue
        embedded[ref] = parse_json(published[ref])
        pending.extend(sorted(_refs(embedded[ref]) - set(embedded)))
    if embedded:
        wired.setdefault("$defs", {}).update(embedded)
    return wired


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
                    "remedies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "What to write instead, one per refusal that knows its fix: a "
                            "missing field's line, an unknown field's nearest real name, a "
                            "quantity or provenanced value in the form the schema takes"
                        ),
                    },
                    "subject": _SUBJECT_SCHEMA,
                },
                required=["errors"],
            ),
            writes=True,
            cost=Cost.BOUNDED,
            backing="anvilate.spec:parse_spec",
            subject="document",
        ),
        ToolDefinition(
            name="build_part",
            title="Build or regenerate the part",
            description=(
                "Build the audited pattern selected by the Design Spec and return its B-Rep "
                "geometry summary. The drawable element types are listed in the server "
                "instructions; an element type outside them is refused with the list. "
                "No caller code "
                "is executed, so the bounded primitive build replies synchronously."
            ),
            input_schema=_object_schema(
                {"spec": _spec_input()},
                required=["spec"],
            ),
            output_schema=_object_schema(
                {
                    "geometry": {"$ref": _GEOMETRY_REF},
                    "warnings": {"type": "array", "items": {"type": "string"}},
                    "subject": _SUBJECT_SCHEMA,
                },
                required=["geometry", "warnings", "subject"],
            ),
            writes=True,
            cost=Cost.BOUNDED,
            tiers=(ValidationTier.T0_GEOMETRY,),
            subject="spec",
            backing="anvilate.geometry:build_spec",
        ),
        ToolDefinition(
            name="render_viewport",
            title="Render a viewport image",
            description=(
                "Render the built part from a named view, so an agent can see what it made "
                "before proposing the next edit. Returns the image and one line of text "
                "(view, size, digest, where the file was written): PNG by default, which a "
                "model can look at, or the SVG drawing with format svg. The image is also "
                "written to the server's output folder for the engineer to open. A "
                "build_combination handle draws the whole combination on one sheet: four "
                "views, each part numbered, and the parts list."
            ),
            input_schema=_object_schema(
                {
                    "subject": _SUBJECT_SCHEMA,
                    "view": {
                        "type": "string",
                        "enum": ["overview", "iso", "front", "top", "right"],
                        "description": "overview is all four views on one image with the "
                        "part's name, size, material and verdict: the one to show first",
                    },
                    "width_px": {
                        "type": "integer",
                        "minimum": 64,
                        "maximum": 4096,
                        "description": "the image's width in pixels; 800 when omitted",
                    },
                    "dimensions": {
                        "type": "boolean",
                        "description": "add the overall dimensions, measured from the solid",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["png", "svg"],
                        "description": "png when omitted, which a model can see; svg: the drawing",
                    },
                },
                required=["subject", "view"],
            ),
            output_schema=None,
            writes=True,
            cost=Cost.BOUNDED,
            subject="subject",
            backing="anvilate.geometry:render_viewport",
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
                {
                    "subject": _SUBJECT_SCHEMA,
                    "query": {
                        "type": "string",
                        "minLength": 1,
                        "description": (
                            "volume, a declared dimension, extent_x, face_count, "
                            "area:<semantic-face>, feature_count, or feature:<tag>:diameter "
                            "(also depth, x, y, z) for a hole or slot by its tag"
                        ),
                    },
                },
                required=["subject", "query"],
            ),
            output_schema=_object_schema(
                {"measurement": {"$ref": _MEASUREMENT_REF}},
                required=["measurement"],
            ),
            cost=Cost.BOUNDED,
            subject="subject",
            backing="anvilate.geometry:measure_geometry",
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
                    "spec": _spec_input(),
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
                        "description": (
                            "screen only these tiers instead of the spec's own acceptance.tiers"
                        ),
                    },
                },
                required=["spec"],
            ),
            output_schema=_object_schema(
                {"scorecard": {"$ref": _SCORECARD_REF}, "subject": _SUBJECT_SCHEMA},
                required=["scorecard", "subject"],
            ),
            writes=True,
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
                "tolerance, not on a clock, so a client that declares the Tasks extension "
                "gets a task: progress is reportable, cancellation terminates the solver "
                "subprocesses, and a cancelled run reports its affected checks as not "
                "evaluated rather than as passing. Any other client gets the same result in "
                "the reply. This release ships no finite-element solver, so T3 is reported "
                "not evaluated, with that reason."
            ),
            input_schema=_object_schema(
                {
                    "spec": _spec_input(),
                    "convergence_tol": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "description": "the relative change between meshes a result must settle to",
                    },
                },
                required=["spec"],
            ),
            output_schema=_object_schema(
                {"scorecard": {"$ref": _SCORECARD_REF}},
                required=["scorecard"],
            ),
            writes=True,
            cost=Cost.UNBOUNDED,
            tiers=(ValidationTier.T3_FEA,),
            backing="anvilate.screening:screen_spec",
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
                "Export what the engineer takes away. From a run_validation handle: the "
                "evidence bundle (returned, and written), a QIF results file, or the one-page "
                "part sheet. From a build_part handle: the STEP file to open in CAD, a 3MF "
                "mesh, or a DXF profile for a flat part. From a build_combination handle: "
                "step, an assembly with each part a named component. Files are written to "
                "the server's "
                "output folder and the result names each path, size and SHA-256; no tool "
                "takes a destination. STEP, 3MF, DXF and QIF are written only when the "
                "part's checks pass, and this surface grants no override. A part that is "
                "drawn and has no screen is written marked unvalidated, and the result "
                "says so."
            ),
            input_schema=_object_schema(
                {
                    "subject": _SUBJECT_SCHEMA,
                    "format": {"type": "string", "enum": list(_EXPORT_FORMATS)},
                },
                required=["subject", "format"],
            ),
            output_schema=_object_schema(
                {
                    "format": {"type": "string"},
                    # The bundle itself, as the primitives `BundleSections.to_document_dict`
                    # produces — the roll-up *and* the card, because a bundle whose checks a
                    # reviewer cannot read is not evidence. Present for `evidence_bundle`.
                    "bundle": {"$ref": _BUNDLE_REF},
                    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    # The file a call wrote: where, how big, and its digest. Absent only
                    # for a bundle returned by a server with no output folder.
                    "file": _FILE_SCHEMA,
                    # False, with the reason, for a part that is drawn and not checked: the
                    # file is written and carries the unvalidated mark. Absent otherwise.
                    "validated": {"type": "boolean"},
                    "note": {"type": "string"},
                },
                required=["format", "sha256"],
            ),
            writes=True,
            cost=Cost.BOUNDED,
            emits_artifacts=True,
            backing="anvilate.bundle:BundleSections",
            subject="subject",
        ),
        ToolDefinition(
            name="build_combination",
            title="Build a combination of parts",
            description=(
                "Place two or more catalog parts by the features they share, and check "
                "where they meet. The document names its parts, each with its own Design "
                "Spec, and the mates that place each one on a part before it: "
                "hole_pattern, face_to_face, edge_flush or shaft_in_bore. No coordinates "
                "are written. hardware puts a bolt, washers and a nut in every hole of a "
                "hole_pattern mate. Returns where each part landed, the parts list, and a "
                "scorecard: each part's own verdict, whether mated holes line up, bolt "
                "clearance and length, and interference between every pair. The subject "
                "handle goes to render_viewport for the picture and to export_artifact "
                "with format step for a STEP assembly."
            ),
            input_schema=_object_schema(
                {
                    "combination": {
                        "type": "object",
                        "description": (
                            "{name, parts: [{id, spec}], mates: [{id, kind, place: {part, "
                            "face, holes, axis, feature}, on: {...}, offset, "
                            "rotation_deg}], hardware: [{mate, bolt, length, washer, "
                            "nut}], welds: [{mate, type, size}]}. The first part is the "
                            "base. face is top, bottom, left, right, front or back; holes "
                            "are feature tags from build_part, paired in order; axis is "
                            'x, y or z. Example mate: {"id": "bolted", "kind": '
                            '"hole_pattern", "place": {"part": "bracket", '
                            '"face": "bottom", "holes": ["b1", "b2"]}, '
                            '"on": {"part": "plate", "face": "top", '
                            '"holes": ["a1", "a2"]}}'
                        ),
                    },
                },
                required=["combination"],
            ),
            output_schema=_object_schema(
                {
                    "combination": {"$ref": _COMBINATION_REF},
                    "scorecard": {"$ref": _SCORECARD_REF},
                    "subject": _SUBJECT_SCHEMA,
                },
                required=["combination", "scorecard", "subject"],
            ),
            writes=True,
            cost=Cost.BOUNDED,
            subject="combination",
            backing="anvilate.combination:build_combination",
        ),
        ToolDefinition(
            name="list_context",
            title="List a context folder",
            description=(
                "List the engineering files in a folder the user pointed this server at, "
                "and whose each is to read: Anvilate measures STEP, DXF, STL and 3MF with "
                "read_cad_file; images, PDFs and text are yours to read; DWG, IGES and "
                "native CAD files need exporting first, and the listing says how. Pass "
                '"." for the context folder itself. Nothing is opened.'
            ),
            input_schema=_object_schema(
                {
                    "folder": {
                        "type": "string",
                        "minLength": 1,
                        "description": 'a folder inside the context, or "." for its root',
                    },
                },
                required=["folder"],
            ),
            output_schema=_object_schema(
                {"inventory": {"$ref": _CONTEXT_INVENTORY_REF}},
                required=["inventory"],
            ),
            cost=Cost.BOUNDED,
            subject="folder",
            backing="anvilate.context:inventory",
        ),
        ToolDefinition(
            name="read_cad_file",
            title="Measure a CAD file",
            description=(
                "Measure one STEP, DXF, STL or 3MF file in the context folder instead of "
                "reading its text. Returns its size, volume, holes with diameters and "
                "positions, hole patterns, and for a DXF its closed profiles and "
                "dimensions, in millimetres, with the unit the file was written in and "
                "its SHA-256. A DXF or STL that states no unit needs unit. When the file "
                "is a shape the catalog draws (a plate with holes, a flange, a tube), seed "
                "holds that part's element_params and the sources citing the file: add "
                "the fields seed.missing names and build it. A spec value "
                "taken from a file cites it in the spec's sources (field, origin, file, "
                "sha256, locator): measured_from_file for these numbers, agent_read for "
                "one you read off a picture or PDF yourself. Leave confirmed_by empty; "
                "that is the engineer's to fill."
            ),
            input_schema=_object_schema(
                {
                    # `source`, not `path`: every path-like name on this surface would read as
                    # somewhere to write, and no tool takes a destination.
                    "source": {
                        "type": "string",
                        "minLength": 1,
                        "description": "a file inside the context folder, as list_context names it",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["mm", "cm", "m", "in", "ft"],
                        "description": "the unit of a DXF or STL that states none",
                    },
                },
                required=["source"],
            ),
            output_schema=_object_schema(
                {
                    "facts": {"$ref": _CAD_FACTS_REF},
                    # Present when the file is a shape the catalog draws: that part's
                    # parameters filled from the measurements, the sources that cite the
                    # file for each, and the fields a file of this kind cannot give.
                    "seed": {
                        "type": "object",
                        "properties": {
                            "element_type": {"type": "string"},
                            "element_params": {"type": "object"},
                            "sources": {"type": "array", "items": {"type": "object"}},
                            "missing": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["element_type", "element_params", "sources", "missing"],
                        "additionalProperties": False,
                    },
                },
                required=["facts"],
            ),
            cost=Cost.BOUNDED,
            subject="source",
            backing="anvilate.context:read_cad_file",
        ),
        ToolDefinition(
            name="describe_part",
            title="List the parts, or describe one",
            description=(
                "Call this before writing a spec for a part. With no element_type it lists "
                "every element a spec can declare, with whether build_part draws it and "
                "whether a screen checks it. With an element_type it returns that "
                "element's fields, which are required and what each takes, and an example "
                "spec to copy and edit. The example's values are placeholders: replace "
                "each with what the user stated."
            ),
            input_schema=_object_schema(
                {
                    "element_type": {
                        "type": "string",
                        "minLength": 1,
                        "description": "an element to describe, such as mounting_plate",
                    },
                },
                required=[],
            ),
            output_schema=_object_schema(
                {"catalog": {"$ref": _PART_CATALOG_REF}},
                required=["catalog"],
            ),
            cost=Cost.BOUNDED,
            reads_shipped_catalog=True,
            backing="anvilate.patterns:describe_part",
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
        if ref not in {
            _SPEC_REF,
            _SCORECARD_REF,
            _BUNDLE_REF,
            _GEOMETRY_REF,
            _VIEWPORT_REF,
            _MEASUREMENT_REF,
            _PART_CATALOG_REF,
            _CONTEXT_INVENTORY_REF,
            _CAD_FACTS_REF,
            _COMBINATION_REF,
        }:
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
    missing = sorted((REQUIRED_OPERATIONS | _LOOKUPS) - set(names))
    if missing:
        issues.append(f"the spec requires operations the catalog does not expose: {missing}")
    extra = sorted(set(names) - REQUIRED_OPERATIONS - _LOOKUPS)
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
        if tool.output_schema is not None:
            issues.extend(_schema_issues(tool, "output_schema", tool.output_schema))
        referenced |= _refs(tool.input_schema) | _refs(tool.output_schema or {})
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
# The revisions this server can speak, newest first. A client names the one it wants, and
# the server answers with that one when it can: Claude Code 2.1 asks for 2025-11-25 and
# refused to connect at all ("Server's protocol version is not supported: 2026-07-28")
# while the server answered with its own revision regardless. The tool surface is the same
# in each; what an older revision lacks is `resultType` on a result, which
# `_for_revision` removes.
SUPPORTED_PROTOCOL_REVISIONS = ("2026-07-28", "2025-11-25", "2025-06-18", "2025-03-26")


def negotiated_revision(requested: object) -> str:
    """The revision to answer ``requested`` with: itself when supported, else the newest."""
    return requested if requested in SUPPORTED_PROTOCOL_REVISIONS else PROTOCOL_REVISION


def _initialize_reply(request_id: Any, revision: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "resultType": "complete",
            "protocolVersion": revision,
            "capabilities": {
                "tools": {"listChanged": False},
                "extensions": {TASKS_EXTENSION: {}},
            },
            # `version` is required of an Implementation, and its absence failed the
            # official conformance suite's handshake before any other check could run.
            # The installed distribution's, as `anvilate --version` reports it.
            "serverInfo": {"name": "anvilate", "title": "Anvilate", "version": _version()},
            "instructions": agent_instructions(),
        },
    }


def _for_revision(response: dict[str, Any] | None, revision: str) -> dict[str, Any] | None:
    """``response`` as ``revision`` defines a result: no `resultType` before 2026-07-28.

    Only a completed result is reshaped. A task result keeps its shape, and an older client
    never receives one: it cannot declare the Tasks extension, so the task tool answers it
    synchronously instead.
    """
    if revision >= "2026-07-28" or response is None:
        return response
    result = response.get("result")
    if isinstance(result, dict) and result.get("resultType") == "complete":
        return {**response, "result": {k: v for k, v in result.items() if k != "resultType"}}
    return response


# What an agent has to be told besides the schemas, found by running a real model through the
# compiler (qwen2.5:14b, 2026-10-08) before the local adapters were removed. Handed only the
# schema, it wrote a stated minimum safety factor into `max_safety_factor`, dropped the load,
# spelled the material "ASTM A36" where the database says ASTM-A36, invented a hole pattern,
# asked for every validation tier, and named no element, so nothing would have screened. The
# schema says what is legal; these say what a request means and which identifiers exist.
_AGENT_RULES = """Anvilate is a local, deterministic engineering checker: you write the
Design Spec, it validates and screens it. describe_part gives an element's fields and an
example spec; run_validation and build_part each return a subject handle the other tools
take. Fix what a refusal names and call again; never report a check that did not run.
- Write only what the user stated: no invented interfaces, dimensions, exports or loads. Ask
  for a missing load, material or interface; do not guess it.
- A stated minimum safety factor is constraints.min_safety_factor ({"value": 2.0, "origin":
  "user_stated"}); max_safety_factor is only an explicit upper limit.
- To screen or draw a part, set element_type to an element below and its fields in
  element_params. acceptance.tiers is ["T1_analytical"] for a check or screen.
- Copy identifiers exactly as listed. A quantity is {"magnitude": 50, "unit": "kN"} in the
  user's units; a product of units uses "*": "kN*m"."""

# Claude Code 2.1 keeps the first 2,048 characters of a server's instructions and drops the
# rest ("Server instructions truncated from 10192 to 2048 chars", its debug log, 2026-10-09).
# The catalogue used to start with every component and section, so the element screens, the
# one list an agent cannot write a spec without, were never seen: an agent asked to screen a
# padeye guessed `padeye`, `lug` and `pad_eye`. The rules, element names and material ids
# come first and are held under this limit by a test; the detail after it is also what the
# refusals name, so a client that cuts it loses speed, not the way forward.
CLIENT_INSTRUCTIONS_LIMIT = 2048


def _closed_values(annotation: Any) -> tuple[str, ...]:
    """The spellings a field accepts when it is a closed set (an enum or a Literal), else ().

    A field named without its values is a field the agent fills by guessing the spelling,
    which is the failure the catalogue exists to prevent for material identifiers.
    """
    from enum import Enum
    from typing import Literal, get_args, get_origin

    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return tuple(str(member.value) for member in annotation)
    if get_origin(annotation) is Literal:
        return tuple(str(value) for value in get_args(annotation))
    return tuple(value for arg in get_args(annotation) for value in _closed_values(arg))


@cache
def agent_instructions() -> str:
    """The rules and the live catalogue an agent writes specs against.

    Sent as the initialize result's ``instructions``, which a client adds to the model's
    context. Generated from the resolver and the element registry, never hand-written, so it
    cannot name a material the database lacks or a field a screen does not read.
    """
    from .screening import element_registry
    from .standards import default_standards_resolver
    from .standards.profiles import default_profile_table

    resolver = default_standards_resolver()
    lines = [
        _AGENT_RULES,
        "",
        "Elements: " + ", ".join(sorted(element_registry())),
        "Materials: " + ", ".join(resolver.known_materials()),
        "",
        "Detail (a client may cut what follows; refusals name the same fields and ids):",
        "Components: " + ", ".join(resolver.known_components()),
        # An agent that does not know a `section` can be named computes one, and a section's
        # properties are the numbers easiest to get wrong from memory.
        "Rolled sections (a member's `section` may name one instead of stating its "
        "properties): " + ", ".join(default_profile_table().designations()) + "; AISC "
        "W-shapes such as W12x26 once the user has run `anvilate fetch aisc-shapes --consent`.",
        "Element screens (element_type: fields; * marks required):",
    ]
    for tag, (model, _screen) in sorted(element_registry().items()):
        summary = (model.__doc__ or "").strip().split("\n")[0].rstrip(".")
        fields = ", ".join(
            f"{name}{'*' if field.is_required() else ''}"
            + (f"={'|'.join(values)}" if (values := _closed_values(field.annotation)) else "")
            for name, field in model.model_fields.items()
        )
        lines.append(f"- {tag}: {summary}. Fields: {fields}")
    return "\n".join(lines)


def _version() -> str:
    """The installed distribution's version, never ``anvilate.__version__``."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("anvilate")
    except PackageNotFoundError:  # pragma: no cover - a source tree with nothing installed
        return "0+not-installed"


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
    if tool.output_schema is None:
        # An image result has no published shape to hold it to; the image document it is
        # built from was validated by its own model when it was rendered.
        return []
    return _object_issues(tool.name, structured, tool.output_schema, noun="result property")


def _object_issues(
    label: str, document: Mapping[str, Any], schema: Mapping[str, Any], *, noun: str
) -> list[str]:
    """One JSON object against one closed 2020-12 object schema, top level only.

    Shared by the input and output checks so a constraint taught to one is understood by
    the other; ``noun`` is what an unexpected property is called in the message, because
    "takes no argument" is wrong about something the server sent.
    """
    if not isinstance(document, Mapping):
        # A complaint, not a traceback. This function's whole product is a list of what is
        # wrong with a document, and "it is not an object" is the first thing that can be
        # wrong with one — `result_issues` answered a string with `'str' object has no
        # attribute 'items'`, from inside the loop below. The same reasoning
        # `contracts.schema_issues` follows about a schema that is not a mapping.
        return [f"{label} is a JSON object; got {type(document).__name__}"]
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
            return [_type_refusal(label, "object", value)]
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
        return [_type_refusal(label, declared, value)]
    return _value_issues(label, value, schema)


def _type_refusal(label: str, declared: str, value: Any) -> str:
    """``value`` is not a JSON ``declared``, said so that the model can correct the call.

    The common case is not a wrong value but a right one encoded twice: an object sent as
    the string of its JSON. "got str" alone was the whole answer to that, and in the
    2026-10-09 measurement agents retried the same string until they gave up.
    """
    if declared in ("object", "array") and isinstance(value, str):
        try:
            decoded = parse_json(value)
        except ValueError:
            decoded = None
        if isinstance(decoded, _JSON_TYPES[declared]):
            return (
                f"{label} must be a JSON {declared}; got a string holding one. Pass the "
                f"{declared} itself as the argument, not its JSON encoding"
            )
    return f"{label} must be a JSON {declared}; got {type(value).__name__}"


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
    # A JSON number is finite (RFC 8259 §6), but Python's reader takes `NaN` and `Infinity`
    # and overflows `1e999` to infinity. Infinity is "above 0", so `convergence_tol` took it
    # and asked for an FEA run that every iterate converges on; NaN failed the bound with a
    # reason that was not the problem.
    if not math.isfinite(value):
        return [f"{label} must be a finite JSON number; got {value}"]
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


def _argument_remedy_text(operation: str) -> str:
    return (
        f"correct the named {operation} argument using its inputSchema from tools/list, "
        f"then call {operation} again"
    )


def _argument_remedy_record(operation: str) -> Remedy:
    return Remedy.rendered(
        action="correct",
        subject=f"the named {operation} argument",
        source=f"the {operation} inputSchema returned by tools/list",
        text=_argument_remedy_text(operation),
    )


class _InvalidArguments(RefusalError):
    """A handler's own refusal of arguments the published schema could not check itself.

    :func:`_argument_issues` validates what a tool's input schema states inline — types,
    enums, bounds. It does not follow a ``$ref``, so a property declared as "a Design Spec"
    is checked by the handler that has to parse one, and this is how that refusal reaches
    the client as INVALID_PARAMS rather than as a traceback.
    """

    def __init__(
        self,
        issues: list[str],
        *,
        operation: str,
        remedies: tuple[str, ...] = (),
    ) -> None:
        self.issues = tuple(issues)
        structured = tuple(
            Remedy.rendered(
                action="apply",
                subject=f"the Design Spec correction: {text}",
                source="the published Design Spec schema and validation issue",
                text=text,
            )
            for text in dict.fromkeys(remedies)
        ) or (_argument_remedy_record(operation),)
        super().__init__("; ".join(issues), remedies=structured)


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


def _argument_remedy(tool: ToolDefinition) -> str:
    """The fallback repair when a handler cannot name a more specific edit."""
    return _argument_remedy_text(tool.name)


def _client_supports_tasks(params: Mapping[str, Any]) -> bool:
    """Whether this request declares the extension, with no remembered handshake."""
    metadata = params.get("_meta")
    if not isinstance(metadata, Mapping):
        return False
    capabilities = metadata.get("io.modelcontextprotocol/clientCapabilities")
    if not isinstance(capabilities, Mapping):
        return False
    extensions = capabilities.get("extensions")
    return isinstance(extensions, Mapping) and TASKS_EXTENSION in extensions


def _task_params(request_id: Any, request: Mapping[str, Any]) -> tuple[str | None, dict | None]:
    """Read the common task argument, returning an error payload when malformed."""
    params = request.get("params")
    if not isinstance(params, Mapping):
        return None, _error(request_id, INVALID_PARAMS, "task params must be a JSON object")
    task_id = params.get("taskId")
    if not isinstance(task_id, str):
        return None, _error(request_id, INVALID_PARAMS, "taskId must be a JSON string")
    return task_id, None


def handle_request(request: Mapping[str, Any]) -> dict[str, Any] | None:
    """One JSON-RPC request to one JSON-RPC response, with no state between calls.

    A pure function, not a server: it takes the decoded request object and returns the
    object to encode back, so a stdio loop, an HTTP handler and a test all drive the same
    code. ``None`` is returned for a notification (a request with no ``id``), which the
    protocol says takes no response.

    Request structure is checked before notification handling. JSON-RPC 2.0 sections
    4–5 distinguish a valid notification from an invalid object with no id: the former
    is silent, while the latter receives ``-32600`` with ``"id": null``.

    ``initialize`` reports the protocol revision and capabilities. ``tools/list`` returns
    :func:`wire_definitions`. ``tools/call`` validates the arguments against the published
    input schema and dispatches bounded work directly. The Tasks extension adds
    ``tasks/get``, ``tasks/update`` and ``tasks/cancel`` for backed unbounded work.

    **A call is checked at both ends against the same document the client was handed.**
    Arguments in by :func:`_argument_issues`, structured content out by
    :func:`result_issues`; a result the published ``outputSchema`` rejects is an
    INTERNAL_ERROR naming the property, not a payload sent for the client to choke on.

    An operation with no handler is refused with that reason rather than answered, because
    a plausible-looking result for something nobody wired is indistinguishable from a real
    one. Two further boundaries are structural:

    * **An unbounded tool requires negotiated task support.** ``run_fea_validation``
      returns a durable handle only when the request declares the extension. ``build_part``
      remains unavailable because no sandboxed geometry generator exists to launch.
    * **Every tool names what it acts on.** :func:`stateless_gaps` is empty and stays
      empty: a tool that named nothing was asking the server to remember its last call,
      which is a session, and four of them did. They take subject handles now — see
      :mod:`anvilate.store` — and the refusal is still here for the tool that stops
      declaring one.
    """
    if not isinstance(request, Mapping):
        return _error(None, INVALID_REQUEST, "a JSON-RPC request is an object")
    if request.get("jsonrpc") != "2.0":
        return _error(None, INVALID_REQUEST, "not a JSON-RPC 2.0 request")
    method = request.get("method")
    if not isinstance(method, str):
        return _error(None, INVALID_REQUEST, "a JSON-RPC method must be a string")
    request_id = request.get("id")
    if "id" in request and (isinstance(request_id, bool) or not isinstance(request_id, (str, int))):
        return _error(None, INVALID_REQUEST, "an MCP request id must be a string or integer")
    if "params" in request and not isinstance(request["params"], Mapping):
        return _error(None, INVALID_REQUEST, "MCP params must be a JSON object")
    # Method-level argument failures never produce a reply to a valid notification.
    if "id" not in request:
        return None

    if method == "initialize":
        revision = negotiated_revision((request.get("params") or {}).get("protocolVersion"))
        return _for_revision(_initialize_reply(request_id, revision), revision)
    if method == "ping":
        # A receiver MUST answer ping promptly with an empty result (basic/utilities/ping);
        # it was answered "unknown method".
        return {"jsonrpc": "2.0", "id": request_id, "result": {"resultType": "complete"}}
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"resultType": "complete", "tools": wire_definitions()},
        }
    if method in {"tasks/get", "tasks/update", "tasks/cancel"}:
        from ._mcp_tasks import UnknownTask, task_store

        task_id, malformed = _task_params(request_id, request)
        if malformed is not None:
            return malformed
        assert task_id is not None
        store = task_store()
        try:
            if method == "tasks/get":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"resultType": "complete", **store.public(task_id)},
                }
            if method == "tasks/update":
                responses = request["params"].get("inputResponses")
                if not isinstance(responses, Mapping):
                    return _error(
                        request_id, INVALID_PARAMS, "inputResponses must be a JSON object"
                    )
                store.read(task_id)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"resultType": "complete"},
                }
            store.cancel(
                task_id,
                _task_call_result(_cancelled_fea_result()),
                "Cancellation honored; T3 FEA was not evaluated.",
            )
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"resultType": "complete"},
            }
        except UnknownTask as unknown:
            return _error(request_id, INVALID_PARAMS, str(unknown.args[0]))
    if method != "tools/call":
        return _error(request_id, METHOD_NOT_FOUND, f"unknown method {method!r}")

    params = request.get("params")
    if params is None:
        params = {}
    if not isinstance(params, Mapping):
        return _error(
            request_id,
            INVALID_PARAMS,
            "tool params must be a JSON object",
            remedies=["write tools/call params as a JSON object with name and arguments"],
        )
    name = params.get("name")
    if not isinstance(name, str):
        return _error(
            request_id,
            INVALID_PARAMS,
            "tool name must be a JSON string",
            remedies=["write params.name as a tool name returned by tools/list"],
        )
    tools = {tool.name: tool for tool in tool_catalog()}
    tool = tools.get(name)
    if tool is None:
        return _error(
            request_id,
            METHOD_NOT_FOUND,
            f"unknown tool {name!r}",
            remedies=["choose params.name from the tool names returned by tools/list"],
        )

    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return _error(
            request_id,
            INVALID_PARAMS,
            "arguments must be a JSON object",
            remedies=[_argument_remedy(tool)],
        )
    issues = _argument_issues(tool, arguments)
    if issues:
        return _error(
            request_id,
            INVALID_PARAMS,
            "; ".join(issues),
            issues=issues,
            remedies=[_argument_remedy(tool)],
        )

    if tool.dispatch is Dispatch.TASK:
        if tool.name not in _TASK_DISPATCH:
            return _error(
                request_id,
                TOOL_UNAVAILABLE,
                f"{tool.name} is task-dispatched, but {_UNBUILT_TASKS[tool.name]}",
                remedies=[
                    f"enable the {tool.name} task capability named in this error or use a "
                    "served validation tier"
                ],
            )
        if _client_supports_tasks(params):
            from ._mcp_tasks import launch_task

            task = launch_task(tool.name, arguments)
            return {"jsonrpc": "2.0", "id": request_id, "result": {"resultType": "task", **task}}
        # A client without the Tasks extension gets the answer in the reply instead. Claude
        # Code 2.1 declares none, and refusing it (-32021, until 2026-10-09) left the most
        # common client with no T3 tier at all. The handler is the task's own, so the two
        # paths cannot disagree about a result. It returns at once today because this
        # release ships no finite-element solver and says T3 was not evaluated; a solver
        # that lands here must bring a deadline for this path, past which its checks are
        # reported not evaluated rather than left to hang the call.
        handler = _TASK_DISPATCH[tool.name]
    else:
        handler = None
    if not tool.is_stateless:
        return _error(
            request_id,
            TOOL_UNAVAILABLE,
            f"{tool.name} names nothing in its input to act on, so a server with no memory "
            f"between calls cannot serve it. Either the tool takes what it acts on as an "
            f"argument or the server holds a session; the contract does not yet say which",
            remedies=[f"supply the {tool.name} subject through the argument named by tools/list"],
        )
    handler = handler or _DISPATCH.get(tool.name)
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
            remedies=[f"use the {tool.name} capability or alternative named in this error"],
        )
    try:
        structured = handler(arguments)
    except _InvalidArguments as refusal:
        return _error(
            request_id,
            INVALID_PARAMS,
            str(refusal),
            issues=list(refusal.issues),
            remedies=[str(remedy) for remedy in refusal.remedies],
        )
    except _Unavailable as refusal:
        return _error(
            request_id,
            TOOL_UNAVAILABLE,
            str(refusal),
            remedies=[f"use the {tool.name} capability or alternative named in this error"],
        )
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
    return {"jsonrpc": "2.0", "id": request_id, "result": _task_call_result(structured)}


def _task_call_result(structured: Mapping[str, Any]) -> dict[str, Any]:
    """The CallToolResult shared by synchronous calls and completed task calls."""
    document = dict(structured)
    viewport = document.get("viewport")
    if isinstance(viewport, Mapping) and isinstance(viewport.get("image"), str):
        return _image_call_result(viewport, document.get("file"))
    return {
        "content": [{"type": "text", "text": json.dumps(document, sort_keys=True)}],
        "structuredContent": document,
        "isError": bool(document.get("errors")),
    }


def _image_call_result(viewport: Mapping[str, Any], file: Any) -> dict[str, Any]:
    """A rendered view as the model can see it: one sentence, then the image, nothing else.

    No ``structuredContent``. Claude Code and Codex both pass only the structured content to
    the model when a result has it beside an image, and a render the agent cannot look at
    is not a render. The sentence carries what the structured document used to: the view,
    the size, the digest and where the file was written.
    """
    where = (
        f"written to {file['path']}"
        if isinstance(file, Mapping)
        else "not written to disk (the server has no output folder)"
    )
    summary = (
        f"{viewport['view']} view, {viewport['width_px']}x{viewport['height_px']} px, "
        f"{viewport['mime_type']}, sha256 {viewport['sha256']}; {where}."
    )
    return {
        "content": [
            {"type": "text", "text": summary},
            {"type": "image", "data": viewport["image"], "mimeType": viewport["mime_type"]},
        ],
        "isError": False,
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
_BUILT_GEOMETRY = "built-geometry"
# Which operation publishes each kind a tool can ask for. A handle of the wrong kind was
# refused with the two kind names and nothing else, and in the 2026-10-09 measurement agents
# that passed compile_spec's handle to read_scorecard or render_viewport gave up there.
_BUILT_COMBINATION = "built-combination"
_PUBLISHED_BY = {
    _SCREENING: "run_validation",
    _BUILT_GEOMETRY: "build_part",
    _BUILT_COMBINATION: "build_combination",
}


def _producer_named(wrong: _WrongKind, kind: str) -> _WrongKind:
    """``wrong``, with the operation that publishes a ``kind`` handle named in its message."""
    producer = _PUBLISHED_BY[kind]
    return _WrongKind(
        f"{wrong.args[0]}. A {kind} handle is the `subject` that {producer} returns: call "
        f"{producer} with the Design Spec and pass the subject it replies with",
        found=wrong.found,
    )


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
    except _WrongKind as wrong:
        message = str(wrong.args[0])
        if wrong.found == "scorecard":
            raise UnknownSubject(
                f"{message}. A handle used to name the scorecard alone; it names the spec "
                f"and the scorecard together now, so that an exported evidence bundle "
                f"carries the inputs its verdicts were computed from. Call run_validation "
                f"again to publish a handle of the current shape"
            ) from wrong
        raise _producer_named(wrong, _SCREENING) from wrong

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
        # The remedies also ride inside each error line; here they are the same list the
        # CLI's JSON refusal reads, so an agent does not have to parse them back out.
        return {
            "errors": [_refusal_line(e["loc"], e["msg"]) for e in failure.errors],
            "remedies": list(failure.remedy_texts),
        }
    except (ValueError, TypeError, KeyError) as failure:
        # parse_spec raises SpecValidationError for a schema failure; anything else is a
        # document it could not even attempt, and it still belongs in `errors` rather than
        # crashing the loop that called it.
        return {"errors": [_reason(failure)]}
    from .screening import _compile_findings

    problems, remedies = _compile_findings(spec, _MODULES) if _MODULES else _compile_findings(spec)
    if problems:
        return {"errors": problems, "remedies": remedies}
    # Published, so the next call has something to name. A compiled document is the subject
    # `run_validation` and the geometry tools act on, and a handle is what keeps the payload
    # off the wire without giving the server a memory between calls.
    document_json = spec.model_dump(mode="json")
    handle = subject_store().publish("design-spec", document_json)
    return {"spec": document_json, "errors": [], "subject": handle}


def _build_part(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Build one audited Design Spec pattern and return its kernel-checked summary."""
    from .geometry import GeometryError, GeometryUnavailable, UnsupportedGeometry, build_spec
    from .spec import SpecValidationError, parse_spec

    try:
        spec = parse_spec(dict(arguments["spec"]))
    except SpecValidationError as failure:
        raise _InvalidArguments(
            [_refusal_line(f"spec.{e['loc']}".rstrip("."), e["msg"]) for e in failure.errors],
            operation="build_part",
            remedies=failure.remedy_texts,
        ) from failure
    except (ValueError, TypeError, KeyError) as failure:
        raise _InvalidArguments([f"spec: {_reason(failure)}"], operation="build_part") from failure
    try:
        built = build_spec(spec)
    except (GeometryUnavailable, UnsupportedGeometry) as failure:
        raise _Unavailable(str(failure)) from failure
    except GeometryError as failure:
        raise _InvalidArguments(
            [f"spec.element_params: {failure}"], operation="build_part"
        ) from failure
    geometry = built.summary().model_dump(mode="json", by_alias=True)
    handle = subject_store().publish(
        _BUILT_GEOMETRY,
        {"spec": spec.model_dump(mode="json"), "geometry": geometry},
    )
    return {
        "geometry": geometry,
        "warnings": [],
        "subject": handle,
    }


def _built_geometry(handle: str):
    """Resolve and regenerate the exact built geometry named by ``handle``."""
    from .geometry import GeometryUnavailable, build_spec
    from .spec import parse_spec

    try:
        try:
            record = subject_store().resolve(handle, kind=_BUILT_GEOMETRY)
        except _WrongKind as wrong:
            raise _producer_named(wrong, _BUILT_GEOMETRY) from wrong
        spec = parse_spec(record["spec"])
        expected = GeometrySummary.model_validate(record["geometry"])
        built = build_spec(spec)
    except (UnknownSubject, GeometryUnavailable):
        # The record is fine; this install cannot regenerate it. Building again cannot help.
        raise
    except (ValueError, TypeError, KeyError) as unreadable:
        raise UnknownSubject(
            f"{handle} resolves to a built-geometry record this build cannot read "
            f"({unreadable}). Call build_part again to publish a current handle"
        ) from unreadable
    actual = built.summary()
    if actual != expected:
        raise UnknownSubject(
            f"{handle} resolves to geometry that no longer regenerates to its stored "
            "summary. Call build_part again before rendering"
        )
    return built


def _written(name: str, data: bytes) -> dict[str, Any] | None:
    """Write one result into the output folder, or ``None`` when the server has none."""
    if output_folder() is None:
        return None
    return write_output(name, data)


def _title_block(handle: str, built: Any) -> tuple[str, ...]:
    """The overview's rows: overall size, material and verdict, from the spec that was built."""
    from .screening import screen_spec
    from .spec import parse_spec

    box = built.shape.bounding_box()
    size = " x ".join(f"{extent:.4g}" for extent in (box.size.X, box.size.Y, box.size.Z)) + " mm"
    spec = parse_spec(subject_store().resolve(handle, kind=_BUILT_GEOMETRY)["spec"])
    verdict = screen_spec(spec, **_screening_options(spec)).status.value
    return (size, str(spec.material.ref), verdict.replace("_", " "))


def _render_viewport(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Render a built-geometry subject as a schema-backed MCP image attachment."""
    from .geometry import (
        GeometryError,
        GeometryUnavailable,
        UnsupportedGeometry,
        render_overview,
        render_viewport,
    )

    try:
        combination = _built_combination(arguments["subject"])
        if combination is not None:
            return _render_combination(combination, arguments)
        built = _built_geometry(arguments["subject"])
        if arguments["view"] == "overview":
            rendered = render_overview(
                built,
                lines=_title_block(arguments["subject"], built),
                width_px=arguments.get("width_px", 1000),
                format=arguments.get("format", "png"),
            )
        else:
            rendered = render_viewport(
                built,
                view=arguments["view"],
                width_px=arguments.get("width_px", 800),
                format=arguments.get("format", "png"),
                dimensions=bool(arguments.get("dimensions", False)),
            )
    except UnknownSubject as unknown:
        raise _InvalidArguments(
            [f"subject: {unknown.args[0]}"], operation="render_viewport"
        ) from unknown
    except (GeometryUnavailable, UnsupportedGeometry) as failure:
        raise _Unavailable(str(failure)) from failure
    except GeometryError as failure:
        raise _InvalidArguments([str(failure)], operation="render_viewport") from failure
    extension = "png" if rendered.format == "png" else "svg"
    file = _written(f"{safe_stem(built.name)}-{rendered.view}.{extension}", rendered.data)
    return {"viewport": rendered.document().model_dump(mode="json"), "file": file}


def _build_combination(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """``build_combination``: parts placed by their mates, checked, counted, and named."""
    from .combination import CombinationError, build_combination, parse_combination
    from .geometry import GeometryUnavailable

    try:
        combination = parse_combination(arguments["combination"])
        built = build_combination(combination)
    except GeometryUnavailable as failure:
        raise _Unavailable(str(failure)) from failure
    except CombinationError as refused:
        raise _InvalidArguments(
            [f"combination: {refused}"], operation="build_combination"
        ) from refused
    handle = subject_store().publish(
        _BUILT_COMBINATION, {"combination": combination.model_dump(mode="json")}
    )
    return {
        "combination": built.summary().model_dump(mode="json"),
        "scorecard": built.card.model_dump(mode="json"),
        "subject": handle,
    }


def _built_combination(handle: str) -> Any:
    """The combination ``handle`` names, rebuilt; ``None`` when the handle is another kind."""
    from .combination import build_combination, parse_combination

    try:
        record = subject_store().resolve(handle, kind=_BUILT_COMBINATION)
    except _WrongKind:
        return None
    return build_combination(parse_combination(record["combination"]))


def _render_combination(built: Any, arguments: Mapping[str, Any]) -> dict[str, Any]:
    """The combination's one picture: four views, each part numbered, the parts list below."""
    from .combination import render_combination
    from .geometry import RenderedViewport

    data, width, height = render_combination(
        built,
        width_px=arguments.get("width_px", 1100),
        format=arguments.get("format", "png"),
    )
    rendered = RenderedViewport(
        view="overview",
        width_px=width,
        height_px=height,
        data=data,
        format=arguments.get("format", "png"),
    )
    extension = "png" if rendered.format == "png" else "svg"
    file = _written(f"{safe_stem(built.name)}-assembly.{extension}", rendered.data)
    return {"viewport": rendered.document().model_dump(mode="json"), "file": file}


def _a_draft_combination(built: Any) -> bool:
    """Whether a combination that does not pass may be written marked unvalidated.

    Nothing may have failed, and every open entry must be a part that is itself a draft (one
    the catalog draws with no screen, or one resting on unconfirmed readings) or a weld that
    is declared and not screened here.
    """
    from .scorecard import CheckStatus
    from .screening import screen_spec

    if any(entry.status is CheckStatus.FAIL for entry in built.card.entries):
        return False
    drafts = {
        f"{part.id} part"
        for part in built.parts
        if _drawn_and_not_checked(part.spec, screen_spec(part.spec))
    }
    open_entries = [e for e in built.card.entries if e.status is CheckStatus.NOT_EVALUATED]
    return all(e.name in drafts or e.name.endswith(" weld") for e in open_entries)


def _export_combination(artifact: str, built: Any) -> dict[str, Any]:
    """A combination as a STEP assembly in the output folder, gated on its own card."""
    import tempfile

    from .combination import CombinationError, write_step_assembly
    from .export.gate import ExportRefused, authorize_export

    if artifact != "step":
        raise _Unavailable(
            f"export_artifact cannot write {artifact} for a combination: a combination "
            "exports as step, a STEP assembly with each part a named component"
        )
    _needs_output_folder(artifact)
    try:
        authorization = authorize_export(built.card)
    except ExportRefused as refused:
        if not _a_draft_combination(built):
            raise _Unavailable(
                f"export_artifact cannot write {artifact}: {refused.unmet}. This surface "
                "grants no override; `anvilate combine --unvalidated` at the shell writes a "
                "watermarked assembly"
            ) from refused
        authorization = authorize_export(built.card, override=True)
    try:
        with tempfile.TemporaryDirectory(prefix="anvilate-step-") as scratch:
            staged = write_step_assembly(
                built, Path(scratch) / "assembly.step", authorization=authorization
            )
            data = staged.read_bytes()
    except CombinationError as failure:
        raise _Unavailable(f"export_artifact cannot write step: {failure}") from failure
    file = write_output(f"{safe_stem(built.name)}.step", data)
    result = {"format": artifact, "sha256": file["sha256"], "file": file}
    if not authorization.validated:
        result["validated"] = False
        result["note"] = (
            "the combination's card does not pass, and nothing on it failed: it holds parts "
            "that are drawn and not checked, unconfirmed readings, or a declared weld. The "
            "file carries the unvalidated mark. Say so when you hand it over"
        )
    return result


def _list_context(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """``list_context``: the engineering files in a context folder, and whose each is."""
    from .context import ContextError, inventory, resolve_in_context

    try:
        listing = inventory(resolve_in_context(arguments["folder"]))
    except ContextError as refused:
        raise _context_refusal(refused, "folder", "list_context") from refused
    return {"inventory": listing.model_dump(mode="json")}


def _read_cad_file(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """``read_cad_file``: one CAD file in the context, measured."""
    from .context import ContextError, read_cad_file, resolve_in_context, seed_part

    try:
        facts = read_cad_file(resolve_in_context(arguments["source"]), unit=arguments.get("unit"))
    except ContextError as refused:
        raise _context_refusal(refused, "source", "read_cad_file") from refused
    result = {"facts": facts.model_dump(mode="json")}
    seed = seed_part(facts)
    if seed is not None:
        result["seed"] = {"missing": [], **seed.model_dump(mode="json")}
    return result


def _context_refusal(refused: Exception, argument: str, operation: str) -> Exception:
    """A server with no context folder is unavailable; anything else is a bad argument."""
    from .context import context_roots

    if not context_roots():
        return _Unavailable(f"{operation} cannot read files: {refused}")
    # The refusal says which argument it is about: a drawing with no unit is about `unit`.
    remedies = getattr(refused, "remedies", ())
    named = remedies[0].subject if remedies else argument
    # The library calls the file `path`; this tool's argument for it is the one named here.
    named = argument if named == "path" else named
    return _InvalidArguments([f"{named}: {refused}"], operation=operation)


def _describe_part(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """``describe_part``: every element in a line, or one with its fields and an example."""
    from .geometry import GeometryError
    from .patterns import describe_part, describe_parts

    element_type = arguments.get("element_type")
    try:
        catalog = describe_parts() if element_type is None else describe_part(element_type)
    except GeometryError as failure:
        raise _InvalidArguments(
            [f"element_type: {failure}"], operation="describe_part"
        ) from failure
    return {"catalog": catalog.model_dump(mode="json")}


def _measure_geometry(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Measure an actual regenerated B-Rep property by built-geometry subject."""
    from .geometry import GeometryError, GeometryUnavailable, measure_geometry

    try:
        built = _built_geometry(arguments["subject"])
        measurement = measure_geometry(built, arguments["query"])
    except UnknownSubject as unknown:
        raise _InvalidArguments(
            [f"subject: {unknown.args[0]}"], operation="measure_geometry"
        ) from unknown
    except GeometryUnavailable as failure:
        raise _Unavailable(str(failure)) from failure
    except GeometryError as failure:
        raise _InvalidArguments([f"query: {failure}"], operation="measure_geometry") from failure
    return {"measurement": measurement.model_dump(mode="json")}


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
            [_refusal_line(f"spec.{e['loc']}".rstrip("."), e["msg"]) for e in failure.errors],
            operation="run_validation",
            remedies=failure.remedy_texts,
        ) from failure
    except (ValueError, TypeError, KeyError) as failure:
        raise _InvalidArguments(
            [f"spec: {_reason(failure)}"], operation="run_validation"
        ) from failure
    card = screen_spec(spec, **_screening_options(spec)).model_dump(mode="json")
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
        raise _InvalidArguments(
            [f"subject: {unknown.args[0]}"], operation="read_scorecard"
        ) from unknown


def _no_override(artifact: str, unmet: str) -> _Unavailable:
    return _Unavailable(
        f"export_artifact cannot write {artifact}: {unmet}. This surface grants no "
        "override. The evidence bundle and the part sheet are written whatever the verdict "
        "and carry it; `anvilate build --unvalidated` at the shell writes a watermarked file"
    )


def _screening_options(spec: Any) -> dict[str, Any]:
    """The keywords a screen takes here: enabled modules, and where cited files are looked for.

    Empty for an ordinary spec, so the call is the one a caller of the library would make.
    A spec that cites source files has them held to their recorded digests wherever the
    server was started with a context folder to find them in.
    """
    options: dict[str, Any] = {"modules": _MODULES} if _MODULES else {}
    if spec.sources:
        from .context import context_roots

        roots = context_roots()
        if roots:
            options["source_roots"] = roots
    return options


def _drawn_and_not_checked(spec: Any, card: Any) -> bool:
    """Whether ``spec`` may be written marked unvalidated: a draft, with nothing failed.

    Two kinds of part can never pass and are not failures. One the catalog draws with no
    screen, and one whose only open entry is the confirmation of values an agent read from
    a file. Either is written with the unvalidated mark. A check that failed, or a
    screened part with a check that could not run, is still refused.
    """
    from .patterns import pattern_for
    from .scorecard import CheckStatus
    from .screening import SOURCE_CONFIRMATION_CHECK

    if any(entry.status is CheckStatus.FAIL for entry in card.entries):
        return False
    pattern = pattern_for(spec.element_type)
    if pattern is not None and not pattern.screened:
        return True
    open_entries = [e for e in card.entries if e.status is CheckStatus.NOT_EVALUATED]
    return bool(open_entries) and all(e.name == SOURCE_CONFIRMATION_CHECK for e in open_entries)


def _needs_output_folder(artifact: str) -> None:
    if output_folder() is None:
        raise _Unavailable(
            f"export_artifact cannot write {artifact}: this server was started without an "
            "output folder. Start it as `anvilate-mcp --out DIR`; no tool takes a path"
        )


def _export_built_part(artifact: str, handle: str) -> dict[str, Any]:
    """STEP, 3MF or DXF for a built part, written to the output folder when its card passes.

    The handle names the spec that was built, so the gate screens that spec, as
    `anvilate build` does: a CAD file is written for a part whose acceptance checks pass. A
    part that is drawn and not checked is written marked unvalidated, and the result says so.
    """
    import tempfile

    from .export.gate import ExportRefused, authorize_export
    from .geometry import (
        GeometryError,
        GeometryUnavailable,
        UnsupportedGeometry,
        render_3mf,
        write_step,
    )
    from .screening import screen_spec
    from .spec import parse_spec

    try:
        combination = _built_combination(handle)
    except UnknownSubject as unknown:
        raise _InvalidArguments(
            [f"subject: {unknown.args[0]}"], operation="export_artifact"
        ) from unknown
    if combination is not None:
        return _export_combination(artifact, combination)
    _needs_output_folder(artifact)
    try:
        built = _built_geometry(handle)
        spec = parse_spec(subject_store().resolve(handle, kind=_BUILT_GEOMETRY)["spec"])
    except UnknownSubject as unknown:
        raise _InvalidArguments(
            [f"subject: {unknown.args[0]}"], operation="export_artifact"
        ) from unknown
    except GeometryUnavailable as failure:
        raise _Unavailable(str(failure)) from failure
    card = screen_spec(spec, **_screening_options(spec))
    try:
        authorization = authorize_export(card)
    except ExportRefused as refused:
        # A part no screen exists for can never pass, and refusing its file would mean the
        # catalog's drawn parts could not be taken into CAD at all. It is written with the
        # unvalidated mark instead. A part with a check that failed is still refused.
        if not _drawn_and_not_checked(spec, card):
            raise _no_override(artifact, refused.unmet) from refused
        authorization = authorize_export(card, override=True)
    stem = safe_stem(built.name)
    try:
        if artifact == "step":
            with tempfile.TemporaryDirectory(prefix="anvilate-step-") as scratch:
                staged = Path(scratch) / "part.step"
                write_step(
                    built,
                    staged,
                    authorization=authorization,
                    tolerances=tuple(spec.geometric_tolerances),
                )
                data = staged.read_bytes()
            name = f"{stem}.step"
        elif artifact == "3mf":
            data, name = render_3mf(built, authorization=authorization), f"{stem}.3mf"
        else:
            from .export.dxf import render_geometry_dxf

            data = render_geometry_dxf(geometry=built, authorization=authorization)
            name = f"{stem}.dxf"
    except (UnsupportedGeometry, ImportError) as failure:
        raise _Unavailable(f"export_artifact cannot write {artifact}: {failure}") from failure
    except GeometryError as failure:
        raise _InvalidArguments([f"subject: {failure}"], operation="export_artifact") from failure
    file = write_output(name, data)
    result = {"format": artifact, "sha256": file["sha256"], "file": file}
    if not authorization.validated:
        result["validated"] = False
        waiting = [source.field for source in spec.sources if not source.confirmed]
        result["note"] = (
            f"{len(waiting)} value(s) were read by an agent and no person has confirmed "
            f"them ({', '.join(waiting)}), so the file carries the unvalidated mark. Say so "
            "when you hand it over, and ask the engineer to confirm them"
            if waiting
            else f"{spec.element_type} is drawn and not checked: no screen ships for it, so "
            "the file carries the unvalidated mark. Say so when you hand it over"
        )
    return result


def _export_artifact(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """``export_artifact``: what the engineer takes away, written where they can open it.

    **Files go to the server's output folder, and no tool names a path.** The first shape of
    this tool returned the bundle and wrote nothing, because a server writing to a path a
    caller names is a capability. That reasoning stands: the folder is chosen once, by the
    user, when the server starts, and a call can only add a file named after the part to it.
    A CAD file is never relayed through the model.

    **From a screening handle:** the evidence bundle (also returned as structured content,
    identical to the one `anvilate export` prints), QIF results, and the one-page part
    sheet. The bundle and the sheet are produced whatever the verdict, because a document
    reporting that a part failed is the one a refusal would withhold. QIF is a statement
    about a part that may be built from it, so it is gated on the card.

    **From a built-part handle:** STEP, 3MF and DXF, gated the same way
    (:func:`_export_built_part`).
    """
    from .bundle import BundleSections, combinations_for
    from .export.gate import ExportRefused, authorize_export
    from .scorecard import Scorecard
    from .screening import carbon_estimate_for
    from .spec import parse_spec
    from .standards.datasets import bundled_datasets

    artifact = arguments["format"]
    handle = arguments["subject"]
    if artifact in _FROM_BUILT_PART:
        return _export_built_part(artifact, handle)
    try:
        record = _screening(handle)
    except UnknownSubject as unknown:
        raise _InvalidArguments(
            [f"subject: {unknown.args[0]}"], operation="export_artifact"
        ) from unknown

    try:
        spec = parse_spec(record["spec"])
        card = Scorecard.model_validate(record["scorecard"])
        sections = BundleSections(
            scorecard=card,
            # Never `None` on this path. The record holds the pair, so the bundle a client
            # gets over MCP carries its inputs exactly as the one `anvilate export` prints
            # does — the parity is by construction rather than by both surfaces remembering.
            spec=spec,
            citations=provenance_for(spec),
            combinations=combinations_for(spec),
            carbon=carbon_estimate_for(spec),
            datasets=bundled_datasets(),
        )
        document = sections.to_document_dict()
    except (ValueError, TypeError, KeyError) as unreadable:
        # A handle that resolves to a record this build cannot read is the same fact as one
        # the store does not hold. `run_validation` writes these records, so the shapes that
        # reach here are a store an older release populated, or an entry something outside
        # this library wrote.
        raise _InvalidArguments(
            [
                f"subject: {handle} resolves to a screening record this build cannot read "
                f"({unreadable}). Publish the screening again with this release and export "
                f"the handle it returns"
            ],
            operation="export_artifact",
        ) from unreadable
    stem = safe_stem(str(spec.name))
    if artifact == "evidence_bundle":
        # The digest of the bundle's own canonical JSON, the same content addressing the
        # store and the attestation layer use, so the sha256 names the document returned.
        canonical = canonical_json(document).encode("utf-8")
        file = _written(f"{stem}.bundle.json", canonical)
        return {
            "format": artifact,
            "bundle": document,
            "sha256": sha256_hex(canonical),
            **({"file": file} if file is not None else {}),
        }
    _needs_output_folder(artifact)
    if artifact == "part_sheet":
        from .sheet import part_sheet

        file = write_output(f"{stem}.html", part_sheet(spec, card).html.encode("utf-8"))
        return {"format": artifact, "sha256": file["sha256"], "file": file}
    from .attestation import EnvironmentBOM
    from .export.qif import export_qif_results

    try:
        authorization = authorize_export(card)
    except ExportRefused as refused:
        raise _no_override(artifact, refused.unmet) from refused
    text = export_qif_results(
        sections,
        part_name=spec.name,
        spec_digest="sha256:"
        + sha256_hex(canonical_json(spec.model_dump(mode="json")).encode("utf-8")),
        bom=EnvironmentBOM.of_this_environment(),
        authorization=authorization,
    )
    file = write_output(f"{stem}.qif", text.encode("utf-8"))
    return {"format": artifact, "sha256": file["sha256"], "file": file}


def _cancelled_fea_result() -> dict[str, Any]:
    """The domain result of stopping T3 work: unevaluated, never passed."""
    from .scorecard import CheckStatus, Scorecard, ScorecardEntry

    card = Scorecard(
        entries=(
            ScorecardEntry(
                name="T3 FEA",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    "the task was cancelled before the converged finite-element checks "
                    "completed; the worker process group was terminated and T3 was not "
                    "evaluated"
                ),
            ),
        )
    )
    return {"scorecard": card.model_dump(mode="json")}


def _run_fea_validation_task(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Run the T3 request in a worker, returning the honest current capability.

    The task transport exists before the solver does. ``screen_spec`` owns the current T3
    answer and reports it as ``NOT_EVALUATED`` rather than manufacturing a converged result.
    Moving this call to a subprocess is still material: a future solver plugs into this one
    task handler without changing the handle, polling, cancellation, or result contract.
    """
    from .screening import screen_spec
    from .spec import SpecValidationError, parse_spec

    try:
        document = dict(arguments["spec"])
        acceptance = dict(document.get("acceptance") or {})
        acceptance["tiers"] = [ValidationTier.T3_FEA.value]
        if "convergence_tol" in arguments:
            acceptance["fea_convergence_tol"] = arguments["convergence_tol"]
        document["acceptance"] = acceptance
        spec = parse_spec(document)
    except SpecValidationError as failure:
        raise _InvalidArguments(
            [_refusal_line(f"spec.{e['loc']}".rstrip("."), e["msg"]) for e in failure.errors],
            operation="run_fea_validation",
            remedies=failure.remedy_texts,
        ) from failure
    except (ValueError, TypeError, KeyError) as failure:
        raise _InvalidArguments(
            [f"spec: {_reason(failure)}"], operation="run_fea_validation"
        ) from failure
    card = screen_spec(spec, **_screening_options(spec))
    entries = tuple(
        entry.model_copy(
            update={
                "detail": (
                    "the asynchronous T3 task completed, but this release ships no finite-"
                    "element solver backend; T3 was not evaluated"
                )
            }
        )
        if entry.name == "T3 FEA"
        else entry
        for entry in card.entries
    )
    return {"scorecard": card.model_copy(update={"entries": entries}).model_dump(mode="json")}


def _execute_task(operation: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Execute one catalogued task and return its final CallToolResult."""
    tool = {candidate.name: candidate for candidate in tool_catalog()}.get(operation)
    handler = _TASK_DISPATCH.get(operation)
    if tool is None or handler is None:
        raise RuntimeError(f"{operation!r} is not a dispatched task")
    structured = handler(arguments)
    wrong = result_issues(tool, structured)
    if wrong:
        raise RuntimeError(
            f"{operation} produced a result its own published outputSchema rejects: "
            + "; ".join(wrong)
        )
    return _task_call_result(structured)


# What each undispatched tool is waiting on. A census in tests/test_mcp.py holds this against
# the dispatch map, so a tool that stops being served, or starts, cannot leave a stale reason
# behind — and one that is neither dispatched nor named here fails the build.
_UNBUILT: dict[str, str] = {}

_UNBUILT_TASKS: dict[str, str] = {}

_TASK_DISPATCH: dict[str, Any] = {
    "run_fea_validation": _run_fea_validation_task,
}

# The operations wired to real code today. A tool absent from this map is refused with the
# reason rather than answered — see the refusal above.
_DISPATCH: dict[str, Any] = {
    "build_combination": _build_combination,
    "build_part": _build_part,
    "compile_spec": _compile_spec,
    "describe_part": _describe_part,
    "export_artifact": _export_artifact,
    "list_context": _list_context,
    "measure_geometry": _measure_geometry,
    "read_cad_file": _read_cad_file,
    "read_scorecard": _read_scorecard,
    "render_viewport": _render_viewport,
    "run_validation": _run_validation,
}


def serve_stdio(stdin: TextIO | None = None, stdout: TextIO | None = None) -> None:
    """Read newline-delimited JSON-RPC from ``stdin`` and write responses to ``stdout``.

    The whole transport: one message per line in, one per line out, flushed each time so a
    client blocked on a read is not waiting on a buffer. Every message is handled by
    :func:`handle_request`, which holds no state. The loop keeps one fact, the protocol
    revision initialize negotiated, and a client that restarts the process initializes again.

    A line that is not JSON is answered with a parse error and the loop continues, because
    a stream is not a session: one client sending rubbish must not take the server down for
    the message after it. A notification produces no line at all, which is what the
    protocol requires and what a client waiting for one response per request depends on.
    """
    source = sys.stdin if stdin is None else stdin
    sink = sys.stdout if stdout is None else stdout
    # The one thing a stream remembers: the protocol revision its initialize settled on, so
    # every later result is shaped the way that client's revision defines one.
    revision = PROTOCOL_REVISION
    for line in source:
        line = line.strip()
        if not line:
            continue
        try:
            request = parse_json(line)
        except ValueError as bad:  # malformed, or nested past what the reader follows
            response: dict[str, Any] | None = _error(None, PARSE_ERROR, f"invalid JSON: {bad}")
        else:
            # No non-object check here any more: `handle_request` holds it, so every
            # transport gets it rather than only the one that remembered to write it.
            response = handle_request(request)
            if (
                isinstance(request, Mapping)
                and request.get("method") == "initialize"
                and isinstance(response, dict)
                and "result" in response
            ):
                revision = response.get("result", {}).get("protocolVersion", revision)
        response = _for_revision(response, revision)
        if response is None:
            continue
        sink.write(json.dumps(response) + "\n")
        sink.flush()


# Third-party modules this server process was started with (`anvilate-mcp --module PATH`).
# Set once at launch from the user's own MCP configuration, never from a tool call: a client
# cannot make the server load code, which is what "enabled by the user, by path" means here.
_MODULES: tuple[Any, ...] = ()


def main(argv: list[str] | None = None) -> None:
    """Run the server on stdio. The console-script and ``python -m`` entry point.

    One option: ``--module PATH`` (repeatable) enables a third-party discipline module, run
    confined and marked unverified-origin; see :mod:`anvilate.thirdparty`. Otherwise there is
    nothing to configure: the surface is the published catalog, the transport is stdin and
    stdout, and there is no state to lose, so a client that restarts the process is in
    exactly the position it was in before.

    A client that stops reading stdout has gone, as surely as one that closes stdin, so the
    broken pipe ends the server the way end of input does: quietly, with status 0. It used
    to print a traceback into the client's log and exit 120. Stdout is pointed at the null
    device first, or the interpreter's own flush at exit raises the same error again.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="anvilate-mcp", description="Anvilate's MCP server.")
    parser.add_argument("--module", action="append", default=[], metavar="PATH")
    parser.add_argument(
        "--out",
        metavar="DIR",
        help="the one folder results are written to (default: ./anvilate-out, or ANVILATE_OUT)",
    )
    parser.add_argument(
        "--context",
        action="append",
        default=[],
        metavar="DIR",
        help="a folder of the user's drawings and models the server may read (repeatable, "
        "read-only; or ANVILATE_CONTEXT). With none, no tool reads a file",
    )
    options = parser.parse_args(argv)
    if options.context:
        from .context import set_context_roots

        missing = [folder for folder in options.context if not Path(folder).is_dir()]
        if missing:
            print(f"anvilate-mcp: --context: not a folder: {', '.join(missing)}", file=sys.stderr)
            raise SystemExit(2)
        set_context_roots(options.context)
    # Decided once, here, by whoever starts the server. No tool takes a destination.
    set_output_folder(options.out or os.environ.get("ANVILATE_OUT") or Path.cwd() / "anvilate-out")
    if options.module:
        from .thirdparty import ThirdPartyModuleError, enable_module

        global _MODULES
        try:
            _MODULES = tuple(enable_module(path) for path in options.module)
        except ThirdPartyModuleError as refused:
            print(f"anvilate-mcp: --module: {refused}", file=sys.stderr)
            raise SystemExit(2) from None
    try:
        serve_stdio()
        sys.stdout.flush()
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess in the tests
    main()
