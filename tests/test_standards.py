"""Tests for the materials database, tracking the standards-data spec scenarios."""

from __future__ import annotations

import re
from pathlib import Path

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


def test_extrusion_alloy_6063_resolved(db: MaterialsDatabase) -> None:
    # 6063-T6 is the standard extrusion alloy (cf. the seed EXT-4040/EXT-2020).
    al = db.get("AA-6063-T6")
    assert al.category == "aluminum"
    assert al.yield_strength.quantity.to("MPa").magnitude == pytest.approx(214.0)
    assert al.ultimate_strength.quantity.to("MPa").magnitude == pytest.approx(241.0)
    assert "T6" in al.yield_strength.citation.condition


def test_aerospace_aluminum_2024_resolved(db: MaterialsDatabase) -> None:
    # 2024-T3 is the classic aerospace structural aluminum (fuselage skins),
    # distinct from the 7075 already in the DB; ASM T3 values.
    al = db.get("AA-2024-T3")
    assert al.category == "aluminum"
    assert al.elastic_modulus.quantity.to("GPa").magnitude == pytest.approx(73.1)
    assert al.yield_strength.quantity.to("MPa").magnitude == pytest.approx(345.0)
    assert al.ultimate_strength.quantity.to("MPa").magnitude == pytest.approx(483.0)
    assert "T3" in al.yield_strength.citation.condition


def test_cast_aluminum_a356_resolved(db: MaterialsDatabase) -> None:
    # A356-T6 is the DB's first casting alloy (all others are wrought); common for
    # cast brackets, housings, and wheels. T6 permanent-mold values.
    al = db.get("AA-A356-T6")
    assert al.category == "aluminum"
    assert al.elastic_modulus.quantity.to("GPa").magnitude == pytest.approx(72.4)
    assert al.yield_strength.quantity.to("MPa").magnitude == pytest.approx(205.0)
    assert al.ultimate_strength.quantity.to("MPa").magnitude == pytest.approx(283.0)
    assert "permanent mold" in al.yield_strength.citation.condition


def test_structural_extrusion_alloy_6082_resolved(db: MaterialsDatabase) -> None:
    # 6082-T6 is the higher-strength structural extrusion alloy (vs the softer
    # 6063); its strengths are the EN 755-2 extrusion minima (Rp0.2 250, Rm 290).
    al = db.get("AA-6082-T6")
    assert al.category == "aluminum"
    assert al.yield_strength.quantity.to("MPa").magnitude == pytest.approx(250.0)
    assert al.ultimate_strength.quantity.to("MPa").magnitude == pytest.approx(290.0)
    assert "EN 755-2" in al.yield_strength.citation.source
    # Distinctly stronger than the soft extrusion alloy it complements.
    assert (
        al.yield_strength.quantity.to("MPa").magnitude
        > db.get("AA-6063-T6").yield_strength.quantity.to("MPa").magnitude
    )


def test_bearing_bronze_resolved_with_copper_alloy_category(db: MaterialsDatabase) -> None:
    # C93200 (SAE 660) is the DB's first copper-family alloy, opening the
    # copper_alloy category; the standard cast bushing bronze (CDA reference).
    bronze = db.get("C93200-SAE660")
    assert bronze.category == "copper_alloy"
    assert bronze.elastic_modulus.quantity.to("GPa").magnitude == pytest.approx(100.0)
    assert bronze.density.quantity.to("g/cm**3").magnitude == pytest.approx(8.93)
    assert bronze.yield_strength.quantity.to("MPa").magnitude == pytest.approx(125.0)
    assert bronze.ultimate_strength.quantity.to("MPa").magnitude == pytest.approx(240.0)
    assert "Copper Development Association" in bronze.yield_strength.citation.source


def test_ductile_iron_resolved_with_new_category_and_no_fatigue_estimate(
    db: MaterialsDatabase,
) -> None:
    # ASTM A536 65-45-12 opens the cast_iron category; its strengths are the
    # grade-name minima (45 ksi yield / 65 ksi tensile). Endurance is absent, not
    # a misleading 0.5*Su steel estimate.
    di = db.get("ASTM-A536-65-45-12")
    assert di.category == "cast_iron"
    assert di.yield_strength.quantity.to("MPa").magnitude == pytest.approx(310.0)
    assert di.ultimate_strength.quantity.to("MPa").magnitude == pytest.approx(448.0)
    assert "A536" in di.yield_strength.citation.source
    assert di.endurance_limit is None


def test_mild_steel_1018_resolved_with_estimated_endurance(db: MaterialsDatabase) -> None:
    # 1018 CD is the reference general-purpose mild steel; its strengths are the
    # Shigley Table A-20 cold-drawn values, and the endurance limit is a labeled
    # 0.5*Su screening estimate like the other steels.
    steel = db.get("AISI-1018-CD")
    assert steel.category == "carbon_steel"
    assert steel.yield_strength.quantity.to("MPa").magnitude == pytest.approx(370.0)
    assert steel.ultimate_strength.quantity.to("MPa").magnitude == pytest.approx(440.0)
    assert "Shigley" in steel.ultimate_strength.citation.source
    se = steel.endurance_limit
    assert se.quantity.to("MPa").magnitude == pytest.approx(220.0)  # 0.5 * 440
    assert se.citation.estimated is True and se.citation.method


def test_medium_carbon_1045_resolved_with_estimated_endurance(db: MaterialsDatabase) -> None:
    # 1045 CD is the common medium-carbon shaft/gear steel, between mild 1018 and
    # alloy 4140; Shigley Table A-20 cold-drawn values (77/91 kpsi) + a labeled
    # 0.5*Su endurance estimate.
    steel = db.get("AISI-1045-CD")
    assert steel.category == "carbon_steel"
    assert steel.yield_strength.quantity.to("MPa").magnitude == pytest.approx(530.0)
    assert steel.ultimate_strength.quantity.to("MPa").magnitude == pytest.approx(630.0)
    assert "Table A-20" in steel.ultimate_strength.citation.source
    assert steel.endurance_limit.quantity.to("MPa").magnitude == pytest.approx(315.0)  # 0.5*630
    assert steel.endurance_limit.citation.estimated is True
    # Stronger than the mild 1018 it sits above.
    assert (
        steel.yield_strength.quantity.to("MPa").magnitude
        > db.get("AISI-1018-CD").yield_strength.quantity.to("MPa").magnitude
    )


def test_alloy_steel_4140_resolved_with_new_category(db: MaterialsDatabase) -> None:
    # 4140 is the DB's first heat-treatable alloy steel; annealed strengths are
    # the Shigley Table A-21 values (60.5/95 kpsi) and it opens the alloy_steel
    # category (a free string, no code change).
    steel = db.get("AISI-4140")
    assert steel.category == "alloy_steel"
    assert steel.yield_strength.quantity.to("MPa").magnitude == pytest.approx(417.0)
    assert steel.ultimate_strength.quantity.to("MPa").magnitude == pytest.approx(655.0)
    assert "Table A-21" in steel.ultimate_strength.citation.source
    assert steel.endurance_limit.quantity.to("MPa").magnitude == pytest.approx(327.5)


def test_premium_alloy_steel_4340_resolved(db: MaterialsDatabase) -> None:
    # 4340 is the premium high-strength alloy steel (landing gear, high-load
    # shafts), stronger than 4140; Shigley Table A-21 annealed values (68.5/108
    # kpsi) + a labeled 0.5*Su endurance estimate.
    steel = db.get("AISI-4340")
    assert steel.category == "alloy_steel"
    assert steel.yield_strength.quantity.to("MPa").magnitude == pytest.approx(470.0)
    assert steel.ultimate_strength.quantity.to("MPa").magnitude == pytest.approx(745.0)
    assert "Table A-21" in steel.ultimate_strength.citation.source
    assert steel.endurance_limit.quantity.to("MPa").magnitude == pytest.approx(372.5)
    # Stronger than the 4140 it sits above.
    assert (
        steel.ultimate_strength.quantity.to("MPa").magnitude
        > db.get("AISI-4140").ultimate_strength.quantity.to("MPa").magnitude
    )


def test_stainless_316_completes_the_austenitic_pair(db: MaterialsDatabase) -> None:
    # 316 is the molybdenum-bearing corrosion-resistant sibling of 304; the two
    # share the ASTM A240 annealed strength minima (30/75 ksi).
    ss = db.get("SS-316")
    assert ss.category == "stainless_steel"
    assert ss.elastic_modulus.quantity.to("GPa").magnitude == pytest.approx(193.0)
    assert ss.density.quantity.to("g/cm**3").magnitude == pytest.approx(8.00)
    assert ss.yield_strength.quantity.to("MPa").magnitude == pytest.approx(205.0)
    assert ss.ultimate_strength.quantity.to("MPa").magnitude == pytest.approx(515.0)
    assert "A240" in ss.yield_strength.citation.source


def test_shear_modulus_derived_from_e_and_nu(db: MaterialsDatabase) -> None:
    # G = E/(2(1+nu)). Steel A36 (200 GPa, 0.26) -> 79.4 GPa;
    # aluminum 6061-T6 (68.9 GPa, 0.33) -> 25.9 GPa.
    a36 = db.get("ASTM-A36")
    expected = a36.elastic_modulus.quantity.to("GPa").magnitude / (
        2 * (1 + a36.poisson_ratio.value)
    )
    assert a36.shear_modulus().to("GPa").magnitude == pytest.approx(expected, rel=1e-9)
    al = db.get("AA-6061-T6")
    assert al.shear_modulus().to("GPa").magnitude == pytest.approx(25.9, rel=1e-2)


def test_bulk_modulus_derived_from_e_and_nu(db: MaterialsDatabase) -> None:
    # K = E/(3(1-2nu)). Steel A992 (200 GPa, 0.30) -> 166.7 GPa.
    a992 = db.get("ASTM-A992")
    expected = a992.elastic_modulus.quantity.to("GPa").magnitude / (
        3 * (1 - 2 * a992.poisson_ratio.value)
    )
    assert a992.bulk_modulus().to("GPa").magnitude == pytest.approx(expected, rel=1e-9)
    assert a992.bulk_modulus().to("GPa").magnitude == pytest.approx(166.7, rel=1e-3)
    # The bulk modulus exceeds the shear modulus for a typical metal (nu < 0.5).
    assert a992.bulk_modulus().to("GPa").magnitude > a992.shear_modulus().to("GPa").magnitude


def test_shear_modulus_feeds_a_torsion_check(db: MaterialsDatabase) -> None:
    # A DB material's derived G drives the shaft twist-angle check directly.
    from anvilate.analysis import shaft_twist_angle
    from anvilate.units import Quantity

    g = db.get("ASTM-A36").shear_modulus()
    theta = shaft_twist_angle(
        torque=Quantity.parse("50 N*m"),
        length=Quantity.parse("1 m"),
        diameter=Quantity.parse("20 mm"),
        shear_modulus=g,
    )
    assert theta.to("degree").magnitude > 0


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


def test_nema34_mounting_geometry_from_database(cdb) -> None:
    # NEMA 34 extends the golden-path frames: its 2.74 in bolt square and
    # 2.875 in pilot boss are unambiguous NEMA standard values.
    frame = cdb.get("NEMA34")
    assert frame.bolt_spacing.quantity.to("mm").magnitude == pytest.approx(69.6)
    assert frame.pilot_diameter.quantity.to("mm").magnitude == pytest.approx(73.025)
    assert frame.mounting_hole.quantity.to("mm").magnitude == pytest.approx(5.0)


