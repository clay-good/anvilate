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
from anvilate.standards.materials import _load_records


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


def test_titanium_grade5_properties_resolved(db: MaterialsDatabase) -> None:
    # Ti-6Al-4V (Grade 5) is a distinct, mechanically stiff/strong aerospace alloy.
    ti = db.get("Ti-6Al-4V")
    assert ti.category == "titanium"
    assert ti.elastic_modulus.quantity.to("GPa").magnitude == pytest.approx(113.8)
    assert ti.density.quantity.to("g/cm**3").magnitude == pytest.approx(4.43)
    assert ti.yield_strength.quantity.to("MPa").magnitude == pytest.approx(880.0)
    assert ti.ultimate_strength.quantity.to("MPa").magnitude == pytest.approx(950.0)
    assert ti.poisson_ratio.value == pytest.approx(0.342)


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
    mats = _load_records(text, bundled=True)
    m = mats["X-1"]
    assert m.elastic_modulus.citation.license == "TEST-LICENSE"
    assert m.elastic_modulus.citation.retrieved == "2026-01-01"
    # A property that states its own license keeps it.
    assert m.ultimate_strength.citation.license == "OVERRIDE"


def test_bundled_records_marked_bundled(db: MaterialsDatabase) -> None:
    # Bundled records are distinguishable from user/team extension records.
    assert db.get("AA-6061-T6").bundled is True
    assert db.extension_ids() == []


_EXTENSION_YAML = """
dataset:
  name: acme-internal
  version: "1"
  license: "team-local"
  retrieved: "2026-07-08"
materials:
  ACME-BRACKET-STOCK:
    name: "Acme internal bracket stock"
    category: aluminum
    elastic_modulus:
      quantity: {magnitude: 69, unit: GPa}
      citation: {source: "internal cert", condition: "as-supplied"}
    poisson_ratio:
      value: 0.33
      citation: {source: "internal cert", condition: "as-supplied"}
    density:
      quantity: {magnitude: 2.70, unit: g/cm**3}
      citation: {source: "internal cert", condition: "as-supplied"}
    yield_strength:
      quantity: {magnitude: 300, unit: MPa}
      citation: {source: "internal cert", condition: "as-supplied"}
    ultimate_strength:
      quantity: {magnitude: 330, unit: MPa}
      citation: {source: "internal cert", condition: "as-supplied"}
"""


def test_team_local_extension_record_referenced_like_bundled(db: MaterialsDatabase) -> None:
    # Scenario: company part library — a team adds a local record, referenced
    # like any bundled material, but marked as a team-local (non-bundled) record.
    extended = db.extended(_EXTENSION_YAML)
    stock = extended.get("ACME-BRACKET-STOCK")
    assert stock.bundled is False
    assert stock.yield_strength.quantity.to("MPa").magnitude == pytest.approx(300.0)
    assert extended.extension_ids() == ["ACME-BRACKET-STOCK"]
    # The bundled database is left unchanged.
    assert not db.has_material("ACME-BRACKET-STOCK")


def test_extension_overrides_bundled_record(db: MaterialsDatabase) -> None:
    # An extension record supersedes a bundled record of the same ID and is
    # still marked non-bundled, so a report can flag the override.
    override = _EXTENSION_YAML.replace("ACME-BRACKET-STOCK", "AA-6061-T6")
    extended = db.extended(override)
    record = extended.get("AA-6061-T6")
    assert record.bundled is False
    assert record.yield_strength.quantity.to("MPa").magnitude == pytest.approx(300.0)
    assert len(extended) == len(db)  # override, not addition


