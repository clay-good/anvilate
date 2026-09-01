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
    freeze_release,
    released_path,
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
def test_a_released_version_still_means_what_it_meant(name):
    """The half that matters, and the half the first version of this test did not do.

    It compared the checked-in artifact against a freshly generated one — which is *already*
    the drift check above, so the version assertion was only reachable from a state that was
    red for another reason. The moment an author did what the drift failure told them to do
    (regenerate), both halves went green with the version untouched, and a required property
    deleted from the contract shipped under the same `$id`. An audit demonstrated exactly
    that.

    So the comparison is against content frozen when the version was cut, in its own file,
    never regenerated. Changing what a released version means now requires deleting that
    file — a deliberate act visible in a diff, rather than the natural consequence of
    following an error message.
    """
    schema = schema_artifacts()[name]
    version = str(schema["x-anvilate-version"])
    frozen = released_path(_SCHEMAS, name, version)
    assert frozen.exists(), (
        f"{name} declares version {version} with no frozen release for it. Run "
        "anvilate.contracts.freeze_release to cut it — a version nobody froze is a version "
        "whose meaning can change without anyone noticing"
    )
    assert json.loads(frozen.read_text(encoding="utf-8")) == schema, (
        f"{name} version {version} no longer matches what was released under that number. "
        "Bump the version and freeze the new one; a client pinned to this version would "
        "fetch different content under the same identifier and have no way to know"
    )


def test_the_release_freeze_refuses_to_launder_a_change(tmp_path):
    """`freeze_release` must not be usable to overwrite a frozen version, or the gate above
    has the same hole one function call further away."""
    freeze_release(tmp_path)
    name, schema = next(iter(schema_artifacts().items()))
    frozen = released_path(tmp_path, name, str(schema["x-anvilate-version"]))
    frozen.write_text(frozen.read_text(encoding="utf-8").replace('"type"', '"kind"', 1), "utf-8")
    with pytest.raises(ValueError, match="already frozen with different content"):
        freeze_release(tmp_path)