def test_coverage_gap_surfaces_rather_than_guessing(cdb) -> None:
    # Scenario: coverage gap surfaces to user — an un-recorded frame is unknown
    # (with a near-miss), never silently estimated.
    from anvilate.standards import UnknownComponentError, default_standards_resolver

    assert not cdb.has_component("NEMA42")
    with pytest.raises(UnknownComponentError) as exc:
        cdb.get("NEMA42")
    assert exc.value.suggestions  # offers the closest recorded frames
    assert not default_standards_resolver().has_component("NEMA42")


def test_bundled_frames_marked_bundled(cdb) -> None:
    # Bundled frames are distinguishable from user/team extension records.
    assert cdb.get("NEMA23").bundled is True
    assert cdb.extension_ids() == []


_COMPONENT_EXTENSION_YAML = """
dataset:
  name: acme-internal-components
  version: "1"
  source: "Acme internal engineering standard"
  license: "team-local"
  retrieved: "2026-07-08"
frames:
  ACME-MOUNT-1:
    name: "Acme internal motor mount"
    faceplate_width:
      quantity: {magnitude: 60.0, unit: mm}
      citation: {condition: "internal drawing"}
    bolt_spacing:
      quantity: {magnitude: 50.0, unit: mm}
      citation: {condition: "internal drawing"}
    pilot_diameter:
      quantity: {magnitude: 40.0, unit: mm}
      citation: {condition: "internal drawing"}
    mounting_hole:
      quantity: {magnitude: 5.0, unit: mm}
      citation: {condition: "M5 mounting screw"}
"""


def test_team_local_component_extension_referenced_like_bundled(cdb) -> None:
    # Scenario: company part library — a team adds a local component record,
    # referenced like any bundled frame but marked team-local (non-bundled).
    extended = cdb.extended(_COMPONENT_EXTENSION_YAML)
    mount = extended.get("ACME-MOUNT-1")
    assert mount.bundled is False
    assert mount.bolt_spacing.quantity.to("mm").magnitude == pytest.approx(50.0)
    assert extended.extension_ids() == ["ACME-MOUNT-1"]
    # The team-local record's provenance is preserved end to end.
    assert mount.pilot_diameter.citation.license == "team-local"
    # The bundled database is left unchanged.
    assert not cdb.has_component("ACME-MOUNT-1")


def test_component_extension_overrides_bundled_record(cdb) -> None:
    # An extension record of the same ID supersedes the bundled one and is marked
    # non-bundled, so a team can correct a frame without forking the seed.
    override = _COMPONENT_EXTENSION_YAML.replace("ACME-MOUNT-1", "NEMA23")
    extended = cdb.extended(override)
    frame = extended.get("NEMA23")
    assert frame.bundled is False
    assert frame.bolt_spacing.quantity.to("mm").magnitude == pytest.approx(50.0)
    # The bundled database still holds the original standardized value.
    assert cdb.get("NEMA23").bundled is True
    assert cdb.get("NEMA23").bolt_spacing.quantity.to("mm").magnitude == pytest.approx(47.14)


def test_resolver_composes_component_db_and_seed() -> None:
    # The DB-backed frames, the bearing table, and the fastener/extrusion tables
    # are one component set.
    from anvilate.standards import default_standards_resolver

    resolver = default_standards_resolver()
    known = set(resolver.known_components())
    assert {"NEMA17", "NEMA23", "NEMA34", "EXT-4040", "EXT-2020", "ISO4762-M5"} <= known
    assert "6204" in known  # bearings resolve as standard components too
    assert resolver.has_component("NEMA23")  # from the components DB
    assert resolver.has_component("6204")  # from the bearing table
    assert resolver.has_component("EXT-4040")  # from the extrusion table
    assert not resolver.has_component("6211")  # a bearing not in the seed is unknown


# --- Deep-groove ball bearing boundary dimensions (ISO 15) ---


@pytest.fixture(scope="module")
def bearings():
    from anvilate.standards import default_bearing_table

    return default_bearing_table()


def test_bearing_boundary_dimensions_with_citation(bearings) -> None:
    # 608 (the ubiquitous skate bearing) is 8 x 22 x 7 mm; each dimension carries
    # its ISO 15 citation.
    b608 = bearings.get("608")
    assert b608.bore.quantity.to("mm").magnitude == pytest.approx(8.0)
    assert b608.outer_diameter.quantity.to("mm").magnitude == pytest.approx(22.0)
    assert b608.width.quantity.to("mm").magnitude == pytest.approx(7.0)
    assert "ISO 15" in b608.bore.citation.source
    assert b608.bore.citation.license
    # 6204: 20 x 47 x 14 mm, the light-series 20 mm-bore bearing.
    b6204 = bearings.get("6204")
    assert b6204.bore.quantity.to("mm").magnitude == pytest.approx(20.0)
    assert b6204.outer_diameter.quantity.to("mm").magnitude == pytest.approx(47.0)
    assert b6204.width.quantity.to("mm").magnitude == pytest.approx(14.0)


def test_bearing_dimensions_are_length(bearings) -> None:
    for designation in bearings.designations():
        rec = bearings.get(designation)
        for field in ("bore", "outer_diameter", "width"):
            assert getattr(rec, field).quantity.has_dimension("[length]"), (designation, field)


def test_bearing_citations_expose_the_evidence_trail(bearings) -> None:
    citations = bearings.get("6000").citations()
    assert set(citations) == {"bore", "outer_diameter", "width"}
    for name, cite in citations.items():
        assert isinstance(cite, PropertyCitation), name
        assert cite.source and cite.license, name


def test_bearing_ordering_is_numeric(bearings) -> None:
    # 608 sorts before the 6000-series, not lexically after 6304.
    designations = bearings.designations()
    assert designations.index("608") < designations.index("6000")
    assert designations.index("6000") < designations.index("6204")


def test_bearing_series_extends_to_40mm_bore(bearings) -> None:
    # The 60/62/63 series now reach a 30-40 mm bore: 6008 (40x68x15) and the
    # medium 6306 (30x72x19).
    b6008 = bearings.get("6008")
    assert b6008.bore.quantity.to("mm").magnitude == pytest.approx(40.0)
    assert b6008.outer_diameter.quantity.to("mm").magnitude == pytest.approx(68.0)
    b6306 = bearings.get("6306")
    assert b6306.outer_diameter.quantity.to("mm").magnitude == pytest.approx(72.0)
    assert b6306.width.quantity.to("mm").magnitude == pytest.approx(19.0)


def test_bearing_series_reach_50mm_bore(bearings) -> None:
    # All three series now extend to a 50 mm bore: 6010 (50x80x16), the light
    # 6210 (50x90x20), and the medium 6310 (50x110x27).
    b6010 = bearings.get("6010")
    assert b6010.bore.quantity.to("mm").magnitude == pytest.approx(50.0)
    assert b6010.outer_diameter.quantity.to("mm").magnitude == pytest.approx(80.0)
    b6210 = bearings.get("6210")
    assert b6210.outer_diameter.quantity.to("mm").magnitude == pytest.approx(90.0)
    b6310 = bearings.get("6310")
    assert b6310.outer_diameter.quantity.to("mm").magnitude == pytest.approx(110.0)
    assert b6310.width.quantity.to("mm").magnitude == pytest.approx(27.0)


def test_bearing_thin_section_68_series(bearings) -> None:
    # The 68-series thin-section bearings share a bore with the 60-series but have
    # a much smaller OD and width: 6804 is 20x32x7 (vs the 60-series 6004 42x12).
    b6800 = bearings.get("6800")
    assert b6800.bore.quantity.to("mm").magnitude == pytest.approx(10.0)
    assert b6800.outer_diameter.quantity.to("mm").magnitude == pytest.approx(19.0)
    assert b6800.width.quantity.to("mm").magnitude == pytest.approx(5.0)
    b6804 = bearings.get("6804")
    assert b6804.outer_diameter.quantity.to("mm").magnitude == pytest.approx(32.0)
    # Thinner than the extra-light 60-series bearing of the same 20 mm bore.
    assert (
        b6804.outer_diameter.quantity.to("mm").magnitude
        < bearings.get("6004").outer_diameter.quantity.to("mm").magnitude
    )


def test_bearing_unknown_designation_surfaces_gap(bearings) -> None:
    from anvilate.standards import UnknownBearingError

    with pytest.raises(UnknownBearingError) as exc:
        bearings.get("6211")  # not in the seed; a gap, not a guess
    assert exc.value.suggestions


def test_bundled_bearings_marked_bundled(bearings) -> None:
    # Bundled bearings are distinguishable from user/team extension records.
    assert bearings.get("6204").bundled is True
    assert bearings.extension_ids() == []


_BEARING_EXTENSION_YAML = """
dataset:
  name: acme-internal-bearings
  version: "1"
  source: "Acme internal bearing spec"
  license: "team-local"
  retrieved: "2026-07-08"
bearings:
  "ACME-SPINDLE-1": {bore: 22, outer_diameter: 50, width: 14}
"""


def test_team_local_bearing_extension_referenced_like_bundled(bearings) -> None:
    # Scenario: company part library — a team registers a special bearing,
    # referenced like any bundled one but marked team-local (non-bundled).
    extended = bearings.extended(_BEARING_EXTENSION_YAML)
    special = extended.get("ACME-SPINDLE-1")
    assert special.bundled is False
    assert special.bore.quantity.to("mm").magnitude == pytest.approx(22.0)
    assert extended.extension_ids() == ["ACME-SPINDLE-1"]
    # The bundled table is left unchanged.
    assert not bearings.has_bearing("ACME-SPINDLE-1")


def test_bearing_extension_overrides_bundled_record(bearings) -> None:
    # An extension record of the same designation supersedes the bundled one and
    # is marked non-bundled.
    override = _BEARING_EXTENSION_YAML.replace("ACME-SPINDLE-1", "6204")
    extended = bearings.extended(override)
    b = extended.get("6204")
    assert b.bundled is False
    assert b.outer_diameter.quantity.to("mm").magnitude == pytest.approx(50.0)
    # The bundled table still holds the standardized ISO 15 value (47 mm OD).
    assert bearings.get("6204").bundled is True
    assert bearings.get("6204").outer_diameter.quantity.to("mm").magnitude == pytest.approx(47.0)


# --- Parallel dowel pins (ISO 2338) ---


@pytest.fixture(scope="module")
def dowels():
    from anvilate.standards import default_dowel_pin_table

    return default_dowel_pin_table()


def test_dowel_pin_dimensions_with_citation(dowels) -> None:
    # A 6 mm ISO 2338 pin: diameter 6 mm at class m6, 1.2 mm chamfer, stocked
    # 12-60 mm; each dimension carries its ISO 2338 citation.
    p6 = dowels.get("ISO2338-6")
    assert p6.nominal_diameter.quantity.to("mm").magnitude == pytest.approx(6.0)
    assert p6.tolerance_class == "m6"
    assert p6.chamfer.quantity.to("mm").magnitude == pytest.approx(1.2)
    assert p6.length_min.quantity.to("mm").magnitude == pytest.approx(12.0)
    assert p6.length_max.quantity.to("mm").magnitude == pytest.approx(60.0)
    assert "ISO 2338" in p6.nominal_diameter.citation.source
    assert p6.nominal_diameter.citation.license