def test_standards_resolver_backs_spec_reference_validation() -> None:
    # The materials database is the single source of truth for reference
    # validation: a spec referencing a DB material validates, and an unknown
    # one is rejected with a suggestion drawn from the database.
    from anvilate.spec import (
        AcceptanceCriteria,
        DesignSpec,
        Manufacturing,
        ManufacturingProcess,
        MaterialRef,
        Provenanced,
        StandardComponentInterface,
        UnknownReferenceError,
        ValidationTier,
        validate_references,
    )
    from anvilate.standards import default_standards_resolver
    from anvilate.units import UnitSystem

    resolver = default_standards_resolver()

    def _spec(material: str) -> DesignSpec:
        return DesignSpec(
            name="probe",
            description="probe",
            units=Provenanced.stated(UnitSystem.SI),
            material=MaterialRef(ref=material),
            manufacturing=Manufacturing(process=ManufacturingProcess.CNC_MILLING),
            interfaces=[StandardComponentInterface(ref="NEMA23", tag="bore")],
            acceptance=AcceptanceCriteria(tiers=[ValidationTier.T0_GEOMETRY]),
        )

    validate_references(_spec("AA-6061-T6"), resolver)  # resolves against the DB

    with pytest.raises(UnknownReferenceError) as exc:
        validate_references(_spec("AA-6061-T7"), resolver)
    assert "AA-6061-T6" in exc.value.suggestions


def _cite() -> dict:
    return {
        "source": "s",
        "condition": "c",
        "license": "l",
        "retrieved": "2026-07-08",
    }


# --- Components database (NEMA frames) ---


@pytest.fixture(scope="module")
def cdb():
    from anvilate.standards import default_components_db

    return default_components_db()


def test_nema23_mounting_geometry_from_database(cdb) -> None:
    # Scenario: NEMA 23 resolution — the mounting bolt-square and pilot bore come
    # from the database record, each with a citation.
    frame = cdb.get("NEMA23")
    assert frame.bolt_spacing.quantity.to("mm").magnitude == pytest.approx(47.14)
    assert frame.pilot_diameter.quantity.to("mm").magnitude == pytest.approx(38.1)
    assert frame.bolt_spacing.citation.source
    assert frame.bolt_spacing.citation.license


def test_component_citations_expose_the_evidence_trail(cdb) -> None:
    # Mirrors Material.citations(): every recorded dimension carries its source.
    citations = cdb.get("NEMA23").citations()
    assert set(citations) == {
        "faceplate_width",
        "bolt_spacing",
        "pilot_diameter",
        "mounting_hole",
    }
    for name, cite in citations.items():
        assert isinstance(cite, PropertyCitation), name
        assert cite.source and cite.license, name


def test_component_properties_are_length_dimensioned(cdb) -> None:
    for component_id in cdb.known_components():
        frame = cdb.get(component_id)
        for field in ("faceplate_width", "bolt_spacing", "pilot_diameter", "mounting_hole"):
            assert getattr(frame, field).quantity.has_dimension("[length]"), (component_id, field)


def test_component_wrong_dimension_rejected() -> None:
    from anvilate.standards import NemaFrame

    record = {
        "id": "BAD",
        "name": "bad",
        "faceplate_width": {"quantity": {"magnitude": 5, "unit": "kg"}, "citation": _cite()},
        "bolt_spacing": {"quantity": {"magnitude": 31, "unit": "mm"}, "citation": _cite()},
        "pilot_diameter": {"quantity": {"magnitude": 22, "unit": "mm"}, "citation": _cite()},
        "mounting_hole": {"quantity": {"magnitude": 3, "unit": "mm"}, "citation": _cite()},
    }
    with pytest.raises(Exception) as exc:
        NemaFrame.model_validate(record)
    msg = str(exc.value)
    assert "faceplate_width" in msg
    assert "length" in msg


def test_coverage_gap_surfaces_rather_than_guessing(cdb) -> None:
    # Scenario: coverage gap surfaces to user — an un-recorded frame is unknown
    # (with a near-miss), never silently estimated.
    from anvilate.standards import UnknownComponentError, default_standards_resolver

    assert not cdb.has_component("NEMA34")
    with pytest.raises(UnknownComponentError) as exc:
        cdb.get("NEMA34")
    assert exc.value.suggestions  # offers the closest recorded frames
    assert not default_standards_resolver().has_component("NEMA34")


