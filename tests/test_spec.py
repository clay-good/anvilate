"""Tests for the Design Spec IR, tracking the spec-ir spec scenarios."""

from __future__ import annotations

from pathlib import Path

import pytest

from anvilate.spec import (
    SCHEMA_VERSION,
    AcceptanceCriteria,
    Constraints,
    DesignSpec,
    HolePattern,
    InterfaceContract,
    LoadCase,
    LoadKind,
    Manufacturing,
    ManufacturingProcess,
    MaterialRef,
    Origin,
    Provenanced,
    SpecValidationError,
    StandardComponentInterface,
    ToleranceDimension,
    UnknownReferenceError,
    UnsupportedSchemaVersion,
    ValidationTier,
    dump_spec_yaml,
    json_schema,
    load_spec_yaml,
    parse_spec,
    validate_references,
)
from anvilate.tolerance import FitTolerance, SymmetricTolerance
from anvilate.units import Quantity, UnitSystem


def golden_bracket() -> DesignSpec:
    """The golden-path bracket from the spec-ir scenario, as a typed spec."""
    return DesignSpec(
        name="nema23_bracket",
        description="Aluminum bracket mounting a NEMA 23 stepper to a 4040 extrusion.",
        units=Provenanced.stated(UnitSystem.SI),
        material=MaterialRef(ref="AA-6061-T6"),
        manufacturing=Manufacturing(
            process=ManufacturingProcess.CNC_MILLING,
            tolerance_class="medium",
        ),
        interfaces=[
            StandardComponentInterface(ref="NEMA23", tag="motor_pilot_bore"),
            StandardComponentInterface(ref="EXT-4040", tag="extrusion_mount_face"),
        ],
        load_cases=[
            LoadCase(
                name="cantilevered_motor",
                kind=LoadKind.REMOTE_MASS,
                applied_to="motor_pilot_bore",
                remote_mass=Quantity.parse("1.1 kg"),
            ),
        ],
        constraints=Constraints(
            max_mass=Provenanced.stated(Quantity.parse("150 g")),
            min_safety_factor=Provenanced.stated(2.0),
        ),
        acceptance=AcceptanceCriteria(
            tiers=[ValidationTier.T0_GEOMETRY, ValidationTier.T1_ANALYTICAL],
        ),
    )


# --- Requirement: Complete engineering intent coverage (golden-path bracket) ---


def test_golden_bracket_every_fact_has_a_typed_field():
    spec = golden_bracket()
    assert spec.material.ref == "AA-6061-T6"
    assert spec.manufacturing.process is ManufacturingProcess.CNC_MILLING
    assert {i.ref for i in spec.interfaces} == {"NEMA23", "EXT-4040"}
    assert spec.load_cases[0].remote_mass.has_dimension("[mass]")
    assert spec.constraints.max_mass.value.to("g").magnitude == pytest.approx(150)
    assert spec.constraints.min_safety_factor.value == 2.0
    assert ValidationTier.T1_ANALYTICAL in spec.acceptance.tiers


# --- Requirement: Typed, schema-validated document ---


def test_valid_spec_round_trips_through_yaml():
    spec = golden_bracket()
    text = dump_spec_yaml(spec)
    reloaded = load_spec_yaml(text)
    assert reloaded == spec


def test_unknown_key_rejected_with_path():
    data = dump_and_load_dict(golden_bracket())
    data["manufacturing"]["bogus_field"] = 1
    with pytest.raises(SpecValidationError) as exc:
        parse_spec(data)
    assert any("manufacturing" in e["loc"] for e in exc.value.errors)


def test_units_inconsistency_rejected_with_path():
    data = dump_and_load_dict(golden_bracket())
    # A mass constraint given a length quantity must be rejected.
    data["constraints"]["max_mass"]["value"] = {"magnitude": 10, "unit": "mm"}
    with pytest.raises(SpecValidationError) as exc:
        parse_spec(data)
    assert any("max_mass" in e["loc"] for e in exc.value.errors)


# --- Requirement: References resolve against curated databases ---


def test_known_references_resolve():
    validate_references(golden_bracket())  # does not raise


def test_unknown_material_rejected_with_suggestions():
    spec = golden_bracket().model_copy(update={"material": MaterialRef(ref="AA-6061-T7")})
    with pytest.raises(UnknownReferenceError) as exc:
        validate_references(spec)
    assert "AA-6061-T6" in exc.value.suggestions


def test_unknown_component_rejected():
    spec = golden_bracket().model_copy(
        update={"interfaces": [StandardComponentInterface(ref="NEMA99", tag="bore")]}
    )
    with pytest.raises(UnknownReferenceError):
        validate_references(spec)


# --- Requirement: Assumption provenance ---


def test_default_requires_rationale():
    ok = Provenanced.default(2.0, rationale="standard screening default; edit to override")
    assert ok.origin is Origin.DEFAULT
    with pytest.raises(ValueError):
        Provenanced(value=2.0, origin=Origin.DEFAULT)  # no rationale


def test_provenance_survives_serialization():
    spec = golden_bracket().model_copy(
        update={
            "constraints": Constraints(
                min_safety_factor=Provenanced.default(
                    2.0, rationale="standard screening default; edit to override"
                )
            )
        }
    )
    reloaded = load_spec_yaml(dump_spec_yaml(spec))
    sf = reloaded.constraints.min_safety_factor
    assert sf.origin is Origin.DEFAULT
    assert "screening" in sf.rationale


