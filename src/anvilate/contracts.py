"""The Spec IR and the scorecard as standalone, versioned JSON Schema artifacts.

Anvilate's two load-bearing data contracts are the input — a
:class:`~anvilate.spec.DesignSpec` — and the output — a
:class:`~anvilate.scorecard.Scorecard`. Today they are Python classes, which means anything
outside Python has to trust a description of them. Published as JSON Schema 2020-12 they
become something a CAD add-in, a CI job, or an MCP client can validate against without
importing anvilate at all, and something a tool definition can point at rather than
paraphrase.

The schemas are **generated from the models**, never written by hand, because a hand-written
copy of a live model is a document that is wrong the first time somebody adds a field. The
generated artifacts are checked into ``docs/api/schemas/`` and held against the models by a
gate, in the same shape as this repository's other manifests: a model change that does not
regenerate them fails the build.

The gate has a second half, and it is the one that matters. A contract that changed without
its version moving is the failure this task exists to prevent — a client pinned to
``1.1.0`` would fetch a different document under the same name and have no way to know. So
the check is not "the artifact matches the model" but "the artifact matches the model **or**
the version moved", and the message says which.

``$id`` carries the version. Two schemas with different content and one ``$id`` is the
problem stated; two with the same content and different ``$id`` is merely a wasted release.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ._cli_output import CLI_OUTPUT_SCHEMA_VERSION
from .geometry import (
    ConfirmedCylindricalMate,
    ConfirmedPlanarContact,
    ConfirmedPlanarGap,
    ConfirmedStepInterface,
    CylindricalMateEngagementCheck,
    CylindricalMateFitCheck,
    GeometryMeasurement,
    GeometrySummary,
    PlanarContactAreaCheck,
    PlanarGapClearanceCheck,
    StepInterfaceCandidates,
    ViewportImage,
)
from .scorecard import Scorecard
from .spec import SCHEMA_VERSION, DesignSpec

__all__ = [
    "JSON_SCHEMA_DIALECT",
    "RELEASED_DIRECTORY",
    "freeze_release",
    "released_path",
    "ELEMENT_SCHEMA_INITIAL_VERSION",
    "ELEMENT_SCHEMA_VERSIONS",
    "element_schema_version",
    "SCORECARD_SCHEMA_VERSION",
    "BUNDLE_SCHEMA_VERSION",
    "GEOMETRY_SCHEMA_VERSION",
    "CONFIRMED_INTERFACE_SCHEMA_VERSION",
    "CONFIRMED_CONTACT_SCHEMA_VERSION",
    "CONFIRMED_CYLINDRICAL_MATE_SCHEMA_VERSION",
    "CONFIRMED_PLANAR_GAP_SCHEMA_VERSION",
    "PLANAR_CONTACT_AREA_CHECK_SCHEMA_VERSION",
    "PLANAR_GAP_CLEARANCE_CHECK_SCHEMA_VERSION",
    "CYLINDRICAL_MATE_ENGAGEMENT_CHECK_SCHEMA_VERSION",
    "CYLINDRICAL_MATE_FIT_CHECK_SCHEMA_VERSION",
    "INTERFACE_CANDIDATES_SCHEMA_VERSION",
    "MEASUREMENT_SCHEMA_VERSION",
    "VIEWPORT_SCHEMA_VERSION",
    "bundle_json_schema",
    "geometry_json_schema",
    "confirmed_interface_json_schema",
    "confirmed_contact_json_schema",
    "confirmed_cylindrical_mate_json_schema",
    "confirmed_planar_gap_json_schema",
    "planar_contact_area_check_json_schema",
    "planar_gap_clearance_check_json_schema",
    "cylindrical_mate_engagement_check_json_schema",
    "cylindrical_mate_fit_check_json_schema",
    "interface_candidates_json_schema",
    "measurement_json_schema",
    "viewport_json_schema",
    "element_json_schemas",
    "SPEC_SCHEMA_VERSION",
    "schema_artifacts",
    "schema_issues",
    "scorecard_json_schema",
    "spec_json_schema",
    "write_schemas",
]

# The dialect the MCP 2026-07-28 protocol expects for tool input and output schemas, which
# is the reason these artifacts exist in this form rather than as an ad-hoc dump.
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

_BASE_ID = "https://anvilate.dev/schemas"

# Where a version's content is frozen once and never regenerated. See `freeze_release`.
RELEASED_DIRECTORY = "released"

# The Spec IR carries its own version already — it is the number a spec file states in its
# `anvilate_spec` field — so the published artifact uses it rather than inventing a second
# one that could disagree.
SPEC_SCHEMA_VERSION = SCHEMA_VERSION

# The scorecard had no versioned contract before it had a published one. Bump this when the
# generated schema changes; the gate in tests/test_contracts.py refuses a changed schema
# under an unchanged version and says so by name.
SCORECARD_SCHEMA_VERSION = "1.9.0"

# The evidence bundle, which the `export_artifact` MCP tool serves and `anvilate export`
# prints. It had no contract at all: the tool published its entire output as
# `{"type": "object"}`, so the one thing it exists to hand a client was the one thing its
# schema said nothing about. Same rule as the two above — bump on a change to the generated
# document, and the gate refuses a changed schema under an unchanged version.
BUNDLE_SCHEMA_VERSION = "1.16.0"

# The kernel-independent geometry summary shared by CLI and MCP build results.
GEOMETRY_SCHEMA_VERSION = "1.2.0"

# Planar faces and through-hole patterns measured from imported mating STEP solids.
INTERFACE_CANDIDATES_SCHEMA_VERSION = "1.11.0"

# One measured candidate accepted by a named person as an InterfaceContract.
CONFIRMED_INTERFACE_SCHEMA_VERSION = "1.4.0"

# One measured planar contact accepted by a named person without an invented hole pattern.
CONFIRMED_CONTACT_SCHEMA_VERSION = "1.0.0"

# One measured cylindrical mate accepted by a named person without a fit verdict.
CONFIRMED_CYLINDRICAL_MATE_SCHEMA_VERSION = "1.0.0"

# One measured planar gap accepted by a named person without an allowable clearance.
CONFIRMED_PLANAR_GAP_SCHEMA_VERSION = "1.0.0"

# One confirmed planar gap checked against a caller-supplied cited band.
PLANAR_GAP_CLEARANCE_CHECK_SCHEMA_VERSION = "1.0.0"

# One confirmed planar contact checked against a caller-supplied cited minimum area.
PLANAR_CONTACT_AREA_CHECK_SCHEMA_VERSION = "1.0.0"

# One confirmed cylindrical mate checked against an explicit ISO 286 fit.
CYLINDRICAL_MATE_FIT_CHECK_SCHEMA_VERSION = "1.0.0"

# One confirmed cylindrical mate checked against a caller-supplied cited minimum engagement.
CYLINDRICAL_MATE_ENGAGEMENT_CHECK_SCHEMA_VERSION = "1.0.0"

# The self-contained SVG image document returned by ``render_viewport``.
VIEWPORT_SCHEMA_VERSION = "1.0.0"

# A scalar read directly from a built B-Rep by ``measure_geometry``.
MEASUREMENT_SCHEMA_VERSION = "1.0.0"


def _artifact(model: type, *, name: str, version: str, description: str) -> dict[str, Any]:
    """One model as a self-describing JSON Schema 2020-12 document.

    ``mode="serialization"`` because the published contract is what Anvilate *writes*: a
    validation schema built from the input side would describe the coercions pydantic
    accepts rather than the document a consumer will actually receive.
    """
    schema = model.model_json_schema(mode="serialization", ref_template="#/$defs/{model}")
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": f"{_BASE_ID}/{name}/{version}.json",
        "title": schema.pop("title", name),
        # Both are popped, not just the title. `**schema` re-introduced whatever pydantic
        # put there, so the curated sentence was dead code and consumers received the
        # class's raw docstring — unrendered reST markup, and without the two things the
        # curated text exists to say: the plain-language tri-state warning and the line
        # naming which model generated the document.
        "description": description,
        "x-anvilate-version": version,
        **{key: value for key, value in schema.items() if key != "description"},
    }


def spec_json_schema() -> dict[str, Any]:
    """The Design Spec IR as a JSON Schema 2020-12 document."""
    return _artifact(
        DesignSpec,
        name="design-spec",
        version=SPEC_SCHEMA_VERSION,
        description=(
            "Anvilate Design Spec IR: the typed, versioned description of a part that the "
            "screening pipeline consumes. Generated from anvilate.spec.DesignSpec."
        ),
    )


def geometry_json_schema() -> dict[str, Any]:
    """The serializable identity and kernel checks for one built solid."""
    return _artifact(
        GeometrySummary,
        name="geometry-summary",
        version=GEOMETRY_SCHEMA_VERSION,
        description=(
            "Anvilate geometry summary: the audited pattern, declared dimensions, semantic "
            "face tags, and kernel-checked volume for one valid solid. Generated from "
            "anvilate.geometry.GeometrySummary."
        ),
    )


def viewport_json_schema() -> dict[str, Any]:
    """The deterministic viewport image and its integrity metadata."""
    return _artifact(
        ViewportImage,
        name="viewport-image",
        version=VIEWPORT_SCHEMA_VERSION,
        description=(
            "Anvilate viewport image: one deterministic SVG rendering with its view, pixel "
            "dimensions, exact media type, SHA-256 digest, and base64 payload. Generated "
            "from anvilate.geometry.ViewportImage."
        ),
    )


def interface_candidates_json_schema() -> dict[str, Any]:
    """The measured, unconfirmed interface candidates from one mating STEP."""
    return _artifact(
        StepInterfaceCandidates,
        name="step-interface-candidates",
        version=INTERFACE_CANDIDATES_SCHEMA_VERSION,
        description=(
            "Anvilate STEP interface candidates: planar mating faces and regular "
            "equal-diameter through-hole patterns and concentric locating features measured "
            "from imported solids, with measured solid summaries, exact coplanar contacts, "
            "projected planar gaps, coaxial cylindrical mating candidates, and a scored "
            "positive-volume solid-interference check on multi-solid inputs. "
            "Candidates require user confirmation before becoming interface contracts. "
            "Generated from anvilate.geometry.StepInterfaceCandidates."
        ),
    )


def confirmed_interface_json_schema() -> dict[str, Any]:
    """One confirmed STEP candidate and the InterfaceContract created from it."""
    return _artifact(
        ConfirmedStepInterface,
        name="confirmed-step-interface",
        version=CONFIRMED_INTERFACE_SCHEMA_VERSION,
        description=(
            "Anvilate confirmed STEP interface: the source digest and exact measured "
            "candidate IDs, the named person who accepted them, and the InterfaceContract "
            "created for downstream design. Generated from "
            "anvilate.geometry.ConfirmedStepInterface."
        ),
    )


def confirmed_contact_json_schema() -> dict[str, Any]:
    """One exact planar contact accepted by a named person."""
    return _artifact(
        ConfirmedPlanarContact,
        name="confirmed-planar-contact",
        version=CONFIRMED_CONTACT_SCHEMA_VERSION,
        description=(
            "Anvilate confirmed planar contact: one exact kernel-measured contact candidate, "
            "its source digest and solid/face endpoints, a semantic name, overlap area, and "
            "the named person who accepted it. Generated from "
            "anvilate.geometry.ConfirmedPlanarContact."
        ),
    )


def confirmed_cylindrical_mate_json_schema() -> dict[str, Any]:
    """One exact cylindrical mate accepted by a named person."""
    return _artifact(
        ConfirmedCylindricalMate,
        name="confirmed-cylindrical-mate",
        version=CONFIRMED_CYLINDRICAL_MATE_SCHEMA_VERSION,
        description=(
            "Anvilate confirmed cylindrical mate: one exact measured bore/shaft candidate, "
            "its source digest, endpoints, signed clearance, axial engagement, semantic name, "
            "and the named person who accepted it without a fit verdict. Generated from "
            "anvilate.geometry.ConfirmedCylindricalMate."
        ),
    )


def confirmed_planar_gap_json_schema() -> dict[str, Any]:
    """One exact planar gap accepted by a named person."""
    return _artifact(
        ConfirmedPlanarGap,
        name="confirmed-planar-gap",
        version=CONFIRMED_PLANAR_GAP_SCHEMA_VERSION,
        description=(
            "Anvilate confirmed planar gap: one exact projected-overlap candidate, its "
            "source digest, solid/face endpoints, separation, overlap, direction, semantic "
            "name, and named confirmer without an allowable-clearance verdict. Generated "
            "from anvilate.geometry.ConfirmedPlanarGap."
        ),
    )


def planar_gap_clearance_check_json_schema() -> dict[str, Any]:
    """One confirmed planar gap checked against a cited clearance band."""
    return _artifact(
        PlanarGapClearanceCheck,
        name="planar-gap-clearance-check",
        version=PLANAR_GAP_CLEARANCE_CHECK_SCHEMA_VERSION,
        description=(
            "Anvilate planar gap clearance check: one confirmed gap checked against "
            "caller-supplied minimum and maximum separations, with margins, pass/fail "
            "status, and the requirement citation. Generated from "
            "anvilate.geometry.PlanarGapClearanceCheck."
        ),
    )


def planar_contact_area_check_json_schema() -> dict[str, Any]:
    """One confirmed planar contact checked against a cited minimum overlap area."""
    return _artifact(
        PlanarContactAreaCheck,
        name="planar-contact-area-check",
        version=PLANAR_CONTACT_AREA_CHECK_SCHEMA_VERSION,
        description=(
            "Anvilate planar contact area check: one confirmed contact checked against a "
            "caller-supplied minimum overlap area, with margin, pass/fail status, and the "
            "requirement citation. Generated from "
            "anvilate.geometry.PlanarContactAreaCheck."
        ),
    )


def cylindrical_mate_fit_check_json_schema() -> dict[str, Any]:
    """One confirmed cylindrical mate checked against an explicit ISO 286 fit."""
    return _artifact(
        CylindricalMateFitCheck,
        name="cylindrical-mate-fit-check",
        version=CYLINDRICAL_MATE_FIT_CHECK_SCHEMA_VERSION,
        description=(
            "Anvilate cylindrical mate fit check: a confirmed measured bore/shaft pair "
            "checked against caller-supplied ISO 286 basic size and designations, with "
            "feature limits, per-feature verdicts, clearance range, and citation. Generated "
            "from anvilate.geometry.CylindricalMateFitCheck."
        ),
    )


def cylindrical_mate_engagement_check_json_schema() -> dict[str, Any]:
    """One confirmed cylindrical mate checked against a cited minimum engagement."""
    return _artifact(
        CylindricalMateEngagementCheck,
        name="cylindrical-mate-engagement-check",
        version=CYLINDRICAL_MATE_ENGAGEMENT_CHECK_SCHEMA_VERSION,
        description=(
            "Anvilate cylindrical mate engagement check: a confirmed measured bore/shaft "
            "pair checked against a caller-supplied minimum axial engagement, with margin, "
            "pass/fail status, and the requirement citation. Generated from "
            "anvilate.geometry.CylindricalMateEngagementCheck."
        ),
    )


def measurement_json_schema() -> dict[str, Any]:
    """A typed scalar inspection of built geometry."""
    return _artifact(
        GeometryMeasurement,
        name="geometry-measurement",
        version=MEASUREMENT_SCHEMA_VERSION,
        description=(
            "Anvilate geometry measurement: one query answered from the regenerated B-Rep, "
            "with its value, unit, and semantic feature. Generated from "
            "anvilate.geometry.GeometryMeasurement."
        ),
    )


def scorecard_json_schema() -> dict[str, Any]:
    """The scorecard as a JSON Schema 2020-12 document.

    The tri-state is in the enumeration, where a consumer can see it: ``not_evaluated`` is a
    value of ``CheckStatus`` alongside ``pass`` and ``fail``, so a client reading this
    contract cannot model the result as a boolean without noticing what it is dropping.
    """
    return _artifact(
        Scorecard,
        name="scorecard",
        version=SCORECARD_SCHEMA_VERSION,
        description=(
            "Anvilate scorecard: one typed result per validation check, with a rolled-up "
            "status. A check that could not run reports not_evaluated, which is not a pass. "
            "Generated from anvilate.scorecard.Scorecard."
        ),
    )


def bundle_json_schema() -> dict[str, Any]:
    """The exported evidence bundle as a JSON Schema 2020-12 document.

    Generated from :class:`anvilate.bundle.BundleDocument`, which describes the document
    :meth:`anvilate.bundle.BundleSections.to_document_dict` emits. That model does not build
    the document — its own docstring says why — so the thing that makes this schema true of
    the real bundle is the gate that validates every document the library builds against it,
    rather than a shared code path.
    """
    from .bundle import BundleDocument

    return _artifact(
        BundleDocument,
        name="evidence-bundle",
        version=BUNDLE_SCHEMA_VERSION,
        description=(
            "Anvilate evidence bundle: every screening layer's contribution for one part, "
            "with one rolled-up status, the scorecard, and the spec the verdicts were "
            "computed from. A layer that never ran is an absent key, not a null one — the "
            "two are different facts and the bundle refuses to collapse them. Carries the "
            "screening disclaimer unconditionally. Generated from anvilate.bundle."
            "BundleDocument."
        ),
    )


# Where the pack elements' own schemas are published, relative to the schema directory.
ELEMENTS_DIRECTORY = "elements"

# The element schemas move with the packs rather than with the Spec IR, which is the whole
# point of the tag: a new pack element must not bump `SPEC_SCHEMA_VERSION`. And they move
# **one at a time**. A single shared number would have meant that changing one element's
# fields re-issued all twenty-odd `$id`s, so a client pinned to `bolted_connection/1.0.0`
# would be told its contract had moved because a pump duty gained a field.
#
# The version an element publishes at the day it first ships. A pack ships an element by
# existing -- the registry is derived from the packs -- so a new element must not require an
# edit here to be publishable, and this is what it gets until somebody bumps it.
ELEMENT_SCHEMA_INITIAL_VERSION = "1.0.0"

# Elements whose schema has moved since, keyed by the same tag a document writes. Add an
# entry to bump one element; every other element's `$id` is untouched by that edit. An entry
# naming a tag no pack registers is refused by the gate in tests/test_contracts.py -- a
# renamed element must not leave a live version pin behind pointing at nothing.
ELEMENT_SCHEMA_VERSIONS: dict[str, str] = {
    # All twenty-four moved together at 1.1.0, and for one reason: the element models now
    # forbid unknown fields, so each published schema closes `additionalProperties`. That is a
    # real change to what the contract accepts and it is *stricter*, which is the direction a
    # version has to move for — a client sending a property this library was quietly dropping
    # is refused by the schema now instead of screened without it.
    #
    # What it fixes is a silent green in the document front door. `element_params` is an
    # untyped map, so a misspelled OPTIONAL parameter reached the pack model and was ignored:
    # a beam declaring `deflection_limt` was screened with no deflection limit at all, the
    # deflection check vanished from the card, and the card still said PASS. A check that was
    # asked for and did not run, reported as a pass.
    #
    # A single shared number would have re-issued every element on any one element's change,
    # which is what this map exists to avoid. They share a version here because they share a
    # cause; the next bump will be one line.
    "base_plate": "1.1.0",
    "beam_column_member": "1.1.0",
    "beam_member": "1.1.0",
    "bolted_connection": "1.1.0",
    "column_member": "1.1.0",
    "concrete_bearing": "1.1.0",
    "cover_plate": "1.1.0",
    "driven_pile": "1.1.0",
    "feeder": "1.1.0",
    "gusset_plate": "1.1.0",
    "infinite_slope": "1.1.0",
    "lifting_lug": "1.1.0",
    "lighting_installation": "1.1.0",
    "masonry_wall": "1.1.0",
    "pipe_run": "1.1.0",
    "pump_duty": "1.1.0",
    "retaining_wall": "1.1.0",
    "shallow_footing": "1.1.0",
    "shear_plate": "1.1.0",
    "structure": "1.1.0",
    "tension_member": "1.1.0",
    "ventilation_zone": "1.1.0",
    "welded_connection": "1.1.0",
    "worker_noise_exposure": "1.1.0",
}


def element_schema_version(tag: str) -> str:
    """The published schema version for one element tag."""
    return ELEMENT_SCHEMA_VERSIONS.get(tag, ELEMENT_SCHEMA_INITIAL_VERSION)


def element_json_schemas() -> dict[str, dict[str, Any]]:
    """Each pack element a spec can name, as a JSON Schema document keyed by its tag.

    `DesignSpec.element_params` is an untyped map on purpose -- it is what keeps `spec-ir`
    from depending on twenty-odd packs -- and what that trades away is a published contract
    that describes a complete document. These are the other half of that trade: the element's
    own fields, published beside the spec schema and addressed by the same tag a document
    writes, so a client can still validate what it is about to send without the Spec IR
    having to know what a lifting lug is.

    Generated from the same registry the screen resolves through, so an element that ships
    is an element that is published.
    """
    from .screening import element_registry

    return {
        tag: _artifact(
            model,
            name=f"{ELEMENTS_DIRECTORY}/{tag}",
            version=element_schema_version(tag),
            description=(
                f"Anvilate pack element {tag!r}: the fields a Design Spec puts in "
                f"`element_params` when it declares `element_type: {tag}`. Generated from "
                f"{model.__module__}.{model.__name__}."
            ),
        )
        for tag, (model, _screen) in sorted(element_registry().items())
    }


def schema_artifacts() -> dict[str, dict[str, Any]]:
    """Every published schema, keyed by the file name it is written under."""
    return {
        "design-spec.schema.json": spec_json_schema(),
        "scorecard.schema.json": scorecard_json_schema(),
        "evidence-bundle.schema.json": bundle_json_schema(),
        "geometry-summary.schema.json": geometry_json_schema(),
        "step-interface-candidates.schema.json": interface_candidates_json_schema(),
        "confirmed-step-interface.schema.json": confirmed_interface_json_schema(),
        "confirmed-planar-contact.schema.json": confirmed_contact_json_schema(),
        "confirmed-cylindrical-mate.schema.json": confirmed_cylindrical_mate_json_schema(),
        "confirmed-planar-gap.schema.json": confirmed_planar_gap_json_schema(),
        "planar-contact-area-check.schema.json": planar_contact_area_check_json_schema(),
        "planar-gap-clearance-check.schema.json": planar_gap_clearance_check_json_schema(),
        "cylindrical-mate-engagement-check.schema.json": (
            cylindrical_mate_engagement_check_json_schema()
        ),
        "cylindrical-mate-fit-check.schema.json": cylindrical_mate_fit_check_json_schema(),
        "viewport-image.schema.json": viewport_json_schema(),
        "geometry-measurement.schema.json": measurement_json_schema(),
        "cli-output.schema.json": cli_output_json_schema(),
        **{
            f"{ELEMENTS_DIRECTORY}/{tag}.schema.json": schema
            for tag, schema in element_json_schemas().items()
        },
    }


def cli_output_json_schema() -> dict[str, Any]:
    """Every completed ``anvilate --format json`` result as one union contract."""
    from ._cli_output import CLI_OUTPUT_SCHEMA_ID
    from ._cli_output import cli_output_json_schema as generated

    schema = generated()
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": CLI_OUTPUT_SCHEMA_ID,
        "title": "Anvilate CLI output",
        "description": (
            "Every completed machine-readable Anvilate CLI result. Generated from "
            "anvilate._cli_output.CliOutput."
        ),
        "x-anvilate-version": CLI_OUTPUT_SCHEMA_VERSION,
        **{key: value for key, value in schema.items() if key not in {"title"}},
    }


def _serialize(schema: dict[str, Any]) -> str:
    """A schema as the bytes that get checked in.

    Sorted keys and a trailing newline, so regenerating an unchanged model produces a
    byte-identical file and the gate compares content rather than dictionary order.
    """
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_schemas(directory: Path) -> list[Path]:
    """Write every published schema into ``directory``, returning the paths written."""
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, schema in schema_artifacts().items():
        path = directory / name
        # The element schemas live in a subdirectory, so the parent is made rather than
        # assumed: a writer that assumed it would fail on a fresh checkout only.
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_serialize(schema), encoding="utf-8")
        written.append(path)
    return written


def released_path(directory: Path, name: str, version: str) -> Path:
    """Where the frozen copy of one version of one schema lives.

    ``name`` may carry a subdirectory — the pack elements publish under ``elements/`` — and
    the frozen tree mirrors it rather than flattening, so two elements could not collide on
    a shared basename.
    """
    return directory / RELEASED_DIRECTORY / f"{name.removesuffix('.schema.json')}-{version}.json"


def freeze_release(directory: Path) -> list[Path]:
    """Freeze each schema's current version, and refuse to change a version already frozen.

    This is the half that makes the version gate mean anything. Comparing the checked-in
    artifact against a freshly generated one cannot detect a version that should have moved:
    that comparison is *already* the drift check, and the moment an author does what the
    drift failure tells them to do — regenerate — both halves go green with the version
    untouched. A breaking change then ships under the old number.

    So a released version's content is frozen once, in its own file, and never regenerated.
    Changing what a version means requires deleting a frozen file, which is a deliberate act
    visible in a diff rather than the natural consequence of following an error message.
    """
    written = []
    for name, schema in schema_artifacts().items():
        version = str(schema["x-anvilate-version"])
        path = released_path(directory, name, version)
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = _serialize(schema)
        if path.exists():
            try:
                frozen: str | None = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # A frozen artifact that will not decode is a frozen artifact whose content
                # cannot be confirmed to be this one, which is the same refusal — and this is
                # the one place the answer to it must not be a traceback out of a function
                # documented to raise `ValueError`.
                frozen = None
            if frozen != serialized:
                raise ValueError(
                    f"{name} version {version} is already frozen with different content. "
                    "Bump the schema version instead — a released version whose meaning "
                    "changes is a breaking change no client can see"
                )
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialized, encoding="utf-8")
        written.append(path)
    return written


def _collect_refs(node: Any, found: list[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            found.append(ref)
        for value in node.values():
            _collect_refs(value, found)
    elif isinstance(node, list):
        for value in node:
            _collect_refs(value, found)


def schema_issues(schema: dict[str, Any]) -> list[str]:
    """Structural problems in a generated schema, as a list of complaints.

    The checks that need no validator library: the dialect and identifier are declared, the
    identifier carries the version the document states, and every internal ``$ref`` resolves
    to a definition that is present. A dangling ``$ref`` is the failure mode of a schema
    assembled from models — a type referenced but not inlined — and it produces a document
    that looks complete and validates nothing.

    An empty list means the document is self-consistent, not that it is a valid 2020-12
    schema; that needs the meta-schema and a validator, which the opt-in test supplies.
    """
    if not isinstance(schema, dict):
        # A schema is read back from `docs/api/schemas/` to be checked, so the argument comes
        # from a file. `'list' object has no attribute 'get'` is not a complaint about a
        # schema, which is what this function returns.
        return [f"a schema is a mapping; got {type(schema).__name__}"]
    issues: list[str] = []
    if schema.get("$schema") != JSON_SCHEMA_DIALECT:
        issues.append(f"the schema declares dialect {schema.get('$schema')!r}")
    identifier = schema.get("$id")
    version = schema.get("x-anvilate-version")
    if not isinstance(identifier, str) or not identifier.startswith(_BASE_ID):
        issues.append(f"the schema has no anvilate $id; got {identifier!r}")
    elif not isinstance(version, str) or f"/{version}.json" not in identifier:
        issues.append(f"$id {identifier!r} does not carry the stated version {version!r}")

    definitions = set(schema.get("$defs", {}))
    refs: list[str] = []
    _collect_refs(schema, refs)
    for ref in sorted(set(refs)):
        if not ref.startswith("#/$defs/"):
            issues.append(f"the schema references {ref!r}, which is not an internal $def")
        elif ref.removeprefix("#/$defs/") not in definitions:
            issues.append(f"the schema references {ref!r}, which it does not define")
    return issues