def test_resolver_composes_component_db_and_seed() -> None:
    # The DB-backed frames and the not-yet-tabled seed IDs are one component set.
    from anvilate.standards import default_standards_resolver

    resolver = default_standards_resolver()
    assert set(resolver.known_components()) == {
        "NEMA17",
        "NEMA23",
        "EXT-4040",
        "EXT-2020",
        "ISO4762-M5",
    }
    assert resolver.has_component("NEMA23")  # from the components DB
    assert resolver.has_component("EXT-4040")  # from the static seed


# --- Metric clearance holes (ISO 273) ---


@pytest.fixture(scope="module")
def clearance():
    from anvilate.standards import default_clearance_table

    return default_clearance_table()


def test_clearance_hole_lookup_returns_diameter_and_citation(clearance) -> None:
    # Scenario: clearance hole lookup — an M5 screw at normal fit returns the
    # standard clearance diameter with its source citation.
    from anvilate.standards import Fit

    normal = clearance.get("M5", Fit.NORMAL)
    assert normal.quantity.to("mm").magnitude == pytest.approx(5.5)
    assert "ISO 273" in normal.citation.source
    assert normal.citation.license
    # Fit changes the diameter; normal is the default.
    assert clearance.get("M5", Fit.CLOSE).quantity.to("mm").magnitude == pytest.approx(5.3)
    assert clearance.get("M5").quantity == normal.quantity


def test_clearance_holes_are_length_dimensioned(clearance) -> None:
    for size in clearance.sizes():
        assert clearance.get(size).quantity.has_dimension("[length]"), size


def test_clearance_hole_ordering_is_numeric(clearance) -> None:
    # M2.5 sorts between M2 and M3, not lexically after M2.
    assert clearance.sizes()[:3] == ["M2", "M2.5", "M3"]


def test_clearance_hole_unknown_size_surfaces_gap(clearance) -> None:
    from anvilate.standards import UnknownThreadSizeError

    with pytest.raises(UnknownThreadSizeError):
        clearance.get("M7")  # not a preferred size; no record rather than a guess


# --- Metric thread pitch and tap drill (ISO 261 / 724) ---


@pytest.fixture(scope="module")
def threads():
    from anvilate.standards import default_thread_table

    return default_thread_table()


def test_thread_pitch_and_tap_drill_lookup(threads) -> None:
    m5 = threads.get("M5")
    assert m5.pitch.quantity.to("mm").magnitude == pytest.approx(0.8)
    assert m5.tap_drill.quantity.to("mm").magnitude == pytest.approx(4.2)
    assert "ISO 261" in m5.pitch.citation.source
    assert m5.tap_drill.citation.license


def test_thread_dimensions_are_length(threads) -> None:
    for size in threads.sizes():
        rec = threads.get(size)
        assert rec.pitch.quantity.has_dimension("[length]"), size
        assert rec.tap_drill.quantity.has_dimension("[length]"), size


def test_thread_unknown_size_surfaces_gap(threads) -> None:
    from anvilate.standards import UnknownThreadSizeError

    with pytest.raises(UnknownThreadSizeError):
        threads.get("M7")


def test_larger_preferred_sizes_resolved(clearance, threads) -> None:
    # M14/M16/M20 extend the ISO 273/261 coverage past M12.
    from anvilate.standards import Fit

    assert clearance.get("M16", Fit.NORMAL).quantity.to("mm").magnitude == pytest.approx(17.5)
    assert clearance.get("M20", Fit.COARSE).quantity.to("mm").magnitude == pytest.approx(24.0)
    assert clearance.get("M14", Fit.CLOSE).quantity.to("mm").magnitude == pytest.approx(15.0)
    m20 = threads.get("M20")
    assert m20.pitch.quantity.to("mm").magnitude == pytest.approx(2.5)
    assert m20.tap_drill.quantity.to("mm").magnitude == pytest.approx(17.5)
    assert threads.get("M16").pitch.quantity.to("mm").magnitude == pytest.approx(2.0)
