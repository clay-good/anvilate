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
