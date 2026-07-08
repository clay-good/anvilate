"""Tests for the materials database, tracking the standards-data spec scenarios."""

from __future__ import annotations

import pytest

from anvilate.standards import (
    Material,
    MaterialPropertyUnavailable,
    MaterialsDatabase,
    PropertyCitation,
    UnknownMaterialError,
    default_materials_db,
)
from anvilate.standards.materials import _load_bundle


@pytest.fixture(scope="module")
def db() -> MaterialsDatabase:
    return default_materials_db()


def test_seed_covers_golden_path_materials(db: MaterialsDatabase) -> None:
    # The seed must at least cover the identifiers the reference resolver names.
    assert set(db.known_materials()) >= {
        "AA-6061-T6",
        "AA-7075-T6",
        "ASTM-A36",
        "ASTM-A992",
        "SS-304",
    }


def test_yield_strength_carries_temper_and_citation(db: MaterialsDatabase) -> None:
    # Scenario: yield strength with temper — the T6 value with its citation.
    prop = db.get("AA-6061-T6").yield_strength
    assert prop.quantity.to("MPa").magnitude == pytest.approx(276.0)
    assert "T6" in prop.citation.condition
    assert prop.citation.source


def test_every_property_is_provenance_tagged(db: MaterialsDatabase) -> None:
    # Scenario: provenance in evidence bundle — each property has a citation with
    # a source and a redistribution-safe license.
    for material_id in db.known_materials():
        citations = db.get(material_id).citations()
        assert citations, material_id
        for name, cite in citations.items():
            assert cite.source, (material_id, name)
            assert cite.license, (material_id, name)
            assert cite.retrieved, (material_id, name)


def test_missing_property_blocks_the_check(db: MaterialsDatabase) -> None:
    # Scenario: missing property blocks the check — require() raises rather than
    # substituting an unsourced value.
    ss304 = db.get("SS-304")
    assert ss304.endurance_limit is None
    with pytest.raises(MaterialPropertyUnavailable):
        ss304.require("endurance_limit")


def test_estimated_property_is_labeled_with_method(db: MaterialsDatabase) -> None:
    # Scenario: derived fatigue parameters are labeled as estimates.
    cite = db.get("ASTM-A36").endurance_limit.citation
    assert cite.estimated is True
    assert cite.method


def test_estimated_property_must_name_method() -> None:
    with pytest.raises(ValueError, match="estimation method"):
        PropertyCitation(
            source="x",
            condition="y",
            license="z",
            retrieved="2026-07-08",
            estimated=True,
        )


def test_unknown_material_suggests_near_miss(db: MaterialsDatabase) -> None:
    with pytest.raises(UnknownMaterialError) as excinfo:
        db.get("AA-6061")
    assert "AA-6061-T6" in excinfo.value.suggestions


def test_wrong_dimension_property_is_rejected() -> None:
    # A modulus given a non-pressure quantity must fail validation, naming the
    # field and the dimension mismatch — the units layer's guarantee, applied to
    # material records.
    record = {
        "id": "BAD-1",
        "name": "bad",
        "category": "test",
        "elastic_modulus": {"quantity": {"magnitude": 5, "unit": "kg"}, "citation": _cite()},
        "poisson_ratio": {"value": 0.3, "citation": _cite()},
        "density": {"quantity": {"magnitude": 7.85, "unit": "g/cm**3"}, "citation": _cite()},
        "yield_strength": {"quantity": {"magnitude": 250, "unit": "MPa"}, "citation": _cite()},
        "ultimate_strength": {"quantity": {"magnitude": 400, "unit": "MPa"}, "citation": _cite()},
    }
    with pytest.raises(Exception) as exc:  # pydantic wraps the DimensionError
        Material.model_validate(record)
    msg = str(exc.value)
    assert "elastic_modulus" in msg
    assert "pressure" in msg


def test_dataset_license_fills_property_citations() -> None:
    # The dataset states shared license/retrieved once; each property inherits it.
    text = """
dataset:
  name: t
  version: "0"
  license: "TEST-LICENSE"
  retrieved: "2026-01-01"
materials:
  X-1:
    name: X
    category: test
    elastic_modulus:
      quantity: {magnitude: 200, unit: GPa}
      citation: {source: s, condition: c}
    poisson_ratio:
      value: 0.3
      citation: {source: s, condition: c}
    density:
      quantity: {magnitude: 7.85, unit: g/cm**3}
      citation: {source: s, condition: c}
    yield_strength:
      quantity: {magnitude: 250, unit: MPa}
      citation: {source: s, condition: c}
    ultimate_strength:
      quantity: {magnitude: 400, unit: MPa}
      citation: {source: s, condition: c, license: "OVERRIDE"}
"""
    mats = _load_bundle(text)
    m = mats["X-1"]
    assert m.elastic_modulus.citation.license == "TEST-LICENSE"
    assert m.elastic_modulus.citation.retrieved == "2026-01-01"
    # A property that states its own license keeps it.
    assert m.ultimate_strength.citation.license == "OVERRIDE"


def test_bundled_records_marked_bundled(db: MaterialsDatabase) -> None:
    # Bundled records are distinguishable from user/team extension records.
    assert db.get("AA-6061-T6").bundled is True


def _cite() -> dict:
    return {
        "source": "s",
        "condition": "c",
        "license": "l",
        "retrieved": "2026-07-08",
    }