def test_the_version_gate_catches_a_silently_changed_contract(tmp_path):
    """The exact sequence that defeated the first version of this gate: change the schema,
    regenerate the artifact as the drift failure instructs, leave the version alone.

    The old comparison — checked-in artifact against freshly generated — went green at that
    point, because regenerating is what makes those two agree. The frozen release does not
    move, so it does not.
    """
    freeze_release(tmp_path)
    name, schema = next(iter(schema_artifacts().items()))
    version = str(schema["x-anvilate-version"])
    frozen = json.loads(released_path(tmp_path, name, version).read_text(encoding="utf-8"))

    # A property removed from the contract — the breaking change a pinned client cannot see.
    changed = dict(schema)
    properties = dict(schema["properties"])
    properties.pop(next(iter(properties)))
    changed["properties"] = properties

    assert frozen == schema, "the freeze must record what is generated today"
    assert frozen != changed, (
        "the frozen release agreed with a contract that had a property removed, so the "
        "gate would not fire on the change it exists to catch"
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


@pytest.mark.parametrize("name", sorted(schema_artifacts()))
def test_the_curated_description_is_the_one_that_ships(name):
    """`**schema` re-introduced pydantic's own key, so the curated sentence was dead code
    and consumers received the class docstring instead — unrendered reST markup, and without
    the two things the curated text exists to say."""
    description = schema_artifacts()[name]["description"]
    assert "Generated from anvilate." in description
    assert ":attr:" not in description and "``" not in description


def test_a_real_design_spec_validates_against_its_published_contract():
    """The contract has to describe what Anvilate actually writes. A scorecard round trip
    was pinned; the spec side was only ever checked by an auditor, which is not a gate."""
    jsonschema = pytest.importorskip("jsonschema")
    from anvilate.spec import (
        AcceptanceCriteria,
        Constraints,
        DesignSpec,
        LoadCase,
        LoadKind,
        Manufacturing,
        ManufacturingProcess,
        MaterialRef,
        Provenanced,
        StandardComponentInterface,
        ValidationTier,
    )
    from anvilate.units import Quantity, UnitSystem

    spec = DesignSpec(
        name="nema23_bracket",
        description="Aluminum bracket mounting a NEMA 23 stepper to a 4040 extrusion.",
        units=Provenanced.stated(UnitSystem.SI),
        material=MaterialRef(ref="AA-6061-T6"),
        manufacturing=Manufacturing(
            process=ManufacturingProcess.CNC_MILLING, tolerance_class="medium"
        ),
        interfaces=[StandardComponentInterface(ref="NEMA23", tag="motor_pilot_bore")],
        load_cases=[
            LoadCase(
                name="cantilevered_motor",
                kind=LoadKind.REMOTE_MASS,
                applied_to="motor_pilot_bore",
                remote_mass=Quantity.parse("1.1 kg"),
            )
        ],
        constraints=Constraints(min_safety_factor=Provenanced.stated(2.0)),
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
    )
    schema = _published("design-spec.schema.json")
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(spec.model_dump(mode="json"))


def test_disambiguation_is_not_quadratic_in_the_size_of_a_duplicate_group():
    """A structural card merges every member into one scorecard, so thousands of one name is
    the shape this has to survive. Restarting the probe at 1 per name took six seconds for
    eight thousand."""
    import time

    from anvilate.export.qif import _unique_names

    start = time.perf_counter()
    unique = _unique_names(["B1 bending"] * 8000)
    elapsed = time.perf_counter() - start
    assert len(set(unique)) == 8000
    assert elapsed < 1.0, f"disambiguating 8000 identical names took {elapsed:.1f}s"


def test_every_element_a_spec_can_name_has_a_published_schema():
    """The other half of the tag-and-map trade, held in both directions.

    `DesignSpec.element_params` is an untyped map so that `spec-ir` need not depend on
    twenty-odd packs, and what that costs is a published contract that no longer describes a
    complete document. These schemas are what pays it back — the element's own fields,
    addressed by the same tag a document writes.

    So the registry and the published set must be the same set. An element with no schema is
    a document a client cannot validate before sending; a schema with no element is a tag
    that resolves to nothing.
    """
    from anvilate.contracts import ELEMENTS_DIRECTORY, element_json_schemas
    from anvilate.screening import element_registry

    registry, published = element_registry(), element_json_schemas()
    assert len(registry) > 20, f"only {len(registry)} elements are registered"
    assert set(registry) == set(published), (
        f"unpublished: {sorted(set(registry) - set(published))}; "
        f"published but unreachable: {sorted(set(published) - set(registry))}"
    )

    on_disk = {
        path.stem.removesuffix(".schema")
        for path in (_SCHEMAS / ELEMENTS_DIRECTORY).glob("*.schema.json")
    }
    assert on_disk == set(registry), (
        f"the checked-in element schemas and the registry disagree: "
        f"{sorted(on_disk ^ set(registry))}"
    )


def test_an_element_schema_describes_the_fields_its_own_screen_requires():
    """Generated from the model the screen takes, so the schema and the thing it validates
    cannot be two different ideas of an element. Held on the required set, which is the half
    a client actually needs: a document missing one of these does not screen."""
    import jsonschema

    from anvilate.contracts import element_json_schemas
    from anvilate.screening import element_registry

    registry = element_registry()
    for tag, schema in sorted(element_json_schemas().items()):
        jsonschema.Draft202012Validator.check_schema(schema)
        model = registry[tag][0]
        required = {name for name, field in model.model_fields.items() if field.is_required()}
        assert set(schema.get("required", ())) == required, tag
        assert schema["$id"].endswith(".json") and f"/{tag}/" in schema["$id"], tag


def test_the_lifting_lug_schema_accepts_the_document_the_docs_page_shows():
    """The end of the trade, demonstrated rather than asserted: a client that fetches the
    element schema by tag can validate its `element_params` before sending them."""
    import re

    import jsonschema
    import yaml

    from anvilate.contracts import element_json_schemas

    page = (_SCHEMAS.parent.parent / "spec-screening.md").read_text(encoding="utf-8")
    block = re.search(r"```yaml\n(element_type:.*?)```", page, re.S)
    assert block is not None, "the element block on spec-screening.md has moved"
    shown = yaml.safe_load(block.group(1))

    schema = element_json_schemas()[shown["element_type"]]
    validator = jsonschema.Draft202012Validator(schema)
    params = json.loads(json.dumps(shown["element_params"]))
    assert not list(validator.iter_errors(params)), [
        e.message for e in validator.iter_errors(params)
    ]
    # And a document missing a required field is refused by the schema, not only by the pack.
    del params["hole_diameter"]
    assert list(validator.iter_errors(params))
