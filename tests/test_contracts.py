"""The published JSON Schemas are held against the models that generate them.

Two things can go wrong with a published contract, and only one of them is obvious. The
obvious one is drift: a field added to a model and not regenerated, so the artifact
describes a document nobody produces any more. The other one is worse, because it is
invisible from outside: **the artifact changes and its version does not**, so a client
pinned to ``1.1.0`` fetches a different document under the same name with no way to notice.

So the gate is not "the artifact matches the model". It is "the artifact matches the model,
**or** the version moved" — and when it fails it says which of the two the author owes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvilate.contracts import (
    JSON_SCHEMA_DIALECT,
    SCORECARD_SCHEMA_VERSION,
    SPEC_SCHEMA_VERSION,
    _serialize,
    schema_artifacts,
    schema_issues,
    scorecard_json_schema,
    spec_json_schema,
)

_SCHEMAS = Path(__file__).resolve().parent.parent / "docs" / "api" / "schemas"


def _published(name: str) -> dict:
    return json.loads((_SCHEMAS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(schema_artifacts()))
def test_the_published_schema_matches_the_model_that_generates_it(name):
    """The drift half. A hand-edited copy of a live model is a document that is wrong the
    first time somebody adds a field, so the artifact is generated and compared byte for
    byte against the checked-in file."""
    path = _SCHEMAS / name
    assert path.exists(), f"{name} is not published; run anvilate.contracts.write_schemas"
    generated = _serialize(schema_artifacts()[name])
    assert path.read_text(encoding="utf-8") == generated, (
        f"docs/api/schemas/{name} no longer matches the model it was generated from. "
        "Regenerate it with anvilate.contracts.write_schemas — and if the change is not "
        "backward compatible, bump the schema version too, because a client pinned to the "
        "old one will fetch this document under the old name"
    )


@pytest.mark.parametrize("name", sorted(schema_artifacts()))
def test_a_changed_contract_cannot_keep_its_old_version(name):
    """The half that matters. A published schema whose content moved under an unchanged
    ``$id`` is a silent breaking change: the version is the only thing a consumer can pin,
    and it is the only thing this can check without a network."""
    published = _published(name)
    generated = schema_artifacts()[name]
    if published == generated:
        return  # nothing changed; the version is free to stay put
    assert published.get("x-anvilate-version") != generated.get("x-anvilate-version"), (
        f"{name} changed but still declares version "
        f"{generated.get('x-anvilate-version')!r}. Bump it — a client pinned to that "
        "version would fetch a different document under the same identifier and have no "
        "way to know"
    )


@pytest.mark.parametrize("name", sorted(schema_artifacts()))
def test_the_generated_schema_is_self_consistent(name):
    assert schema_issues(schema_artifacts()[name]) == []


def test_the_self_check_catches_a_dangling_reference():
    """A ``$ref`` to a definition that is not present is the failure mode of a schema
    assembled from models — a type referenced but never inlined — and it produces a document
    that looks complete and validates nothing."""
    schema = spec_json_schema()
    schema["$defs"].pop(next(iter(schema["$defs"])))
    assert any("does not define" in issue for issue in schema_issues(schema))


def test_the_self_check_catches_a_version_the_id_does_not_carry():
    schema = scorecard_json_schema()
    schema["x-anvilate-version"] = "9.9.9"
    assert any("does not carry the stated version" in issue for issue in schema_issues(schema))


def test_the_self_check_catches_the_wrong_dialect():
    schema = scorecard_json_schema()
    schema["$schema"] = "http://json-schema.org/draft-07/schema#"
    assert any("declares dialect" in issue for issue in schema_issues(schema))


def test_each_schema_declares_the_dialect_the_tool_contracts_need():
    """2020-12 specifically: it is the dialect the MCP tool-schema contract expects, which
    is the reason these artifacts exist in this form."""
    for schema in schema_artifacts().values():
        assert schema["$schema"] == JSON_SCHEMA_DIALECT


def test_the_scorecard_contract_shows_the_tri_state_to_a_consumer():
    """A client reading this contract must not be able to model the result as a boolean
    without noticing what it is dropping."""
    statuses = _published("scorecard.schema.json")["$defs"]["CheckStatus"]["enum"]
    assert set(statuses) == {"pass", "fail", "over_margin", "not_evaluated"}


def test_the_spec_contract_carries_its_own_version_number():
    published = _published("design-spec.schema.json")
    assert published["x-anvilate-version"] == SPEC_SCHEMA_VERSION
    assert SPEC_SCHEMA_VERSION in published["$id"]
    # And it is the same number a spec file states, not a second one that could disagree.
    assert published["properties"]["anvilate_spec"]["default"] == SPEC_SCHEMA_VERSION


def test_the_scorecard_contract_carries_its_own_version_number():
    published = _published("scorecard.schema.json")
    assert published["x-anvilate-version"] == SCORECARD_SCHEMA_VERSION
    assert SCORECARD_SCHEMA_VERSION in published["$id"]


def test_a_real_scorecard_validates_against_the_published_contract():
    """The contract has to describe what Anvilate actually writes, so this validates a
    scorecard the library produced rather than one shaped to fit.

    Opt-in on ``jsonschema``: it is not a runtime dependency, and a check that cannot run is
    reported as not run.
    """
    jsonschema = pytest.importorskip("jsonschema")
    from anvilate.scorecard import Scorecard, ScorecardEntry

    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("pin bearing", computed=2.7, required=2.0),
            ScorecardEntry.from_safety_factor("plate tear-out", computed=None, required=2.0),
        )
    )
    schema = _published("scorecard.schema.json")
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(card.model_dump(mode="json"))


def test_the_published_schemas_are_valid_2020_12_schemas():
    """The real conformance check, opt-in because ``jsonschema`` is not a runtime
    dependency. Skipped rather than passed when it is absent."""
    jsonschema = pytest.importorskip("jsonschema")
    for name in sorted(schema_artifacts()):
        jsonschema.Draft202012Validator.check_schema(_published(name))