def test_dowel_pin_dimensions_are_length(dowels) -> None:
    for designation in dowels.designations():
        rec = dowels.get(designation)
        for field in ("nominal_diameter", "chamfer", "length_min", "length_max"):
            assert getattr(rec, field).quantity.has_dimension("[length]"), (designation, field)


def test_dowel_pin_citations_expose_the_evidence_trail(dowels) -> None:
    citations = dowels.get("ISO2338-3").citations()
    assert set(citations) == {"nominal_diameter", "chamfer", "length_min", "length_max"}
    for name, cite in citations.items():
        assert isinstance(cite, PropertyCitation), name
        assert cite.source and cite.license, name


def test_dowel_pin_ordering_is_numeric(dowels) -> None:
    # ISO2338-2 sorts before ISO2338-10 by nominal diameter, not lexically.
    designations = dowels.designations()
    assert designations.index("ISO2338-2") < designations.index("ISO2338-10")
    assert designations.index("ISO2338-10") < designations.index("ISO2338-20")


def test_dowel_pin_length_range_is_ordered(dowels) -> None:
    for designation in dowels.designations():
        rec = dowels.get(designation)
        lo = rec.length_min.quantity.to("mm").magnitude
        hi = rec.length_max.quantity.to("mm").magnitude
        assert lo < hi, designation


def test_dowel_pin_unknown_designation_surfaces_gap(dowels) -> None:
    from anvilate.standards import UnknownDowelPinError

    with pytest.raises(UnknownDowelPinError) as exc:
        dowels.get("ISO2338-7")  # not a standard size; a gap, not a guess
    assert exc.value.suggestions


def test_dowel_pins_resolve_as_standard_components() -> None:
    # Dowel pins join the one component set the resolver answers over.
    from anvilate.standards import default_standards_resolver

    resolver = default_standards_resolver()
    assert resolver.has_component("ISO2338-6")
    assert "ISO2338-6" in set(resolver.known_components())
    assert not resolver.has_component("ISO2338-7")


# --- Socket-head cap screws (ISO 4762) ---


@pytest.fixture(scope="module")
def cap_screws():
    from anvilate.standards import default_cap_screw_table

    return default_cap_screw_table()


def test_cap_screw_head_geometry_with_citation(cap_screws) -> None:
    # An M5 socket-head cap screw: head 8.5 mm dia x 5 mm high, 4 mm hex key; each
    # dimension carries its ISO 4762 citation.
    m5 = cap_screws.get("ISO4762-M5")
    assert m5.head_diameter.quantity.to("mm").magnitude == pytest.approx(8.5)
    assert m5.head_height.quantity.to("mm").magnitude == pytest.approx(5.0)
    assert m5.socket.quantity.to("mm").magnitude == pytest.approx(4.0)
    assert "ISO 4762" in m5.head_diameter.citation.source
    assert m5.head_diameter.citation.license


def test_cap_screw_dimensions_are_length(cap_screws) -> None:
    for designation in cap_screws.designations():
        rec = cap_screws.get(designation)
        for field in ("head_diameter", "head_height", "socket"):
            assert getattr(rec, field).quantity.has_dimension("[length]"), (designation, field)


def test_cap_screw_citations_expose_the_evidence_trail(cap_screws) -> None:
    citations = cap_screws.get("ISO4762-M6").citations()
    assert set(citations) == {"head_diameter", "head_height", "socket"}
    for name, cite in citations.items():
        assert isinstance(cite, PropertyCitation), name
        assert cite.source and cite.license, name


def test_cap_screw_ordering_is_numeric(cap_screws) -> None:
    # M4 sorts before M10 by nominal thread diameter, not lexically.
    designations = cap_screws.designations()
    assert designations.index("ISO4762-M4") < designations.index("ISO4762-M10")
    assert designations.index("ISO4762-M10") < designations.index("ISO4762-M20")


def test_cap_screw_head_clears_its_thread(cap_screws) -> None:
    # A head must be wider than its thread so a counterbore is a real feature: the
    # M6 head (10 mm) is well over the 6 mm nominal.
    m6 = cap_screws.get("ISO4762-M6")
    assert m6.head_diameter.quantity.to("mm").magnitude > 6.0


def test_cap_screw_unknown_designation_surfaces_gap(cap_screws) -> None:
    from anvilate.standards import UnknownCapScrewError

    with pytest.raises(UnknownCapScrewError) as exc:
        cap_screws.get("ISO4762-M7")  # not a standard socket-head size
    assert exc.value.suggestions


def test_cap_screws_resolve_as_standard_components() -> None:
    # Cap screws now resolve from the table, retiring the old ISO4762-M5 seed stub.
    from anvilate.standards import default_standards_resolver

    resolver = default_standards_resolver()
    assert resolver.has_component("ISO4762-M5")
    assert "ISO4762-M8" in set(resolver.known_components())
    assert not resolver.has_component("ISO4762-M7")


# --- Plain washers (ISO 7089) ---


@pytest.fixture(scope="module")
def washers():
    from anvilate.standards import default_washer_table

    return default_washer_table()


def test_washer_dimensions_with_citation(washers) -> None:
    # An M6 plain washer: 6.4 mm bore, 12 mm outer, 1.6 mm thick; each dimension
    # carries its ISO 7089 citation.
    w6 = washers.get("ISO7089-M6")
    assert w6.inner_diameter.quantity.to("mm").magnitude == pytest.approx(6.4)
    assert w6.outer_diameter.quantity.to("mm").magnitude == pytest.approx(12.0)
    assert w6.thickness.quantity.to("mm").magnitude == pytest.approx(1.6)
    assert "ISO 7089" in w6.inner_diameter.citation.source
    assert w6.inner_diameter.citation.license


def test_washer_dimensions_are_length(washers) -> None:
    for designation in washers.designations():
        rec = washers.get(designation)
        for field in ("inner_diameter", "outer_diameter", "thickness"):
            assert getattr(rec, field).quantity.has_dimension("[length]"), (designation, field)


def test_washer_citations_expose_the_evidence_trail(washers) -> None:
    citations = washers.get("ISO7089-M5").citations()
    assert set(citations) == {"inner_diameter", "outer_diameter", "thickness"}
    for name, cite in citations.items():
        assert isinstance(cite, PropertyCitation), name
        assert cite.source and cite.license, name


def test_washer_ordering_is_numeric(washers) -> None:
    # M4 sorts before M10 by nominal thread size, not lexically.
    designations = washers.designations()
    assert designations.index("ISO7089-M4") < designations.index("ISO7089-M10")
    assert designations.index("ISO7089-M10") < designations.index("ISO7089-M20")


def test_washer_bore_clears_and_face_exceeds_its_thread(washers) -> None:
    # The bore must clear the nominal thread and the outer face must exceed it, so
    # the washer is a real bearing surface: M8 bore 8.4 > 8, outer 16 > 8.4.
    w8 = washers.get("ISO7089-M8")
    bore = w8.inner_diameter.quantity.to("mm").magnitude
    outer = w8.outer_diameter.quantity.to("mm").magnitude
    assert bore > 8.0
    assert outer > bore


def test_washer_unknown_designation_surfaces_gap(washers) -> None:
    from anvilate.standards import UnknownWasherError

    with pytest.raises(UnknownWasherError) as exc:
        washers.get("ISO7089-M7")  # not a standard washer size
    assert exc.value.suggestions


def test_washers_resolve_as_standard_components() -> None:
    from anvilate.standards import default_standards_resolver

    resolver = default_standards_resolver()
    assert resolver.has_component("ISO7089-M6")
    assert "ISO7089-M8" in set(resolver.known_components())
    assert not resolver.has_component("ISO7089-M7")


# --- Hexagon nuts (ISO 4032) ---


@pytest.fixture(scope="module")
def hex_nuts():
    from anvilate.standards import default_hex_nut_table

    return default_hex_nut_table()


def test_hex_nut_dimensions_with_citation(hex_nuts) -> None:
    # An M6 hex nut: 10 mm across flats, 5.2 mm high; each dimension carries its
    # ISO 4032 citation.
    n6 = hex_nuts.get("ISO4032-M6")
    assert n6.width_across_flats.quantity.to("mm").magnitude == pytest.approx(10.0)
    assert n6.height.quantity.to("mm").magnitude == pytest.approx(5.2)
    assert "ISO 4032" in n6.width_across_flats.citation.source
    assert n6.width_across_flats.citation.license


def test_hex_nut_dimensions_are_length(hex_nuts) -> None:
    for designation in hex_nuts.designations():
        rec = hex_nuts.get(designation)
        for field in ("width_across_flats", "height"):
            assert getattr(rec, field).quantity.has_dimension("[length]"), (designation, field)


def test_hex_nut_citations_expose_the_evidence_trail(hex_nuts) -> None:
    citations = hex_nuts.get("ISO4032-M8").citations()
    assert set(citations) == {"width_across_flats", "height"}
    for name, cite in citations.items():
        assert isinstance(cite, PropertyCitation), name
        assert cite.source and cite.license, name


def test_hex_nut_ordering_is_numeric(hex_nuts) -> None:
    designations = hex_nuts.designations()
    assert designations.index("ISO4032-M4") < designations.index("ISO4032-M10")
    assert designations.index("ISO4032-M10") < designations.index("ISO4032-M20")


def test_hex_nut_uses_iso4032_width_not_din934(hex_nuts) -> None:
    # ISO 4032 narrowed the M10 and M12 widths across flats from the old DIN 934
    # sizes (17, 19) to 16 and 18 — the retrieved values must be the ISO ones.
    assert hex_nuts.get("ISO4032-M10").width_across_flats.quantity.to(
        "mm"
    ).magnitude == pytest.approx(16.0)
    assert hex_nuts.get("ISO4032-M12").width_across_flats.quantity.to(
        "mm"
    ).magnitude == pytest.approx(18.0)


def test_hex_nut_unknown_designation_surfaces_gap(hex_nuts) -> None:
    from anvilate.standards import UnknownHexNutError

    with pytest.raises(UnknownHexNutError) as exc:
        hex_nuts.get("ISO4032-M7")  # not a standard nut size
    assert exc.value.suggestions


def test_hex_nuts_resolve_as_standard_components() -> None:
    from anvilate.standards import default_standards_resolver

    resolver = default_standards_resolver()
    assert resolver.has_component("ISO4032-M6")
    assert "ISO4032-M8" in set(resolver.known_components())
    assert not resolver.has_component("ISO4032-M7")


# --- Hexagon-head bolts (ISO 4014 / 4017) ---


@pytest.fixture(scope="module")
def hex_bolts():
    from anvilate.standards import default_hex_bolt_table

    return default_hex_bolt_table()


def test_hex_bolt_head_geometry_with_citation(hex_bolts) -> None:
    # An M8 hex bolt head: 13 mm across flats, 5.3 mm high; each dimension carries
    # its ISO 4014/4017 citation.
    b8 = hex_bolts.get("ISO4014-M8")
    assert b8.width_across_flats.quantity.to("mm").magnitude == pytest.approx(13.0)
    assert b8.head_height.quantity.to("mm").magnitude == pytest.approx(5.3)
    assert "ISO 4014" in b8.width_across_flats.citation.source
    assert b8.width_across_flats.citation.license


