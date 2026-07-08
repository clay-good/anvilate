"""Tests for the Design Spec IR, tracking the spec-ir spec scenarios."""

from __future__ import annotations

from pathlib import Path

import pytest

from anvilate.spec import (
    SCHEMA_VERSION,
    AcceptanceCriteria,
    ChainAnalysis,
    ChainLink,
    Constraints,
    DesignSpec,
    DimensionChain,
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
    validate_dimension_graph,
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


# --- Requirement: One-dimensional tolerance stack-up over a declared chain ---


def _bracket_with_chain() -> DesignSpec:
    # Scenario: a chain from the mount face (+) through the flange thickness (-)
    # to the motor pilot seat (-), required clearance 0.1-0.5 mm.
    return golden_bracket().model_copy(
        update={
            "dimensions": [
                ToleranceDimension(
                    tag="mount_face",
                    nominal=Quantity.parse("20 mm"),
                    tolerance=SymmetricTolerance(plus_minus=Quantity.parse("0.05 mm")),
                ),
                ToleranceDimension(
                    tag="flange_thickness",
                    nominal=Quantity.parse("12 mm"),
                    tolerance=SymmetricTolerance(plus_minus=Quantity.parse("0.03 mm")),
                ),
                ToleranceDimension(
                    tag="pilot_seat",
                    nominal=Quantity.parse("7.7 mm"),
                    tolerance=SymmetricTolerance(plus_minus=Quantity.parse("0.02 mm")),
                ),
            ],
            "chains": [
                DimensionChain(
                    name="motor_seat_gap",
                    links=[
                        ChainLink(dimension="mount_face", direction=1),
                        ChainLink(dimension="flange_thickness", direction=-1),
                        ChainLink(dimension="pilot_seat", direction=-1),
                    ],
                    required_min=Quantity.parse("0.1 mm"),
                    required_max=Quantity.parse("0.5 mm"),
                ),
            ],
        }
    )


def test_declared_chain_builds_and_analyzes():
    spec = _bracket_with_chain()
    chain = spec.chains[0]
    stack = chain.build(spec.dimensions)

    wc = stack.worst_case()
    assert wc.nominal.to("mm").magnitude == pytest.approx(0.3)
    # Worst-case gap [0.20, 0.40] satisfies the required 0.1-0.5 mm clearance.
    assert wc.satisfies(chain.required_min, chain.required_max) is True
    # Ranked widest-share first — the mount face carries the widest tolerance.
    assert wc.contributions[0].name == "mount_face"


def test_declared_chain_rejects_unknown_dimension_tag():
    spec = _bracket_with_chain()
    broken = spec.chains[0].model_copy(
        update={"links": [ChainLink(dimension="does_not_exist", direction=1)]}
    )
    with pytest.raises(KeyError, match="does_not_exist"):
        broken.build(spec.dimensions)


def test_chain_analyze_reports_ranges_and_pass_fail():
    # Scenario: interface gap stack-up — one call yields both ranges, the pass/fail
    # against the chain's own requirement, and the ranked contributions.
    spec = _bracket_with_chain()
    analysis = spec.chains[0].analyze(spec.dimensions)

    assert isinstance(analysis, ChainAnalysis)
    assert analysis.name == "motor_seat_gap"
    # Worst-case gap [0.20, 0.40] and the tighter RSS gap both fit 0.1-0.5 mm.
    assert analysis.worst_case.nominal.to("mm").magnitude == pytest.approx(0.3)
    assert analysis.worst_case.lower.to("mm").magnitude == pytest.approx(0.20)
    assert analysis.worst_case.upper.to("mm").magnitude == pytest.approx(0.40)
    assert analysis.rss.width.to("mm").magnitude < analysis.worst_case.width.to("mm").magnitude
    assert analysis.worst_case_passes is True
    assert analysis.rss_passes is True
    assert analysis.passes is True
    # Ranked widest-share first — the mount face carries the widest tolerance.
    assert analysis.worst_case.contributions[0].name == "mount_face"


def test_chain_analyze_fails_when_worst_case_violates_requirement():
    # Scenario: stack-up failure — tighten the floor past the worst-case lower
    # bound and the chain fails on worst-case while RSS still fits.
    spec = _bracket_with_chain()
    chain = spec.chains[0].model_copy(update={"required_min": Quantity.parse("0.23 mm")})
    analysis = chain.analyze(spec.dimensions)

    assert analysis.worst_case_passes is False
    assert analysis.passes is False
    # RSS lower bound (~0.238) clears 0.23, so the realistic range still fits.
    assert analysis.rss_passes is True


def test_chain_analyze_str_renders_verdict():
    spec = _bracket_with_chain()
    assert "PASS" in str(spec.chains[0].analyze(spec.dimensions))


def test_chain_analyze_rejects_unknown_dimension_tag():
    spec = _bracket_with_chain()
    broken = spec.chains[0].model_copy(
        update={"links": [ChainLink(dimension="does_not_exist", direction=1)]}
    )
    with pytest.raises(KeyError, match="does_not_exist"):
        broken.analyze(spec.dimensions)


def test_chain_round_trips_through_yaml():
    spec = _bracket_with_chain()
    reloaded = load_spec_yaml(dump_spec_yaml(spec))
    assert reloaded == spec
    assert reloaded.chains[0].links[1].direction == -1


def test_valid_dimension_graph_passes():
    validate_dimension_graph(_bracket_with_chain())  # no raise


def test_dimension_graph_flags_unknown_link_and_duplicates_at_once():
    spec = _bracket_with_chain().model_copy(
        update={
            "dimensions": [
                ToleranceDimension(
                    tag="mount_face",
                    nominal=Quantity.parse("20 mm"),
                    tolerance=SymmetricTolerance(plus_minus=Quantity.parse("0.05 mm")),
                ),
                ToleranceDimension(  # duplicate tag
                    tag="mount_face",
                    nominal=Quantity.parse("21 mm"),
                    tolerance=SymmetricTolerance(plus_minus=Quantity.parse("0.05 mm")),
                ),
            ],
            "chains": [
                DimensionChain(
                    name="motor_seat_gap",
                    links=[ChainLink(dimension="ghost", direction=1)],  # unknown tag
                    required_min=Quantity.parse("0.1 mm"),
                    required_max=Quantity.parse("0.5 mm"),
                ),
            ],
        }
    )
    with pytest.raises(SpecValidationError) as exc:
        validate_dimension_graph(spec)
    locs = [e["loc"] for e in exc.value.errors]
    # Both problems are reported in one pass.
    assert "dimensions.1.tag" in locs
    assert "chains.0.links.0.dimension" in locs


def test_chain_requires_at_least_one_link():
    with pytest.raises(Exception):  # noqa: B017 - pydantic min_length ValidationError
        DimensionChain(
            name="empty",
            links=[],
            required_min=Quantity.parse("0.1 mm"),
            required_max=Quantity.parse("0.5 mm"),
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