# --- Requirement: Reproducible and diffable ---


def test_single_constraint_change_is_a_minimal_diff():
    a = dump_spec_yaml(golden_bracket())
    changed = golden_bracket()
    changed.constraints.max_mass = Provenanced.stated(Quantity.parse("170 g"))
    b = dump_spec_yaml(changed)
    diff_lines = [line for line in _line_diff(a, b) if line.startswith(("+", "-"))]
    # Only the magnitude line changed (150 -> 170).
    assert any("170" in line for line in diff_lines)
    assert not any("min_safety_factor" in line for line in diff_lines if line.startswith("-"))


# --- Requirement: Schema versioning and migration ---


def test_current_version_stamped():
    assert golden_bracket().anvilate_spec == SCHEMA_VERSION


def test_unsupported_major_version_refused():
    data = dump_and_load_dict(golden_bracket())
    data["anvilate_spec"] = "2.0.0"
    with pytest.raises(UnsupportedSchemaVersion):
        parse_spec(data)


def test_older_minor_version_loads():
    data = dump_and_load_dict(golden_bracket())
    data["anvilate_spec"] = "1.0.0"  # same major; loads and re-stamps current
    spec = parse_spec(data)
    assert spec.anvilate_spec == SCHEMA_VERSION


# --- JSON Schema surface ---


def test_json_schema_generates():
    schema = json_schema()
    assert schema["title"] == "DesignSpec"
    assert "material" in schema["properties"]


# --- Interface contracts publishable ---


def test_interface_contract_publishable():
    spec = golden_bracket().model_copy(
        update={
            "exports": [
                InterfaceContract(
                    name="mount_pattern",
                    mating_plane="extrusion_mount_face",
                    pattern=HolePattern(
                        diameter=Quantity.parse("40 mm"),
                        hole_count=4,
                        hole_size=Quantity.parse("5 mm"),
                    ),
                )
            ]
        }
    )
    reloaded = load_spec_yaml(dump_spec_yaml(spec))
    assert reloaded.exports[0].name == "mount_pattern"


# --- Requirement: Typed explicit tolerances and fits on the IR ---


def test_spec_carries_typed_toleranced_dimensions():
    # A spec declares explicit per-dimension tolerances as typed fields; each
    # resolves to the common band the drawing and DFM layers read.
    spec = golden_bracket().model_copy(
        update={
            "dimensions": [
                ToleranceDimension(
                    tag="motor_pilot_bore",
                    nominal=Quantity.parse("22 mm"),
                    tolerance=FitTolerance(designation="H7"),
                ),
                ToleranceDimension(
                    tag="mount_face_thickness",
                    nominal=Quantity.parse("6 mm"),
                    tolerance=SymmetricTolerance(plus_minus=Quantity.parse("0.1 mm")),
                ),
            ]
        }
    )
    # The fit resolves through the encoded ISO 286 tables, with its citation.
    bore = spec.dimensions[0].resolve()
    assert bore.label == "H7"
    assert bore.source is not None
    assert bore.lower.to("mm").magnitude == pytest.approx(0.0)
    # The symmetric band resolves to ±0.1 mm.
    face = spec.dimensions[1].resolve()
    assert face.upper.to("mm").magnitude == pytest.approx(0.1)
    assert face.lower.to("mm").magnitude == pytest.approx(-0.1)


def test_toleranced_dimensions_round_trip_through_yaml():
    spec = golden_bracket().model_copy(
        update={
            "dimensions": [
                ToleranceDimension(
                    tag="motor_pilot_bore",
                    nominal=Quantity.parse("22 mm"),
                    tolerance=FitTolerance(designation="H7"),
                ),
            ]
        }
    )
    reloaded = load_spec_yaml(dump_spec_yaml(spec))
    assert reloaded == spec
    assert isinstance(reloaded.dimensions[0].tolerance, FitTolerance)


def test_toleranced_dimension_rejects_unknown_key():
    data = dump_and_load_dict(
        golden_bracket().model_copy(
            update={
                "dimensions": [
                    ToleranceDimension(
                        tag="motor_pilot_bore",
                        nominal=Quantity.parse("22 mm"),
                        tolerance=FitTolerance(designation="H7"),
                    ),
                ]
            }
        )
    )
    data["dimensions"][0]["bogus"] = 1
    with pytest.raises(SpecValidationError) as exc:
        parse_spec(data)
    assert any("dimensions" in e["loc"] for e in exc.value.errors)


def test_toleranced_dimension_rejects_non_length_nominal():
    with pytest.raises(Exception, match="length"):
        ToleranceDimension(
            tag="bad",
            nominal=Quantity.parse("22 kg"),
            tolerance=FitTolerance(designation="H7"),
        )


# --- Committed example stays loadable ---


def test_example_spec_file_loads_and_resolves():
    path = Path(__file__).resolve().parent.parent / "examples" / "nema23_bracket.spec.yaml"
    spec = load_spec_yaml(path.read_text())
    validate_references(spec)
    assert spec.name == "nema23_bracket"
    assert spec.anvilate_spec == SCHEMA_VERSION


# --- helpers ---


def dump_and_load_dict(spec: DesignSpec) -> dict:
    import yaml

    return yaml.safe_load(dump_spec_yaml(spec))


def _line_diff(a: str, b: str) -> list[str]:
    import difflib

    return list(difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm=""))