def test_hex_bolt_dimensions_are_length(hex_bolts) -> None:
    for designation in hex_bolts.designations():
        rec = hex_bolts.get(designation)
        for field in ("width_across_flats", "head_height"):
            assert getattr(rec, field).quantity.has_dimension("[length]"), (designation, field)


def test_hex_bolt_citations_expose_the_evidence_trail(hex_bolts) -> None:
    citations = hex_bolts.get("ISO4014-M6").citations()
    assert set(citations) == {"width_across_flats", "head_height"}
    for name, cite in citations.items():
        assert isinstance(cite, PropertyCitation), name
        assert cite.source and cite.license, name


def test_hex_bolt_ordering_is_numeric(hex_bolts) -> None:
    designations = hex_bolts.designations()
    assert designations.index("ISO4014-M4") < designations.index("ISO4014-M10")
    assert designations.index("ISO4014-M10") < designations.index("ISO4014-M20")


def test_hex_bolt_head_shares_wrench_size_with_nut(hex_bolts) -> None:
    # ISO 4014 bolt heads and ISO 4032 nuts take the same wrench: M10 is 16 mm
    # across flats for both, so a joint's toolset is consistent.
    from anvilate.standards import default_hex_nut_table

    bolt_s = hex_bolts.get("ISO4014-M10").width_across_flats.quantity.to("mm").magnitude
    nut_s = (
        default_hex_nut_table().get("ISO4032-M10").width_across_flats.quantity.to("mm").magnitude
    )
    assert bolt_s == pytest.approx(nut_s)


def test_hex_bolt_unknown_designation_surfaces_gap(hex_bolts) -> None:
    from anvilate.standards import UnknownHexBoltError

    with pytest.raises(UnknownHexBoltError) as exc:
        hex_bolts.get("ISO4014-M7")  # not a standard bolt size
    assert exc.value.suggestions


def test_hex_bolts_resolve_as_standard_components() -> None:
    from anvilate.standards import default_standards_resolver

    resolver = default_standards_resolver()
    assert resolver.has_component("ISO4014-M8")
    assert "ISO4014-M6" in set(resolver.known_components())
    assert not resolver.has_component("ISO4014-M7")


# --- T-slot extrusion profiles ---


@pytest.fixture(scope="module")
def extrusions():
    from anvilate.standards import default_extrusion_table

    return default_extrusion_table()


def test_extrusion_profile_dimensions_with_citation(extrusions) -> None:
    # A 40x40 profile: 40 mm module, 10 mm T-slot; each dimension carries its
    # (vendor-convention) citation.
    p40 = extrusions.get("EXT-4040")
    assert p40.profile_width.quantity.to("mm").magnitude == pytest.approx(40.0)
    assert p40.slot_width.quantity.to("mm").magnitude == pytest.approx(10.0)
    assert p40.profile_width.citation.source
    assert p40.profile_width.citation.license


def test_extrusion_dimensions_are_length(extrusions) -> None:
    for designation in extrusions.designations():
        rec = extrusions.get(designation)
        for field in ("profile_width", "slot_width"):
            assert getattr(rec, field).quantity.has_dimension("[length]"), (designation, field)


def test_extrusion_series_ordering_is_numeric(extrusions) -> None:
    # 20 series sorts before 40 series by module width, not lexically.
    designations = extrusions.designations()
    assert designations.index("EXT-2020") < designations.index("EXT-3030")
    assert designations.index("EXT-3030") < designations.index("EXT-4545")


def test_extrusion_slot_fits_within_its_module(extrusions) -> None:
    # The T-slot is a mouth in the face, so it must be narrower than the module.
    for designation in extrusions.designations():
        rec = extrusions.get(designation)
        width = rec.profile_width.quantity.to("mm").magnitude
        slot = rec.slot_width.quantity.to("mm").magnitude
        assert 0 < slot < width, designation


def test_extrusion_provenance_flags_vendor_convention(extrusions) -> None:
    # T-slot cross-sections are not an ISO standard; the citation must name the
    # vendor convention so a report never presents the slot as a universal fact.
    cite = extrusions.get("EXT-2020").slot_width.citation
    assert "vendor" in cite.condition.lower()


def test_extrusion_unknown_designation_surfaces_gap(extrusions) -> None:
    from anvilate.standards import UnknownExtrusionError

    with pytest.raises(UnknownExtrusionError) as exc:
        extrusions.get("EXT-8080")  # not in the bundled convention
    assert exc.value.suggestions


def test_extrusions_resolve_as_standard_components() -> None:
    # Extrusions now resolve from the table, retiring the old EXT-* seed stubs.
    from anvilate.standards import default_standards_resolver

    resolver = default_standards_resolver()
    assert resolver.has_component("EXT-3030")
    assert "EXT-4545" in set(resolver.known_components())
    assert not resolver.has_component("EXT-8080")


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


def test_fine_pitch_thread_resolved_distinct_from_coarse(threads) -> None:
    # A fine M8x1 is a distinct record from coarse M8; its 75% tap drill is the
    # major diameter minus the finer pitch (8 - 1 = 7.0 mm vs 6.8 for coarse).
    coarse = threads.get("M8")
    fine = threads.get("M8x1")
    assert coarse.pitch.quantity.to("mm").magnitude == pytest.approx(1.25)
    assert fine.pitch.quantity.to("mm").magnitude == pytest.approx(1.0)
    assert fine.tap_drill.quantity.to("mm").magnitude == pytest.approx(7.0)
    assert "fine" in fine.pitch.citation.condition
    assert "coarse" in coarse.pitch.citation.condition


def test_fine_pitch_sorts_by_diameter_then_designation(threads) -> None:
    # Fine threads sort by nominal diameter (M8x1 near M8), not lexically, and
    # ties on diameter break on the designation string.
    sizes = threads.sizes()
    assert sizes.index("M8x1") == sizes.index("M8") + 1
    assert sizes.index("M10x1") < sizes.index("M10x1.25")
    assert sizes.index("M10x1.25") < sizes.index("M12")


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


def test_m22_and_m24_sizes_resolved(clearance, threads) -> None:
    # M22/M24 extend the ISO 273/261 coverage past M20.
    from anvilate.standards import Fit

    assert clearance.get("M22", Fit.NORMAL).quantity.to("mm").magnitude == pytest.approx(24.0)
    assert clearance.get("M24", Fit.CLOSE).quantity.to("mm").magnitude == pytest.approx(25.0)
    assert clearance.get("M24", Fit.COARSE).quantity.to("mm").magnitude == pytest.approx(28.0)
    m24 = threads.get("M24")
    assert m24.pitch.quantity.to("mm").magnitude == pytest.approx(3.0)
    assert m24.tap_drill.quantity.to("mm").magnitude == pytest.approx(21.0)
    assert threads.get("M22").pitch.quantity.to("mm").magnitude == pytest.approx(2.5)


def test_m27_and_m30_sizes_resolved(clearance, threads) -> None:
    # M27/M30 extend fastener coverage to M30 (heavy machinery / structural).
    from anvilate.standards import Fit

    assert clearance.get("M30", Fit.NORMAL).quantity.to("mm").magnitude == pytest.approx(33.0)
    assert clearance.get("M27", Fit.COARSE).quantity.to("mm").magnitude == pytest.approx(32.0)
    m30 = threads.get("M30")
    assert m30.pitch.quantity.to("mm").magnitude == pytest.approx(3.5)
    assert m30.tap_drill.quantity.to("mm").magnitude == pytest.approx(26.5)  # 30 - 3.5
    assert threads.get("M27").tap_drill.quantity.to("mm").magnitude == pytest.approx(24.0)


# --- ASME B36.10M pipe schedules ------------------------------------------


def test_pipe_schedule_table_is_internally_consistent():
    """A transcribed dimension table's own arithmetic is the cheapest guard on it."""
    from anvilate.standards import default_pipe_schedule_table

    table = default_pipe_schedule_table()
    assert len(table) == 108
    assert table.nominal_sizes()[:4] == ["1/2", "3/4", "1", "1-1/4"]
    assert table.nominal_sizes()[-3:] == ["18", "20", "24"]

    # Every schedule of a given NPS shares one outside diameter — that is the point of
    # the schedule system, and a transcription slip would break it.
    for nps in table.nominal_sizes():
        diameters = {
            table.get(nps, schedule).outside_diameter.quantity.to("mm").magnitude
            for schedule in table.schedules(nps)
        }
        assert len(diameters) == 1, (nps, diameters)

    for designation in table.designations():
        nps, schedule = designation.removeprefix("NPS ").split(" SCH ")
        pipe = table.get(nps, schedule)
        od = pipe.outside_diameter.quantity.to("mm").magnitude
        wall = pipe.wall_thickness.quantity.to("mm").magnitude
        # A wall over half the outside diameter would close the bore.
        assert 0 < wall < od / 2, designation
        assert pipe.inside_diameter.to("mm").magnitude == pytest.approx(od - 2 * wall)
        assert pipe.flow_area.to("mm**2").magnitude > 0
        assert pipe.citations()["wall_thickness"].source.startswith("ASME B36.10M")

    # Wall thickness rises monotonically with schedule at every size.
    for nps in table.nominal_sizes():
        walls = [
            table.get(nps, schedule).wall_thickness.quantity.to("mm").magnitude
            for schedule in ("10", "40", "80", "160")
        ]
        assert walls == sorted(walls), (nps, walls)
        # And the outside diameter rises with nominal size.
    diameters = [
        table.get(nps, "40").outside_diameter.quantity.to("mm").magnitude
        for nps in table.nominal_sizes()
    ]
    assert diameters == sorted(diameters)


def test_std_and_xs_are_not_aliases_for_schedule_40_and_80():
    """They coincide in small bore and diverge in large — the error a screen would make."""
    from anvilate.standards import default_pipe_schedule_table

    table = default_pipe_schedule_table()

    def wall(nps: str, schedule: str) -> float:
        return table.get(nps, schedule).wall_thickness.quantity.to("mm").magnitude

    # STD tracks Schedule 40 through NPS 10, then holds while 40 keeps thickening.
    for nps in ("1/2", "2", "4", "10"):
        assert wall(nps, "STD") == wall(nps, "40"), nps
    assert wall("24", "STD") == pytest.approx(9.53)
    assert wall("24", "40") == pytest.approx(17.48)
    # XS tracks Schedule 80 through NPS 8.
    for nps in ("1/2", "2", "8"):
        assert wall(nps, "XS") == wall(nps, "80"), nps
    assert wall("24", "XS") == pytest.approx(12.70)
    assert wall("24", "80") == pytest.approx(30.96)


