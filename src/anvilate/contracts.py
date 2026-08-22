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

from .scorecard import Scorecard
from .spec import SCHEMA_VERSION, DesignSpec

__all__ = [
    "JSON_SCHEMA_DIALECT",
    "RELEASED_DIRECTORY",
    "freeze_release",
    "released_path",
    "SCORECARD_SCHEMA_VERSION",
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
SCORECARD_SCHEMA_VERSION = "1.0.0"


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


def schema_artifacts() -> dict[str, dict[str, Any]]:
    """Every published schema, keyed by the file name it is written under."""
    return {
        "design-spec.schema.json": spec_json_schema(),
        "scorecard.schema.json": scorecard_json_schema(),
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
        path.write_text(_serialize(schema), encoding="utf-8")
        written.append(path)
    return written


def released_path(directory: Path, name: str, version: str) -> Path:
    """Where the frozen copy of one version of one schema lives."""
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
        serialized = _serialize(schema)
        if path.exists():
            if path.read_text(encoding="utf-8") != serialized:
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