def test_pipe_table_anchors_the_sizes_the_piping_example_already_uses():
    from anvilate.standards import UnknownPipeError, default_pipe_schedule_table
    from anvilate.units import Quantity

    table = default_pipe_schedule_table()
    nps4 = table.get("4", "40")
    assert nps4.outside_diameter.quantity.to("mm").magnitude == pytest.approx(114.3)
    assert nps4.wall_thickness.quantity.to("mm").magnitude == pytest.approx(6.02)
    assert table.get("4", "10").wall_thickness.quantity.to("mm").magnitude == pytest.approx(3.05)

    # The wall a pressure check may rely on: nominal less mill tolerance and corrosion.
    available = nps4.available_wall(corrosion_allowance=Quantity.parse("1.5 mm"))
    assert available.to("mm").magnitude == pytest.approx(6.02 * 0.875 - 1.5, rel=1e-9)
    # A wall wholly consumed by its allowances is zero, never negative — a negative
    # thickness flows straight into a pressure rating as a plausible number.
    assert (
        table.get("4", "10")
        .available_wall(corrosion_allowance=Quantity.parse("6 mm"))
        .to("mm")
        .magnitude
        == 0.0
    )
    with pytest.raises(ValueError, match="must not be negative"):
        nps4.available_wall(corrosion_allowance=Quantity.parse("-1 mm"))

    # An untabled combination is refused, not interpolated: a wall between two rows is
    # not a pipe anybody can buy.
    with pytest.raises(UnknownPipeError, match="no record for pipe"):
        table.get("5", "40")
    with pytest.raises(UnknownPipeError):
        table.get("4", "120")
    assert table.has_pipe("4", "40") and not table.has_pipe("4", "120")


# --- standards effectivity ---------------------------------------------------


def _basis(**over):
    from anvilate.standards import DesignBasis

    kwargs = {"pins": {"AISC 360": "16", "ACI 318": "19"}}
    kwargs.update(over)
    return DesignBasis(**kwargs)


def _waiver(**over):
    from datetime import date

    from anvilate.standards import MixedEditionWaiver

    kwargs = {
        "standard": "AISC 360",
        "editions": ("16", "22"),
        "accepted_by": "the engineer of record",
        "rationale": "the existing frame was designed to -16; new members follow -22",
        "accepted_on": date(2026, 8, 17),
    }
    kwargs.update(over)
    return MixedEditionWaiver(**kwargs)


def test_one_bundle_spanning_two_editions_fails_until_someone_signs_for_it():
    """Mixing is allowed. Mixing silently is not.

    A structure designed to one code and retrofitted under another is ordinary practice,
    so the answer is not to forbid it — it is to refuse to let the bundle read as though
    every number came from one book when it did not.
    """
    from anvilate.scorecard import CheckStatus
    from anvilate.standards import design_basis_scorecard

    split = ["AISC 360-16 §D2", "AISC 360-22 §E3", "ACI 318-19 §22.8.3"]
    failed = design_basis_scorecard("bundle", basis=_basis(), references=split)
    assert failed.status is CheckStatus.FAIL
    assert "AISC 360 appears at editions 16, 22" in failed.detail

    waived = design_basis_scorecard("bundle", basis=_basis(waivers=(_waiver(),)), references=split)
    assert waived.status is CheckStatus.PASS
    assert "the engineer of record" in waived.detail

    # A waiver for the wrong standard does not cover it, and neither does one that
    # names only one of the two editions in play.
    for wrong in (_waiver(standard="ACI 318"), _waiver(editions=("16", "14"))):
        still_failed = design_basis_scorecard(
            "bundle", basis=_basis(waivers=(wrong,)), references=split
        )
        assert still_failed.status is CheckStatus.FAIL


def test_a_waiver_with_nobody_s_name_on_it_is_a_suppressed_warning():
    """The two required fields are the two that make it an accepted risk rather than a
    silenced one."""
    import pytest

    with pytest.raises(ValueError, match="may not be blank"):
        _waiver(accepted_by="   ")
    with pytest.raises(ValueError, match="may not be blank"):
        _waiver(rationale="")
    with pytest.raises(ValueError, match="at least two editions"):
        _waiver(editions=("16", "16"))


def test_a_recorded_waiver_carries_its_reason_and_its_date_into_the_entry():
    """The entry named who accepted the mixing and not why, nor when.

    `MixedEditionWaiver` requires `accepted_by` **and** `rationale`, and says why in its own
    docstring: a waiver with nobody's name on it and no reason is a suppressed warning, not
    an accepted risk. The rendering carried the name alone — half of what the model says
    distinguishes the two — so a reviewer reading "AISC 360 16/22 by A. Engineer" could not
    tell a deliberately assessed retrofit from a mistake somebody signed, and could not tell
    whether the acceptance predates the edition it waives.
    """
    from anvilate.standards import design_basis_scorecard

    waiver = _waiver()
    basis = _basis(waivers=(waiver,))
    detail = design_basis_scorecard(
        "bundle", basis=basis, references=["AISC 360-16 §D2", "AISC 360-22 §E3"]
    ).detail
    assert waiver.accepted_by in detail, "the entry does not say who accepted the mixing"
    assert waiver.rationale in detail, "the entry does not say why the mixing was accepted"
    assert waiver.accepted_on.isoformat() in detail, "the entry does not say when"


def test_an_editionless_reference_is_not_evaluated_rather_than_passed():
    """A clause with no edition cannot be checked against a basis, and reporting only the
    ones that happen to carry editions would describe a bundle nobody assembled."""
    from anvilate.scorecard import CheckStatus
    from anvilate.standards import EditionAgreement, design_basis_scorecard, parse_citation

    mixed = ["AISC 360-16 §D2", "ASME BTH-1 §3-3"]
    entry = design_basis_scorecard("bundle", basis=_basis(), references=mixed)
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "1 of 2 references name no edition" in entry.detail
    assert "BTH-1" in entry.detail

    # Agreement against the basis, with the four states distinguished.
    basis = _basis()
    assert basis.agreement(parse_citation("AISC 360-16 §D2")) is EditionAgreement.MATCHES
    assert basis.agreement(parse_citation("AISC 360-22 §E3")) is EditionAgreement.DIFFERS
    assert basis.agreement(parse_citation("ASCE 7-22 §2.3")) is EditionAgreement.NOT_PINNED
    assert basis.agreement(parse_citation("AISC §E3")) is EditionAgreement.NOT_RECORDED


def test_a_pinned_edition_the_library_did_not_write_against_is_reported_not_failed():
    """A project may deliberately assess an existing structure under its original code.

    That is a real and correct thing to do, so it is reported rather than blocked — and
    reporting it is the point, because the alternative is a bundle that looks like it was
    checked against the project's own basis when it was not.
    """
    from anvilate.scorecard import CheckStatus
    from anvilate.standards import WRITTEN_AGAINST, design_basis_scorecard

    # The library's checks are written against AISC 360-16; this project pins -22.
    assert WRITTEN_AGAINST["AISC 360"] == "16"
    entry = design_basis_scorecard(
        "bundle",
        basis=_basis(pins={"AISC 360": "22"}),
        references=["AISC 360-16 §D2", "AISC 360-16 §H1.1"],
    )
    assert entry.status is CheckStatus.PASS
    assert "cited at an edition other than the pinned one" in entry.detail
    assert "AISC 360-16 against the pinned 22" in entry.detail


def test_a_pin_no_citation_matches_is_still_answered_by_the_library():
    """WRITTEN_AGAINST is the other half of the question, and it was wired to nothing.

    A steel project that designs to ASCE 7-16 pins it. This library's load combinations
    are written to ASCE 7-22. If the bundle in hand happens to carry no ASCE citation,
    the old card said PASS and mentioned neither edition — the pin was accepted and read
    by nothing, which is the silent green the whole library exists to refuse. The fact
    that answers it is a fact about the repository, not about this bundle's references.
    """
    from anvilate.scorecard import CheckStatus
    from anvilate.standards import WRITTEN_AGAINST, DesignBasis, design_basis_scorecard

    assert WRITTEN_AGAINST["ASCE 7"] == "22"
    steel_only = ["AISC 360-16 §F2.1", "AISC 360-16 §H1.1"]

    entry = design_basis_scorecard(
        "bundle",
        basis=DesignBasis(pins={"AISC 360": "16", "ASCE 7": "16"}),
        references=steel_only,
    )
    assert entry.status is CheckStatus.PASS
    assert "ASCE 7-16 is pinned while this library's checks are written against ASCE 7-22" in (
        entry.detail
    )

    # A pin that agrees with the library is answered too, and has nothing to report.
    agrees = design_basis_scorecard(
        "bundle",
        basis=DesignBasis(pins={"AISC 360": "16", "ASCE 7": "22"}),
        references=steel_only,
    )
    assert agrees.status is CheckStatus.PASS
    assert "ASCE 7" not in agrees.detail

    # And a pin the bundle DOES cite is reported once, off the citation, not twice.
    cited = design_basis_scorecard(
        "bundle",
        basis=DesignBasis(pins={"AISC 360": "22"}),
        references=steel_only,
    )
    assert cited.detail.count("AISC 360") == 1
    assert "written against" not in cited.detail


def test_a_pin_nothing_can_read_is_not_evaluated_and_names_the_near_misses():
    """A designation no citation carries and this library does not declare screens against
    nothing, and the commonest cause is a spelling that cannot match. Refusing it names
    what is available, the way every other retrieval refusal here does."""
    from anvilate.scorecard import CheckStatus
    from anvilate.standards import DesignBasis, design_basis_scorecard

    entry = design_basis_scorecard(
        "bundle",
        basis=DesignBasis(pins={"AISC-360": "16"}),
        references=["AISC 360-16 §F2.1"],
    )
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "screened against nothing" in entry.detail
    assert "'AISC-360'" in entry.detail
    # The near misses: the designations this bundle cites plus the ones the library declares.
    assert "AISC 360" in entry.detail
    assert "Aluminum Design Manual" in entry.detail

    # A pin naming a standard the bundle cites is read, and does not reach this branch.
    read = design_basis_scorecard(
        "bundle",
        basis=DesignBasis(pins={"AISC 360": "16"}),
        references=["AISC 360-16 §F2.1"],
    )
    assert read.status is CheckStatus.PASS


def test_the_library_declares_the_editions_it_was_actually_written_against():
    """WRITTEN_AGAINST is a fact about this repository, and the source has to agree.

    It is not a claim about which edition is current or adopted anywhere — that is the
    user's to declare, because adoption is a legal question that varies by jurisdiction
    and being confidently wrong about it is the worst failure mode available here.
    """
    from anvilate.standards import WRITTEN_AGAINST, parse_citation

    references = _evidence_reference_strings()
    seen: dict[str, set[str]] = {}
    for text in references:
        citation = parse_citation(text)
        if citation is not None:
            seen.setdefault(citation.standard, set()).add(citation.edition)

    for standard, editions in seen.items():
        if standard not in WRITTEN_AGAINST:
            continue
        assert editions == {WRITTEN_AGAINST[standard]}, (
            f"the source cites {standard} at {sorted(editions)} but WRITTEN_AGAINST "
            f"declares {WRITTEN_AGAINST[standard]!r}; one of the two is wrong"
        )
    assert "AISC 360" in seen, "the sample stopped containing any AISC citation"


def _evidence_reference_strings() -> set[str]:
    """The reference strings the packs put into entries and derivations."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_contract import _evidence_references

    return _evidence_references()


# --- the allowable basis: a distinction that used to live only in prose --------------------


def test_every_bundled_strength_declares_its_allowable_basis():
    """The gate. An unclassified strength cannot satisfy any basis requirement, so a
    record added without one silently fails every check that demands a minimum — which
    reads as a data problem long after it is one."""
    from anvilate.standards.materials import default_materials_db

    database = default_materials_db()
    unclassified = []
    for material_id in sorted(database.known_materials()):
        record = database.get(material_id)
        for name in ("yield_strength", "ultimate_strength"):
            citation = getattr(record, name).citation
            if citation.basis is None:
                unclassified.append(f"{material_id}.{name}")
    assert not unclassified, (
        "bundled strength values with no declared allowable basis — the distinction "
        f"between a handbook mean and a specified minimum: {unclassified}"
    )


def test_the_basis_matches_what_each_record_cites():
    """Classified from each record's own source, not assigned in bulk.

    Two records citing the same book get different answers: Shigley's Table A-20 is
    titled "Deterministic ASTM *Minimum* Tensile and Yield Strengths" and Table A-21 is
    "*Mean* Mechanical Properties of Some Heat-Treated Steels".
    """
    from anvilate.standards.materials import default_materials_db
    from anvilate.standards.records import AllowableBasis

    database = default_materials_db()
    expected = {
        "ASTM-A36": AllowableBasis.SPECIFICATION_MINIMUM,  # "specified minimum", in the source
        "ASTM-A992": AllowableBasis.SPECIFICATION_MINIMUM,
        "AISI-1018-CD": AllowableBasis.SPECIFICATION_MINIMUM,  # Shigley Table A-20, minima
        "AISI-4140": AllowableBasis.TYPICAL,  # Shigley Table A-21, means
        "AA-6061-T6": AllowableBasis.TYPICAL,  # ASM handbook typicals
        "AA-6082-T6": AllowableBasis.SPECIFICATION_MINIMUM,  # EN 755-2 Rp0.2 minimum
    }
    for material_id, basis in expected.items():
        assert database.get(material_id).yield_strength.citation.basis is basis, material_id


def test_a_basis_requirement_is_met_by_anything_at_or_above_it():
    from anvilate.standards.records import AllowableBasis, PropertyCitation

    def _cite(basis):
        return PropertyCitation(
            source="s", condition="c", license="l", retrieved="2026-01-01", basis=basis
        )

    assert _cite(AllowableBasis.A_BASIS).meets_basis(AllowableBasis.B_BASIS)
    assert _cite(AllowableBasis.B_BASIS).meets_basis(AllowableBasis.SPECIFICATION_MINIMUM)
    assert not _cite(AllowableBasis.TYPICAL).meets_basis(AllowableBasis.SPECIFICATION_MINIMUM)
    assert _cite(AllowableBasis.TYPICAL).meets_basis(AllowableBasis.TYPICAL)
    # Unclassified is not typical: it satisfies nothing, including the weakest claim.
    assert not _cite(None).meets_basis(AllowableBasis.TYPICAL)


def test_require_basis_refuses_a_typical_value_where_a_minimum_is_demanded():
    from anvilate.standards.materials import default_materials_db
    from anvilate.standards.records import AllowableBasis, InsufficientBasis, require_basis

    database = default_materials_db()
    minimum = AllowableBasis.SPECIFICATION_MINIMUM
    allowed = require_basis(
        database.get("ASTM-A36").yield_strength,
        minimum,
        material_id="ASTM-A36",
        name="yield strength",
    )
    assert allowed.to("MPa").magnitude == pytest.approx(250.0)
    with pytest.raises(InsufficientBasis, match="requires at least specification_minimum"):
        require_basis(
            database.get("AISI-4140").yield_strength,
            minimum,
            material_id="AISI-4140",
            name="yield strength",
        )


def test_the_provenance_roll_up_states_the_basis_alongside_the_source():
    from anvilate.evidence import _distinct_sources
    from anvilate.standards.materials import default_materials_db

    record = default_materials_db().get("AISI-4140")
    sources = _distinct_sources({"yield_strength": record.yield_strength.citation})
    assert any("(typical)" in s for s in sources)
    minimum = default_materials_db().get("ASTM-A36")
    assert any(
        "(specification minimum)" in s
        for s in _distinct_sources({"yield_strength": minimum.yield_strength.citation})
    )


# --- The license gate over every bundled dataset ---------------------------------------
#
# Anvilate is MIT, and a bundled table travels with the package: whatever its data is
# under, a redistributor inherits. The allow-list is therefore licenses that permit
# redistribution inside an MIT package without adding a copyleft or a share-alike term.
# CC0-1.0 is what everything here is (values only, source standards not redistributed);
# the rest are listed because the open-data changes will bring them, and a gate written
# for exactly today's one entry is a gate nobody can add a dataset through.
_REDISTRIBUTABLE_LICENSES = frozenset(
    {"CC0-1.0", "CC-BY-4.0", "ODC-By-1.0", "MIT", "Apache-2.0", "Unlicense"}
)

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "src" / "anvilate"

# Files that ship inside the package and are not datasets, each with the reason it is not
# one. Everything else that is not Python must carry a licensed dataset block. Listing the
# exemptions rather than the datasets is the direction that survives: a gate naming the two
# directories datasets happen to live in today cannot see the third.
_NOT_A_DATASET = {
    "skills/anvilate/SKILL.md": (
        "the agent skill — instructions this project wrote about its own library, "
        "under the project's own licence, not third-party data"
    ),
    "py.typed": (
        "the PEP 561 marker — an empty file whose presence tells a consumer's type checker "
        "that this package's inline annotations are meant to be read, carrying no content "
        "and no third-party data at all"
    ),
}


def _shipped_non_python_files() -> list[str]:
    """Every non-Python file the wheel carries, package-relative.

    `[tool.hatch.build.targets.wheel] packages = ["src/anvilate"]` ships the directory, so
    this is what gets distributed. `__pycache__` is a build artifact of the checkout and is
    not in the wheel.
    """
    return sorted(
        str(path.relative_to(_PACKAGE_ROOT))
        for path in _PACKAGE_ROOT.rglob("*")
        if path.is_file() and path.suffix != ".py" and "__pycache__" not in path.parts
    )


def _bundled_datasets() -> list[tuple[str, dict]]:
    """Every YAML dataset anywhere in the package, not only under two known directories."""
    import yaml

    return [
        (name, yaml.safe_load((_PACKAGE_ROOT / name).read_text()))
        for name in _shipped_non_python_files()
        if name.endswith(".yaml")
    ]


def _citation_sources(node: object) -> list[object]:
    """Every ``citation.source`` anywhere in a loaded document."""
    if isinstance(node, dict):
        found = []
        citation = node.get("citation")
        if isinstance(citation, dict):
            found.append(citation.get("source"))
        for value in node.values():
            found += _citation_sources(value)
        return found
    if isinstance(node, list):
        return [source for item in node for source in _citation_sources(item)]
    return []


def test_the_dataset_table_is_the_datasets_own_metadata():
    """`docs/citations.md` lists every bundled dataset; every cell is read back here.

    The page already stated a count and a licence, both gated. A count is the weakest true
    thing a page can say about seventeen files: it survives a version bump, a changed
    licence, and a dataset swapped for another one. So the page carries the table, and the
    table is compared row for row against the `dataset` blocks it describes — in both
    directions, because a row for a file that no longer ships is exactly as wrong as a
    shipped file with no row.
    """
    page = (Path(__file__).resolve().parent.parent / "docs" / "citations.md").read_text()
    rows = {}
    for line in page.splitlines():
        if not line.startswith("| `") or "/data/" not in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows[cells[0].strip("`")] = cells[1:]
    assert rows, "the dataset table in docs/citations.md has moved or lost its rows"

    expected = {}
    for name, document in _bundled_datasets():
        dataset = document["dataset"]
        source = dataset.get("source") or (
            "per-record citations — every property cites its own publication"
        )
        expected[name] = [
            str(source),
            str(dataset["version"]),
            str(dataset["license"]).split()[0],
            str(dataset["retrieved"]),
        ]

    assert set(rows) == set(expected), (
        "the table and the shipped datasets disagree about which files exist: "
        f"only on the page {sorted(set(rows) - set(expected))}, "
        f"only in the package {sorted(set(expected) - set(rows))}"
    )
    for name, cells in expected.items():
        assert rows[name] == cells, (
            f"the row for {name} says {rows[name]} and its dataset block says {cells}"
        )


def test_every_bundled_dataset_records_a_redistributable_license():
    """A bundled table travels with the package, so its license is a shipping condition.

    Every dataset states an SPDX identifier this project can redistribute under, the date
    it was retrieved, and where it came from — at the dataset level, or on every record
    for a table (the materials database) whose values each cite a different source.
    """
    datasets = _bundled_datasets()
    assert len(datasets) >= 17, f"the sweep found only {len(datasets)} datasets"

    for name, document in datasets:
        dataset = document.get("dataset")
        assert isinstance(dataset, dict), f"{name} ships no dataset block"
        for field in ("name", "version", "license", "retrieved"):
            assert dataset.get(field), f"{name} declares no dataset {field}"

        spdx = str(dataset["license"]).split()[0]
        assert spdx in _REDISTRIBUTABLE_LICENSES, (
            f"{name} is under {spdx!r}, which is not on the redistributable list "
            f"{sorted(_REDISTRIBUTABLE_LICENSES)}"
        )
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(dataset["retrieved"])), (
            f"{name} records {dataset['retrieved']!r} as its retrieval date, not an ISO date"
        )

        if not dataset.get("source"):
            # No dataset-level source: then every record has to carry its own, which is
            # what the materials table does — each property cites a different publication.
            sources = _citation_sources(document)
            assert sources, f"{name} names no source at either the dataset or the record level"
            assert all(sources), f"{name} has a record citation with an empty source"

    # docs/citations.md counts them and states what they are all under; both are claims
    # about this sweep's result, so they are checked against it rather than reviewed.
    page = " ".join(
        (Path(__file__).resolve().parent.parent / "docs" / "citations.md").read_text().split()
    )
    claim = re.search(r"Each of the (\w+) bundled datasets .*? All (\w+) are ([\w.-]+) today", page)
    assert claim is not None, "the bundled-dataset paragraph in docs/citations.md has moved"
    counted = {"seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20}
    assert counted[claim.group(1)] == len(datasets)
    assert claim.group(2) == claim.group(1), "the page counts the datasets twice, differently"
    assert {str(d["dataset"]["license"]).split()[0] for _n, d in datasets} == {claim.group(3)}


def test_the_license_gate_sees_what_it_claims_to(tmp_path, monkeypatch):
    """The gate's own adversary: each way a dataset can fail it, tried.

    A gate over data nobody has broken yet is a gate nobody has run. These are the four
    mutations that matter — an absent license, a copyleft one, a missing retrieval date
    and one that is not a date — plus a source declared nowhere.
    """
    import yaml

    good = {
        "dataset": {
            "name": "anvilate-test-seed",
            "version": "0.1.0",
            "source": "a published table",
            "license": "CC0-1.0 (values only)",
            "retrieved": "2026-08-27",
        },
        "rows": {"1": 2.0},
    }

    def _run(document: dict) -> None:
        path = tmp_path / "candidate.yaml"
        path.write_text(yaml.safe_dump(document))
        monkeypatch.setattr(
            f"{__name__}._bundled_datasets",
            lambda: [("candidate.yaml", yaml.safe_load(path.read_text()))] * 17,
        )
        test_every_bundled_dataset_records_a_redistributable_license()

    _run(good)  # the shape the gate is written for

    for mutation in (
        {"license": None},
        {"license": "GPL-3.0-or-later (a copyleft table)"},
        {"license": "CC-BY-SA-4.0 (share-alike)"},
        {"retrieved": None},
        {"retrieved": "August 2026"},
        {"name": None},
        {"version": None},
    ):
        broken = {"dataset": {**good["dataset"], **mutation}, "rows": good["rows"]}
        with pytest.raises(AssertionError):
            _run(broken)

    # A dataset with no source at all, and one whose records carry theirs.
    sourceless = {"dataset": {k: v for k, v in good["dataset"].items() if k != "source"}}
    with pytest.raises(AssertionError):
        _run({**sourceless, "rows": good["rows"]})
    _run({**sourceless, "rows": {"1": {"citation": {"source": "a published table"}}}})
    with pytest.raises(AssertionError):
        _run({**sourceless, "rows": {"1": {"citation": {"source": ""}}}})


def test_nothing_ships_inside_the_package_that_is_not_code_a_dataset_or_a_named_exemption():
    """`standards-data`: a release "contains no non-redistributable dataset content — only
    the fetch recipes and checksums".

    The licence gate above used to sweep `standards/data` and `tolerance/data` — the two
    directories every dataset happens to live in today. A `.csv` beside a module, a `.json`
    payload, or the allowables pack `expand-open-design-data` will add under `analysis/data`
    would ship with no licence record and nothing would notice, because the gate was looking
    at where the files are rather than at what the wheel contains.

    So the sweep is inverted: everything that is not Python must be a dataset with a
    redistributable licence, or an exemption with a written reason.
    """
    shipped = _shipped_non_python_files()
    assert shipped, "the sweep found no shipped files at all, so it is checking nothing"
    licensed = {name for name, _document in _bundled_datasets()}
    unaccounted = [name for name in shipped if name not in licensed and name not in _NOT_A_DATASET]
    assert not unaccounted, (
        f"these ship inside the package with no licence record: {unaccounted}. Either give "
        f"each a dataset block with a redistributable SPDX identifier, or add it to "
        f"_NOT_A_DATASET with the reason it is not third-party data"
    )
    for name, reason in _NOT_A_DATASET.items():
        assert name in shipped, f"{name} is exempt and no longer ships; strike it off"
        assert len(reason.split()) >= 6, f"{name} is exempt for no stated reason"


def test_the_shipped_file_sweep_would_see_a_new_data_file(tmp_path, monkeypatch):
    """The adversary. A sweep that returns a fixed list passes the test above forever."""
    import anvilate

    package = Path(anvilate.__file__).resolve().parent
    intruder = package / "analysis" / "smuggled_allowables.csv"
    intruder.write_text("a,b\n1,2\n", encoding="utf-8")
    try:
        assert "analysis/smuggled_allowables.csv" in _shipped_non_python_files()
    finally:
        intruder.unlink()
    assert "analysis/smuggled_allowables.csv" not in _shipped_non_python_files()


# --- the data has to survive packaging, not just exist in the tree --------------------------


def test_every_bundled_dataset_lives_where_the_wheel_will_carry_it():
    """The licence gate reads the source tree. Nothing read what gets *shipped*.

    Every test in this suite runs against `src/`, so a dataset that stopped being packaged
    would keep passing here and fail for the first person who `pip install`ed it — the
    materials database would raise on a lookup that works for every contributor. The
    mechanism that ships it is one line of `pyproject.toml`, and this asserts that line
    still means what it means.

    **A structural check, not a build.** Building a wheel fetches the backend, and this
    suite runs with the socket layer closed. The fresh-install verification is a manual
    procedure, written down in `docs/contributing-analysis.md`; what runs here is the part
    that can.
    """
    import tomllib

    repo = _PACKAGE_ROOT.parents[1]
    config = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = config["tool"]["hatch"]["build"]["targets"]["wheel"]

    packages = wheel.get("packages")
    assert packages == ["src/anvilate"], (
        f"the wheel ships {packages}; this gate understands one whole-package entry and "
        "would not notice data dropped from any other arrangement"
    )
    shipped_root = repo / packages[0]

    # Hatchling ships that directory whole. Anything narrowing it can drop a data file
    # silently, so a narrowing key is a failure here rather than something to interpret.
    for key in ("exclude", "only-include", "artifacts", "force-include", "sources"):
        assert key not in wheel, (
            f"the wheel target declares {key!r}; this gate cannot tell whether the bundled "
            "datasets survive it, and a dataset dropped from a wheel fails for a user and "
            "for nobody else"
        )

    shipped = _shipped_non_python_files()
    assert shipped, "the sweep found no shipped files"
    for name in shipped:
        assert (shipped_root / name).is_file(), f"{name} is not under {packages[0]}"

    # The two gates reinforce each other: every licensed dataset is a file the wheel takes.
    licensed = {name for name, _document in _bundled_datasets()}
    assert licensed <= set(shipped)
    assert len(licensed) >= 17, licensed


# --- A clause number is not an edition --------------------------------------------------


@pytest.mark.parametrize(
    ("text", "standard", "edition"),
    [
        # The designation ends in a digit, so the two-digit suffix is the edition.
        ("AISC 360-16 §J3.6", "AISC 360", "16"),
        ("ACI 318-19 §22.8.3", "ACI 318", "19"),
        ("AISI S100-16 Appendix 1", "AISI S100", "16"),
        ("ASCE 7-22 §2.3", "ASCE 7", "22"),
        # A hyphen-joined four-digit year. These used to parse as *no edition at all*,
        # because the four-digit branch demanded a space or a colon in front of the year —
        # so a code naming its edition in the ordinary way was recorded as naming none, and
        # any bundle citing it degraded to NOT_EVALUATED.
        ("ASME B31.3-2022 §304.1.2", "ASME B31.3", "2022"),
        ("ASME B36.10M-2018", "ASME B36.10M", "2018"),
        ("AWS D1.1-2020 §2.4", "AWS D1.1", "2020"),
        # The space and colon spellings still work.
        ("Aluminum Design Manual 2020 Part I §B.4", "Aluminum Design Manual", "2020"),
        ("ISO 286-2:2010", "ISO 286-2", "2010"),
        ("EN 1993-1-1:2005 §6.2", "EN 1993-1-1", "2005"),
    ],
)
def test_a_citation_that_names_an_edition_parses_to_that_edition(text, standard, edition):
    from anvilate.standards import parse_citation

    citation = parse_citation(text)
    assert citation is not None, f"{text!r} names an edition and parsed to none"
    assert (citation.standard, citation.edition) == (standard, edition)


@pytest.mark.parametrize(
    "text",
    [
        # ASME Section VIII numbers its clauses UG-37, UG-99, UW-12. The designation in
        # front of the hyphen ends in a *letter*, which is what separates a clause prefix
        # from a standard number. This library cites two of these itself.
        "ASME VIII Div 1 UG-37 (reinforcement of openings)",
        "ASME VIII Div 1 UG-99(b)",
        "ASME VIII Div 1 UW-12",
        "ASME VIII Div 1 UCS-56",
        # A part number, not an edition — the Eurocode case, which was already guarded.
        "EN 1993-1-9 §8",
        # And the third spelling of the same trap: `29 CFR 1926` is OSHA's construction
        # part, not the 1926 edition of the Code of Federal Regulations. This library
        # cites it beside a B30.20 proof test, so a bundle carrying 29 CFR 1926 and
        # 29 CFR 1910 would have read as one regulation at two editions.
        "ASME B30.20 (proof test) with OSHA 29 CFR 1926.251(a)(4)",
        "OSHA 29 CFR 1910.184",
        # One digit is not an edition suffix.
        "ASME BTH-1 §3-3",
        # No number at all.
        "AISC Design Guide 1",
    ],
)
def test_a_clause_number_is_not_read_as_an_edition(text):
    from anvilate.standards import parse_citation

    citation = parse_citation(text)
    assert citation is None, (
        f"{text!r} names no edition, and reading one out of it is worse than reading none: "
        f"got {citation}"
    )


def test_two_clauses_of_one_code_are_not_a_mixed_edition():
    """The end-to-end consequence, which is what makes this a defect and not a nit.

    `design_basis_scorecard` FAILs a bundle whose citations put one standard at two
    editions — a real and serious finding, since such a bundle reads as though every number
    came from one book. With `UG-37` and `UG-99(b)` parsing as editions 37 and 99, a
    perfectly ordinary pressure-vessel bundle — a UG-37 reinforcement check and the UG-99
    hydrostatic test, both of which this library emits — failed with

        ASME VIII Div 1 UG appears at editions 37, 99 with no recorded waiver

    A gate that cries wolf on the ordinary case is a gate that gets turned off.
    """
    from anvilate.scorecard import CheckStatus
    from anvilate.standards import DesignBasis, design_basis_scorecard

    entry = design_basis_scorecard(
        "design basis",
        basis=DesignBasis(),
        references=[
            "ASME VIII Div 1 UG-37 (reinforcement of openings)",
            "ASME VIII Div 1 UG-99(b)",
        ],
    )
    assert entry.status is not CheckStatus.FAIL, entry.detail
    # NOT_EVALUATED, not PASS: the two references genuinely name no edition, and the whole
    # rule is that an unversioned clause cannot be checked against a basis.
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "name no edition" in entry.detail
    # And a real split is still caught, so the fix did not disarm the check.
    split = design_basis_scorecard(
        "design basis",
        basis=DesignBasis(),
        references=["AISC 360-16 §J3.6", "AISC 360-22 §J3.6"],
    )
    assert split.status is CheckStatus.FAIL
    assert "16, 22" in split.detail


def test_no_standard_this_library_cites_appears_at_two_editions():
    """The library-scale form of the same property, over its own emitted citations.

    Every `reference=` string and clause constant in the package, grouped by the standard
    it parses to. A standard at two editions here is either a real mixed-edition citation
    in the library — which is a finding — or a parser reading a clause number as an
    edition, which is the defect above. Either way somebody has to look.
    """
    import re
    from collections import defaultdict
    from pathlib import Path

    from anvilate.standards import parse_citation

    pattern = re.compile(
        r'reference\s*=\s*"([^"]{4,90})"'
        r'|citation\s*=\s*"([^"]{4,90})"'
        r'|^_[A-Z_]*CLAUSE[A-Z_]*\s*=\s*"([^"]{4,90})"',
        re.M,
    )
    references = set()
    for path in (Path(__file__).resolve().parent.parent / "src" / "anvilate").rglob("*.py"):
        for groups in pattern.findall(path.read_text(encoding="utf-8")):
            references.add(next(g for g in groups if g))
    assert len(references) > 20, (
        f"only {len(references)} citation strings found; the scan stopped matching the "
        "way this library writes them, and a gate over nothing reports green"
    )

    editions = defaultdict(set)
    for text in references:
        citation = parse_citation(text)
        if citation is not None:
            editions[citation.standard].add(citation.edition)
    split = {name: sorted(eds) for name, eds in editions.items() if len(eds) > 1}
    assert not split, (
        f"standards this library cites at more than one edition: {split}. Either the "
        "citations really are mixed, or a clause number is being read as an edition"
    )


def test_a_parsed_citation_renders_back_as_the_text_it_came_from():
    """The renderer guessed the separator from the edition's *length*, and it cannot be.

    All three conventions are in daily use — `AISC 360-16`, `Aluminum Design Manual 2020`,
    `ISO 286-2:2010` — and which one a standard uses is a fact about that standard, not
    about the shape of its edition. Two digits meant a hyphen and everything else a space,
    which was right only while a four-digit edition could reach the renderer in one
    spelling. Once `ASME B31.3-2022` parsed at all, it rendered as `ASME B31.3 2022`.

    The round trip is the assertion, over the library's own citation strings, because a
    hand-written expectation here is a second place for the convention to be wrong.
    """
    import re
    from pathlib import Path

    from anvilate.standards import parse_citation

    pattern = re.compile(
        r'reference\s*=\s*"([^"]{4,90})"'
        r'|citation\s*=\s*"([^"]{4,90})"'
        r'|^_[A-Z_]*CLAUSE[A-Z_]*\s*=\s*"([^"]{4,90})"',
        re.M,
    )
    references = set()
    for path in (Path(__file__).resolve().parent.parent / "src" / "anvilate").rglob("*.py"):
        for groups in pattern.findall(path.read_text(encoding="utf-8")):
            references.add(next(g for g in groups if g))

    round_tripped = [
        text for text in sorted(references) if (c := parse_citation(text)) and str(c) == text
    ]
    drifted = [
        f"{text!r} renders as {str(parse_citation(text))!r}"
        for text in sorted(references)
        if (c := parse_citation(text)) and str(c) != text
    ]
    assert not drifted, "citations that do not render back as themselves:\n  " + "\n  ".join(
        drifted
    )
    assert len(round_tripped) > 10, (
        f"only {len(round_tripped)} citations round-tripped; if the parser stopped parsing "
        "them this assertion would pass on an empty set"
    )


@pytest.mark.parametrize(
    "text",
    [
        "AISC 360-16 §J4.1",
        "ASME B31.3-2022 §304.1.2",
        "AWS D1.1-2020",
        "ASME B36.10M-2018",
        "Aluminum Design Manual 2020 Part I",
        "ISO 286-2:2010",
        "EN 1993-1-1:2005 §6.2",
    ],
)
def test_each_separator_convention_survives_the_round_trip(text):
    """One case per convention, so a fix for one cannot quietly break another."""
    from anvilate.standards import parse_citation

    citation = parse_citation(text)
    assert citation is not None, f"{text!r} names an edition"
    assert str(citation) == text


def test_the_bundled_tables_are_read_once_and_shared():
    """Every bundled table was re-read and re-parsed on every call.

    A screen asks for the materials database each time it runs, so screening a structure of
    2,000 members parsed `materials.yaml` 2,000 times: 93% of that run's time was YAML, and
    the whole screen was 13x slower than the arithmetic in it. `anvilate.screening` already
    caches the *resolver* it builds from these tables, with a comment saying rebuilding the
    databases per document is work nobody asked for — the same insight, one layer above the
    tables that needed it.

    The tables are immutable through their public API, which is what makes sharing them safe,
    and the test below holds the one operation that could betray that.
    """
    from anvilate.standards import (
        default_bearing_table,
        default_components_db,
        default_hex_bolt_table,
        default_materials_db,
    )

    for factory in (
        default_materials_db,
        default_components_db,
        default_bearing_table,
        default_hex_bolt_table,
    ):
        assert factory() is factory(), f"{factory.__name__} rebuilds its table per call"


def test_extending_a_shared_database_leaves_the_shared_one_alone():
    """The risk the cache introduces, held directly: `extended` must build a new database
    rather than reach into the one every other caller now holds."""
    from anvilate.standards import default_materials_db

    extended = default_materials_db().extended(_EXTENSION_YAML)
    assert extended.has_material("ACME-BRACKET-STOCK")
    assert extended is not default_materials_db()
    assert not default_materials_db().has_material("ACME-BRACKET-STOCK")


def _unbounded_repeats(pattern: str) -> list[str]:
    """Every repetition in ``pattern`` with no upper bound, from the parsed pattern itself.

    `re._parser` is what `re.compile` runs, so this reads the same tree the engine will.
    Walking it rather than the pattern *text* is the whole point: a substring check finds a
    bounded repetition somewhere and concludes the pattern is bounded everywhere.
    """
    import re._parser as parser
    from re._constants import MAXREPEAT

    found: list[str] = []

    def walk(sequence) -> None:
        for op, av in sequence:
            name = str(op)
            if name in ("MAX_REPEAT", "MIN_REPEAT"):
                low, high, sub = av
                if high == MAXREPEAT:
                    found.append(f"{name} {{{low},}}")
                walk(sub)
            elif name == "SUBPATTERN":
                walk(av[3])
            elif name == "BRANCH":
                for branch in av[1]:
                    walk(branch)
            elif name in ("ASSERT", "ASSERT_NOT"):
                walk(av[1])
            elif name == "ATOMIC_GROUP":
                walk(av)

    walk(parser.parse(pattern))
    return found


def test_nothing_in_the_citation_pattern_repeats_without_a_bound():
    """The designation was an unbounded lazy repetition, so the scan was quadratic.

    `design_basis_scorecard` is handed `entry.reference` for every entry of a scorecard, and
    a scorecard comes back from the subject store and out of an attestation envelope. The
    time quadrupled every time the length doubled: a reference of a few thousand characters
    took a tenth of a second, and a long paste did not finish at all.

    **This replaces a wall-clock ratio, and the ratio is why.** It timed 4k against 16k and
    required under 8x, which is a fact about the machine as much as about the pattern: the
    16k run does four times the work, so it is four times as exposed to being descheduled,
    and `min` over several runs does not help when every run is contended. It failed three
    times in a row on a loaded machine and passed on a quiet one, at commits either side of
    the fix. What is asserted instead is the property, and it is deterministic.

    The structural half that was here checked a *substring* of the pattern text — that
    `{0,62}?` appears in it somewhere. That is satisfied by a pattern with a bounded
    repetition in one place and an unbounded one in another, which is exactly the defect,
    and `test_the_pattern_gate_sees_an_unbounded_repeat_it_is_not_looking_at` builds one.

    `_EUROCODE` is deliberately not held to this. Its `(?:-\\d+)*` is unbounded and cannot
    backtrack, because every iteration has to begin with a literal `-`: "EN 1993" followed by
    four thousand "-1"s and then a character that cannot continue takes 0.3 ms. A rule that
    refused it would be a rule about the shape of a quantifier rather than about the work.
    """
    from anvilate.standards.effectivity import _CITATION

    assert _unbounded_repeats(_CITATION.pattern) == [], (
        "the citation pattern repeats without an upper bound, which is what made the scan "
        "quadratic in a subject this library does not control"
    )


def test_the_designations_bound_is_the_one_the_engine_will_use():
    """The bound the engine will use is the constant, and not a literal beside it.

    What this catches is the join coming apart: the pattern is an f-string, and a hand-edit
    that writes `{0,900}?` into it leaves `_LONGEST_DESIGNATION` documented, ratcheted and
    read by nothing. Checked against the *parsed* pattern, since the pattern text is the
    string the constant was interpolated into.

    What it cannot catch is the constant itself being widened — it is keyed on the constant,
    so it agrees with whatever the constant says. That is
    `test_the_designation_ratchet_fires_on_a_designation_that_is_getting_long`'s job, and it
    reads the citations the library actually builds.
    """
    import re._parser as parser

    from anvilate.standards.effectivity import _CITATION, _LONGEST_DESIGNATION

    designation = None
    for op, av in parser.parse(_CITATION.pattern):
        if str(op) == "SUBPATTERN":
            for inner_op, inner_av in av[3]:
                if str(inner_op) == "MIN_REPEAT":
                    designation = inner_av[:2]
                    break
            break
    assert designation == (0, _LONGEST_DESIGNATION), designation


def test_the_pattern_gate_sees_an_unbounded_repeat_it_is_not_looking_at():
    """The adversary for the two above: the gate this replaced could not fail.

    Leave the designation's `{0,62}?` exactly where it is — so the old substring check still
    finds what it looks for — and make a *different* part of the pattern unbounded. The old
    assertion passes on it; the walk does not.
    """
    import re

    from anvilate.standards.effectivity import _CITATION, _LONGEST_DESIGNATION

    mutated = _CITATION.pattern.replace(r"[\s:](?P<long>", r"[\s:]*(?P<long>")
    assert mutated != _CITATION.pattern
    # What the old gate asserted, on the mutated pattern: both halves still hold.
    assert re.search(r"\{0,\d+\}\?", mutated)
    assert f"{{0,{_LONGEST_DESIGNATION}}}?" in mutated
    # And the pattern is unbounded all the same.
    assert _unbounded_repeats(mutated) == ["MAX_REPEAT {0,}"]


def test_the_subject_the_citation_scan_reads_is_bounded_too():
    """A linear scan of an unbounded string is still unbounded work.

    The pattern's bound is half the answer; the other half is that `entry.reference` — the
    only value that reaches `parse_citation` in this library — cannot be arbitrarily long.
    It is a `cited` field, and `cited` refuses past `_LONGEST_CITED` for this reason among
    others. Asserted here rather than only where the bound lives, because this is the caller
    that made the length matter.
    """
    import pydantic

    from anvilate._models import _LONGEST_CITED
    from anvilate.scorecard import CheckStatus, ScorecardEntry
    from anvilate.standards.effectivity import parse_citation

    def entry(reference: str) -> ScorecardEntry:
        return ScorecardEntry(name="n", status=CheckStatus.PASS, detail="d", reference=reference)

    assert entry("A" * _LONGEST_CITED).reference
    with pytest.raises(pydantic.ValidationError, match="is not one a reader can follow"):
        entry("A" * (_LONGEST_CITED + 1))

    # And the scan really is the consumer of that field.
    assert parse_citation("A" * _LONGEST_CITED) is None


def test_the_designation_ratchet_fires_on_a_designation_that_is_getting_long():
    """The session rule reports before the bound is reached, so prove the detector.

    A rule that fires only once the bound is already exceeded fires after the first real
    standard has been silently mis-parsed. This one reports at *half* the bound, and half a
    bound is exactly the sort of arithmetic that is written once and never exercised: today's
    longest designation is 22 characters against 62, so the ratchet is silent on real data
    and would stay silent if it were checking nothing at all.
    """
    from anvilate.standards.effectivity import _LONGEST_DESIGNATION, parse_citation
    from conftest import _designations_at_or_past_the_bound

    ordinary = "ASME BTH-1-2020 §3-3.2"
    assert parse_citation(ordinary) is not None
    assert _designations_at_or_past_the_bound({ordinary}) == set()

    # A designation exactly at half the bound, and one just under it.
    at_half = "A" * (_LONGEST_DESIGNATION // 2 - 1) + "1-2020"
    just_under = "A" * (_LONGEST_DESIGNATION // 2 - 3) + "1-2020"
    assert parse_citation(at_half) is not None and parse_citation(just_under) is not None
    assert _designations_at_or_past_the_bound({at_half}), at_half
    assert _designations_at_or_past_the_bound({just_under}) == set(), just_under

    # And a citation it cannot parse at all is not reported as an over-long designation.
    assert _designations_at_or_past_the_bound({"a" * 200}) == set()
