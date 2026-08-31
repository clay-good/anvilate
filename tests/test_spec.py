"""Tests for the Design Spec IR, tracking the spec-ir spec scenarios."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from anvilate.spec import (
    SCHEMA_VERSION,
    AcceptanceCriteria,
    ChainAnalysis,
    ChainLink,
    Constraints,
    DesignSpec,
    DimensionChain,
    GeometricCharacteristic,
    GeometricTolerance,
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
from anvilate.tolerance import FitTolerance, SymmetricTolerance, ToleranceClass
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


def test_static_load_case_requires_a_force():
    with pytest.raises(ValidationError, match="needs a force"):
        LoadCase(name="tip_push", kind=LoadKind.STATIC, applied_to="tip")


def test_quasi_static_load_case_requires_force_and_factor():
    # Force present but no factor is still incomplete.
    with pytest.raises(ValidationError, match="quasi_static_factor"):
        LoadCase(
            name="shock",
            kind=LoadKind.QUASI_STATIC,
            applied_to="tip",
            force=Quantity.parse("50 N"),
        )
    # Both present is well-formed.
    ok = LoadCase(
        name="shock",
        kind=LoadKind.QUASI_STATIC,
        applied_to="tip",
        force=Quantity.parse("50 N"),
        quasi_static_factor=2.5,
    )
    assert ok.quasi_static_factor == 2.5


def test_remote_mass_load_case_requires_a_mass():
    with pytest.raises(ValidationError, match="needs a remote_mass"):
        LoadCase(name="motor", kind=LoadKind.REMOTE_MASS, applied_to="bore")


def test_combination_loads_aggregates_classified_cases_for_the_engine():
    from anvilate.loads import LoadNature, asce7_lrfd_basic

    def _case(name, nature, force):
        return LoadCase(
            name=name,
            kind=LoadKind.STATIC,
            applied_to="deck",
            force=Quantity.parse(force),
            nature=nature,
        )

    spec = golden_bracket().model_copy(
        update={
            "load_cases": [
                _case("self_weight", LoadNature.DEAD, "10 kN"),
                _case("dead_equipment", LoadNature.DEAD, "10 kN"),  # summed with the above
                _case("occupancy", LoadNature.LIVE, "50 kN"),
                _case("wind_uplift", LoadNature.WIND, "-40 kN"),
                # An unclassified case is not part of any combination.
                LoadCase(
                    name="handling",
                    kind=LoadKind.STATIC,
                    applied_to="tip",
                    force=Quantity.parse("5 kN"),
                ),
            ]
        }
    )
    loads = spec.combination_loads()
    assert loads[LoadNature.DEAD] == pytest.approx(20_000.0)  # 10 + 10 kN, in N
    assert loads[LoadNature.LIVE] == pytest.approx(50_000.0)
    assert loads[LoadNature.WIND] == pytest.approx(-40_000.0)  # sign carries through
    assert LoadNature.SNOW not in loads  # not declared

    # The mapping feeds the combination engine directly — the whole point.
    governing, _ = asce7_lrfd_basic().governing(loads)
    assert governing.name.startswith("LRFD")


def test_combination_basis_resolves_to_its_generator_and_drives_the_flow():
    from anvilate.loads import LoadNature

    # No basis declared -> no combination set (per-case evaluation, as before).
    assert golden_bracket().combination_set() is None

    def _case(name, nature, force):
        return LoadCase(
            name=name,
            kind=LoadKind.STATIC,
            applied_to="deck",
            force=Quantity.parse(force),
            nature=nature,
        )

    spec = golden_bracket().model_copy(
        update={
            "combination_basis": "asce7_lrfd",
            "load_cases": [
                _case("dead", LoadNature.DEAD, "20 kN"),
                _case("live", LoadNature.LIVE, "50 kN"),
            ],
        }
    )
    combos = spec.combination_set()
    assert combos is not None and combos.basis.startswith("ASCE 7-22 LRFD")
    # The spec-driven flow: its own loads through its own declared combination set.
    governing, demand = combos.governing(spec.combination_loads())
    assert governing.name.startswith("LRFD")
    assert demand > 0
    # ASD resolves to the allowable-stress set.
    asd = spec.model_copy(update={"combination_basis": "asce7_asd"}).combination_set()
    assert asd.basis.startswith("ASCE 7-22 ASD")


def test_seismic_combination_basis_resolves_with_its_parameters():
    from anvilate.loads import LoadNature

    base = golden_bracket().model_copy(
        update={
            "load_cases": [
                LoadCase(
                    name="dead",
                    kind=LoadKind.STATIC,
                    applied_to="deck",
                    force=Quantity.parse("60 kN"),
                    nature=LoadNature.DEAD,
                ),
                LoadCase(
                    name="quake",
                    kind=LoadKind.STATIC,
                    applied_to="deck",
                    force=Quantity.parse("180 kN"),
                    nature=LoadNature.SEISMIC,
                ),
            ],
        }
    )
    # A seismic basis needs S_DS declared, or it refuses rather than guessing.
    with pytest.raises(ValueError, match="seismic_design_acceleration"):
        base.model_copy(update={"combination_basis": "asce7_lrfd_seismic"}).combination_set()
    # With S_DS and ρ it resolves to the §2.3.6 seismic set and drives the flow.
    spec = base.model_copy(
        update={
            "combination_basis": "asce7_lrfd_seismic",
            "seismic_design_acceleration": 1.0,
            "seismic_redundancy_factor": 1.3,
        }
    )
    combos = spec.combination_set()
    assert combos is not None and "seismic" in combos.basis.lower()
    governing, _ = combos.governing(spec.combination_loads(), minimize=True)
    assert governing.name.startswith("LRFD 7")  # the reduced-dead reversal case

    # The ASD-seismic dispatch was dead: asce7_asd_seismic is tested directly in test_loads, but
    # the SPEC wiring to it never ran, so returning the LRFD set instead left the suite green --
    # a spec asking for allowable-stress combinations would have silently received strength ones.
    asd = base.model_copy(
        update={
            "combination_basis": "asce7_asd_seismic",
            "seismic_design_acceleration": 0.9,
            "seismic_redundancy_factor": 1.3,
        }
    ).combination_set()
    assert asd is not None
    assert asd.basis == "ASCE 7-22 ASD (seismic)"
    # Ten ASD combinations, not the four LRFD ones -- the count alone separates the two sets.
    names = [c.name for c in asd.combinations]
    assert len(names) == 10
    assert all(name.startswith("ASD") for name in names)
    assert "ASD 8 (+E)" in names and "ASD 8 (-E)" in names


def test_load_case_nature_is_optional_and_classifies_by_asce_symbol():
    from anvilate.loads import LoadNature

    # Unclassified by default — a spec that ignores combinations leaves it None.
    plain = LoadCase(
        name="tip_push", kind=LoadKind.STATIC, applied_to="tip", force=Quantity.parse("50 N")
    )
    assert plain.nature is None
    # A case can be tagged with its load nature for combination factoring.
    wind = LoadCase(
        name="gust",
        kind=LoadKind.STATIC,
        applied_to="face",
        force=Quantity.parse("-40 kN"),
        nature=LoadNature.WIND,
    )
    assert wind.nature is LoadNature.WIND
    # It round-trips through the model dump/validate.
    assert LoadCase.model_validate(wind.model_dump()).nature is LoadNature.WIND


# --- Requirement: General tolerances by default, explicit overrides ---


def test_general_tolerance_class_parsed_from_manufacturing():
    assert golden_bracket().general_tolerance_class() is ToleranceClass.MEDIUM
    coarse = golden_bracket().model_copy(
        update={
            "manufacturing": Manufacturing(
                process=ManufacturingProcess.CNC_MILLING, tolerance_class="c"
            )
        }
    )
    assert coarse.general_tolerance_class() is ToleranceClass.COARSE


def test_general_tolerance_class_defaults_to_medium_when_unstated():
    # A spec that says nothing about tolerances is governed by ISO 2768 medium.
    unstated = golden_bracket().model_copy(
        update={"manufacturing": Manufacturing(process=ManufacturingProcess.CNC_MILLING)}
    )
    assert unstated.general_tolerance_class() is ToleranceClass.MEDIUM


def test_effective_tolerance_falls_back_to_general_class():
    # An untoleranced feature is governed by the spec's general class, resolved at
    # its nominal and carrying the ISO 2768 citation. 35 mm under medium => ±0.3 mm.
    band = golden_bracket().effective_tolerance("untoleranced_face", Quantity.parse("35 mm"))
    assert band.upper.to("mm").magnitude == pytest.approx(0.3)
    assert band.lower.to("mm").magnitude == pytest.approx(-0.3)
    assert band.label == "ISO 2768-m"
    assert band.source and "2768" in band.source


def test_effective_tolerance_explicit_overrides_general():
    # A declared dimension wins over the general class for its tag.
    spec = golden_bracket().model_copy(
        update={
            "dimensions": [
                ToleranceDimension(
                    tag="bore",
                    nominal=Quantity.parse("22 mm"),
                    tolerance=SymmetricTolerance(plus_minus=Quantity.parse("0.05 mm")),
                ),
            ]
        }
    )
    band = spec.effective_tolerance("bore", Quantity.parse("22 mm"))
    assert band.upper.to("mm").magnitude == pytest.approx(0.05)
    assert band.lower.to("mm").magnitude == pytest.approx(-0.05)
    assert band.source is None  # a user-declared ± band cites no standard


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


def test_a_bare_value_is_refused_by_naming_what_to_write():
    """The likeliest spec-authoring mistake, and the answer it used to get.

    `units: SI` is the natural thing to write in a YAML document, and every provenanced
    field in the IR answered it with pydantic's own
    `Input should be a valid dictionary or instance of Provenanced[UnitSystem]` — a Python
    generic reported to somebody holding a YAML file, on `anvilate check` and on the MCP
    `compile_spec` surface alike. The refusal now names the shape to write, the origins
    that are legal, and the one that needs a rationale besides.
    """
    with pytest.raises(ValidationError) as refused:
        DesignSpec(
            name="bracket",
            description="A bracket.",
            units="SI",
            material=MaterialRef(ref="ASTM-A36"),
            manufacturing=Manufacturing(process=ManufacturingProcess.SHEET_METAL),
            acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
        )
    message = str(refused.value)
    assert "origin: user_stated" in message, message
    assert "'SI'" in message, "the refusal does not quote back the value it was handed"
    for origin in Origin:
        assert origin.value in message, f"{origin.value} is legal and the refusal omits it"
    # And it says so without inventing one: a bare value is not silently user_stated.
    assert "not filled in for you" in message


def test_a_bare_value_is_not_quietly_taken_as_user_stated():
    """The other half. Coercing `SI` to `user_stated` would make the document parse and
    would record an origin nobody claimed — the one thing this wrapper exists to prevent."""
    for candidate in ("SI", 2.0, 0, None, ["SI"], UnitSystem.SI):
        with pytest.raises(ValidationError):
            Provenanced[UnitSystem].model_validate(candidate)
    # A mapping and an existing instance both still pass straight through.
    assert Provenanced[float].model_validate({"value": 2.0, "origin": "user_stated"}).value == 2.0
    stated = Provenanced.stated(UnitSystem.SI)
    assert Provenanced[UnitSystem].model_validate(stated) == stated


def test_the_cli_page_shows_a_provenanced_value_the_parser_accepts():
    """`docs/headless-cli.md` prints the wrong form beside the right one. The right one is
    the line a reader copies, so it is loaded and validated rather than read."""
    import re

    import yaml

    page = (Path(__file__).resolve().parent.parent / "docs" / "headless-cli.md").read_text()
    block = re.search(r"```yaml\n(.*?)```", page, re.S)
    assert block is not None, "the provenanced-value block on headless-cli.md has moved"
    # The block shows `units:` twice — the bare form first, the correct one second — and
    # PyYAML keeps the last, which is the one under test.
    shown = yaml.safe_load(block.group(1))
    assert set(shown) == {"units"}, shown
    loaded = Provenanced[UnitSystem].model_validate(shown["units"])
    assert loaded.value is UnitSystem.SI
    assert loaded.origin is Origin.USER_STATED
    # And the form the page calls wrong really is refused, so the contrast it draws is real.
    with pytest.raises(ValidationError):
        Provenanced[UnitSystem].model_validate("SI")


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


def test_hole_pattern_rejects_non_positive_dimensions():
    # A bolt-circle diameter or hole size of zero/negative is not real geometry.
    with pytest.raises(ValidationError, match="hole-pattern hole_size must be positive"):
        HolePattern(
            diameter=Quantity.parse("40 mm"),
            hole_count=4,
            hole_size=Quantity.parse("0 mm"),
        )
    with pytest.raises(ValidationError, match="hole-pattern diameter must be positive"):
        HolePattern(
            diameter=Quantity.parse("-40 mm"),
            hole_count=4,
            hole_size=Quantity.parse("5 mm"),
        )


def test_envelope_rejects_non_positive_extent():
    from anvilate.spec import Envelope

    with pytest.raises(ValidationError, match="envelope z extent must be positive"):
        Envelope(x=Quantity.parse("50 mm"), y=Quantity.parse("50 mm"), z=Quantity.parse("0 mm"))


def test_acceptance_criteria_rejects_duplicate_tiers():
    with pytest.raises(ValidationError, match="tiers must be unique"):
        AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL, ValidationTier.T1_ANALYTICAL])


def test_acceptance_criteria_rejects_non_positive_max_displacement():
    with pytest.raises(ValidationError, match="max_displacement must be positive"):
        AcceptanceCriteria(
            tiers=[ValidationTier.T3_FEA],
            max_displacement=Quantity.parse("0 mm"),
        )


def test_constraints_reject_nonsensical_bounds():
    # A non-positive safety factor, mass budget, or cost cap is not a satisfiable
    # constraint — reject it at construction.
    with pytest.raises(ValidationError, match="min_safety_factor must be positive"):
        Constraints(min_safety_factor=Provenanced.stated(-1.0))
    with pytest.raises(ValidationError, match="max_mass must be positive"):
        Constraints(max_mass=Provenanced.stated(Quantity.parse("0 g")))
    with pytest.raises(ValidationError, match="max_cost must be positive"):
        Constraints(max_cost=Provenanced.stated(0.0))


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


def test_check_tolerances_manufacturable_flags_the_unachievable_ones():
    # Scenario: a tolerance tighter than the CNC-milling floor (0.05 mm band) is
    # flagged; a looser one passes. The screen is keyed by dimension tag.
    spec = golden_bracket().model_copy(
        update={
            "dimensions": [
                ToleranceDimension(
                    tag="loose_slot",
                    nominal=Quantity.parse("20 mm"),
                    tolerance=SymmetricTolerance(plus_minus=Quantity.parse("0.1 mm")),
                ),
                ToleranceDimension(
                    tag="press_seat",
                    nominal=Quantity.parse("10 mm"),
                    tolerance=SymmetricTolerance(plus_minus=Quantity.parse("0.01 mm")),
                ),
            ]
        }
    )
    checks = spec.check_tolerances_manufacturable()
    assert set(checks) == {"loose_slot", "press_seat"}
    assert checks["loose_slot"].achievable is True
    assert checks["press_seat"].achievable is False
    # The scorecard failures are the un-achievable tags.
    failures = {tag for tag, c in checks.items() if not c.achievable}
    assert failures == {"press_seat"}


def test_check_tolerances_manufacturable_empty_without_declarations():
    # No explicit tolerances declared → nothing to screen.
    assert golden_bracket().check_tolerances_manufacturable() == {}


def test_suggest_processes_for_tight_tolerances_completes_the_dfm_scenario():
    # Scenario: an unachievable milling tolerance suggests changing the process.
    # A ±0.01 mm (0.02 band) press seat can't be milled but the finishing floors
    # hold it; a ±0.1 mm slot is fine on milling and so raises no suggestion.
    spec = golden_bracket().model_copy(
        update={
            "dimensions": [
                ToleranceDimension(
                    tag="loose_slot",
                    nominal=Quantity.parse("20 mm"),
                    tolerance=SymmetricTolerance(plus_minus=Quantity.parse("0.1 mm")),
                ),
                ToleranceDimension(
                    tag="press_seat",
                    nominal=Quantity.parse("10 mm"),
                    tolerance=SymmetricTolerance(plus_minus=Quantity.parse("0.01 mm")),
                ),
            ]
        }
    )
    suggestions = spec.suggest_processes_for_tight_tolerances()
    # Only the failing tag appears; the achievable one raises no suggestion.
    assert set(suggestions) == {"press_seat"}
    holders = suggestions["press_seat"]
    assert set(holders) == {"reaming", "grinding", "wire_edm"}
    assert "cnc_milling" not in holders  # the already-declared process is excluded


def test_suggest_processes_empty_when_tolerance_needs_relaxing():
    # A ±0.001 mm (0.002 band) tolerance is below every process floor: the empty
    # suggestion list means "relax the tolerance", the scenario's other branch.
    spec = golden_bracket().model_copy(
        update={
            "dimensions": [
                ToleranceDimension(
                    tag="impossible",
                    nominal=Quantity.parse("10 mm"),
                    tolerance=SymmetricTolerance(plus_minus=Quantity.parse("0.001 mm")),
                ),
            ]
        }
    )
    suggestions = spec.suggest_processes_for_tight_tolerances()
    assert suggestions == {"impossible": []}


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


def test_chain_predict_yield_scores_against_requirement():
    spec = _bracket_with_chain()
    chain = spec.chains[0]
    # Worst-case gap [0.20, 0.40] sits well inside 0.1-0.5 mm: ~all pass.
    assert chain.predict_yield(spec.dimensions, 20000, seed=4) == pytest.approx(1.0, abs=1e-3)
    # Tighten the floor above the mean gap and only part of the run passes.
    tight = chain.model_copy(update={"required_min": Quantity.parse("0.30 mm")})
    partial = tight.predict_yield(spec.dimensions, 20000, seed=4)
    assert 0.4 < partial < 0.6


def test_chain_predict_yield_rejects_unknown_dimension_tag():
    spec = _bracket_with_chain()
    broken = spec.chains[0].model_copy(
        update={"links": [ChainLink(dimension="does_not_exist", direction=1)]}
    )
    with pytest.raises(KeyError, match="does_not_exist"):
        broken.predict_yield(spec.dimensions, 100, seed=0)


def test_spec_analyze_chains_rolls_up_every_declared_chain():
    spec = _bracket_with_chain()
    analyses = spec.analyze_chains()
    assert [a.name for a in analyses] == ["motor_seat_gap"]
    assert all(isinstance(a, ChainAnalysis) for a in analyses)
    assert analyses[0].passes is True
    # A spec with no chains rolls up to an empty list, not an error.
    assert spec.model_copy(update={"chains": []}).analyze_chains() == []


def test_chain_rejects_inverted_required_band():
    # An inverted clearance band (max below min) is nonsensical and is rejected
    # at construction, naming the chain — no silently-unsatisfiable requirement.
    with pytest.raises(ValidationError, match="required_max"):
        DimensionChain(
            name="bad_gap",
            links=[ChainLink(dimension="mount_face", direction=1)],
            required_min=Quantity.parse("0.5 mm"),
            required_max=Quantity.parse("0.1 mm"),
        )


def test_chain_round_trips_through_yaml():
    spec = _bracket_with_chain()
    reloaded = load_spec_yaml(dump_spec_yaml(spec))
    assert reloaded == spec
    assert reloaded.chains[0].links[1].direction == -1


def test_geometric_tolerance_position_with_datums():
    # Scenario: a position tolerance on the mating hole pattern references datums.
    gt = GeometricTolerance(
        characteristic=GeometricCharacteristic.POSITION,
        tolerance=Quantity.parse("0.1 mm"),
        feature="mounting_holes",
        datums=["A", "B", "C"],
        diametral=True,
    )
    assert gt.datums == ["A", "B", "C"]
    assert "⌀" in str(gt)
    assert "A|B|C" in str(gt)


def test_flatness_rejects_datum_reference():
    # Flatness is a form control and references no datum.
    with pytest.raises(ValidationError, match="form control"):
        GeometricTolerance(
            characteristic=GeometricCharacteristic.FLATNESS,
            tolerance=Quantity.parse("0.05 mm"),
            feature="base_face",
            datums=["A"],
        )


def test_perpendicularity_requires_a_datum():
    with pytest.raises(ValidationError, match="requires at least one datum"):
        GeometricTolerance(
            characteristic=GeometricCharacteristic.PERPENDICULARITY,
            tolerance=Quantity.parse("0.05 mm"),
            feature="side_wall",
        )


def test_cylindricity_is_a_form_control_rejecting_datums():
    # Cylindricity, like flatness, controls form and references no datum.
    gt = GeometricTolerance(
        characteristic=GeometricCharacteristic.CYLINDRICITY,
        tolerance=Quantity.parse("0.02 mm"),
        feature="shaft_journal",
    )
    assert not gt.datums
    with pytest.raises(ValidationError, match="form control"):
        GeometricTolerance(
            characteristic=GeometricCharacteristic.CYLINDRICITY,
            tolerance=Quantity.parse("0.02 mm"),
            feature="shaft_journal",
            datums=["A"],
        )


def test_runout_controls_require_a_datum_axis():
    # Circular and total runout are referenced to a datum axis (a rotating part).
    for characteristic in (
        GeometricCharacteristic.CIRCULAR_RUNOUT,
        GeometricCharacteristic.TOTAL_RUNOUT,
    ):
        ok = GeometricTolerance(
            characteristic=characteristic,
            tolerance=Quantity.parse("0.02 mm"),
            feature="shaft_journal",
            datums=["A"],
        )
        assert ok.datums == ["A"]
        with pytest.raises(ValidationError, match="requires at least one datum"):
            GeometricTolerance(
                characteristic=characteristic,
                tolerance=Quantity.parse("0.02 mm"),
                feature="shaft_journal",
            )


def test_parallelism_and_angularity_require_a_datum():
    # Both are orientation controls: legal with a datum, rejected without one.
    for characteristic in (
        GeometricCharacteristic.PARALLELISM,
        GeometricCharacteristic.ANGULARITY,
    ):
        ok = GeometricTolerance(
            characteristic=characteristic,
            tolerance=Quantity.parse("0.1 mm"),
            feature="top_face",
            datums=["A"],
        )
        assert ok.datums == ["A"]
        with pytest.raises(ValidationError, match="requires at least one datum"):
            GeometricTolerance(
                characteristic=characteristic,
                tolerance=Quantity.parse("0.1 mm"),
                feature="top_face",
            )


def test_geometric_tolerance_rejects_repeated_datum():
    # A datum letter is referenced at most once in a feature control frame.
    with pytest.raises(ValidationError, match="repeats"):
        GeometricTolerance(
            characteristic=GeometricCharacteristic.POSITION,
            tolerance=Quantity.parse("0.1 mm"),
            feature="mounting_holes",
            datums=["A", "B", "A"],
        )


def test_geometric_tolerance_rejects_non_positive_zone():
    with pytest.raises(ValidationError, match="must be positive"):
        GeometricTolerance(
            characteristic=GeometricCharacteristic.FLATNESS,
            tolerance=Quantity.parse("0 mm"),
            feature="base_face",
        )


def test_geometric_tolerances_round_trip_through_yaml():
    spec = _bracket_with_chain().model_copy(
        update={
            "geometric_tolerances": [
                GeometricTolerance(
                    characteristic=GeometricCharacteristic.PERPENDICULARITY,
                    tolerance=Quantity.parse("0.05 mm"),
                    feature="pilot_seat",
                    datums=["A"],
                )
            ]
        }
    )
    reloaded = load_spec_yaml(dump_spec_yaml(spec))
    assert reloaded == spec
    assert reloaded.geometric_tolerances[0].characteristic is (
        GeometricCharacteristic.PERPENDICULARITY
    )


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


def test_combination_loads_applies_the_quasi_static_factor():
    """The factor the schema forces a quasi-static case to declare was never read.

    ``combination_loads`` summed the raw force, so a declared dynamic amplification was
    discarded and the demand came out low by exactly that factor -- turning a genuine
    FAIL into a PASS with no sign that anything had been dropped.
    """
    from anvilate.loads import LoadNature

    spec = golden_bracket().model_copy(
        update={
            "combination_basis": "asce7_lrfd",
            "load_cases": [
                LoadCase(
                    name="shock",
                    kind=LoadKind.QUASI_STATIC,
                    applied_to="tip",
                    force=Quantity.parse("1 kN"),
                    quasi_static_factor=3.0,
                    nature=LoadNature.LIVE,
                ),
                LoadCase(
                    name="self_weight",
                    kind=LoadKind.STATIC,
                    applied_to="tip",
                    force=Quantity.parse("400 N"),
                    nature=LoadNature.DEAD,
                ),
            ],
        }
    )
    loads = spec.combination_loads()
    assert loads[LoadNature.LIVE] == pytest.approx(3000.0)  # 1 kN x 3.0, not 1 kN
    assert loads[LoadNature.DEAD] == pytest.approx(400.0)  # a static case is untouched


def test_unclassified_force_cases_names_what_the_combination_engine_cannot_see():
    """The list `combination_loads()` skips, made visible so somebody has to look at it.

    A combination treats a nature nobody supplied as zero, so a forgotten classification
    is a smaller demand and a comfortable pass. A case with no force is not listed: it has
    nothing to contribute to a factored sum.
    """
    from anvilate.loads import LoadNature

    spec = golden_bracket().model_copy(
        update={
            "load_cases": [
                LoadCase(
                    name="self_weight",
                    kind=LoadKind.STATIC,
                    applied_to="deck",
                    force=Quantity.parse("10 kN"),
                    nature=LoadNature.DEAD,
                ),
                LoadCase(
                    name="lateral_thrust",
                    kind=LoadKind.STATIC,
                    applied_to="deck",
                    force=Quantity.parse("200 kN"),
                ),
                LoadCase(
                    name="motor",
                    kind=LoadKind.REMOTE_MASS,
                    applied_to="bore",
                    remote_mass=Quantity.parse("12 kg"),
                ),
            ]
        }
    )
    assert spec.unclassified_force_cases() == ("lateral_thrust",)
    # And the reason it matters: the aggregated mapping is missing 200 kN of it.
    assert sum(spec.combination_loads().values()) == pytest.approx(10_000.0)


def test_a_fully_classified_spec_has_nothing_unclassified():
    from anvilate.loads import LoadNature

    spec = golden_bracket().model_copy(
        update={
            "load_cases": [
                LoadCase(
                    name="self_weight",
                    kind=LoadKind.STATIC,
                    applied_to="deck",
                    force=Quantity.parse("10 kN"),
                    nature=LoadNature.DEAD,
                )
            ]
        }
    )
    assert spec.unclassified_force_cases() == ()


def test_the_specs_own_combination_evidence_cannot_forget_the_unclassified_cases():
    """The short path is the safe one, which is why it exists.

    Building the evidence from the mapping directly leaves the unclassified list to the
    caller — and a caller who forgets it gets a green record over a demand that never saw
    the missing load.
    """
    from anvilate.loads import LoadNature, combination_evidence
    from anvilate.scorecard import CheckStatus

    spec = golden_bracket().model_copy(
        update={
            "combination_basis": "asce7_lrfd",
            "load_cases": [
                LoadCase(
                    name="self_weight",
                    kind=LoadKind.STATIC,
                    applied_to="deck",
                    force=Quantity.parse("10 kN"),
                    nature=LoadNature.DEAD,
                ),
                LoadCase(
                    name="lateral_thrust",
                    kind=LoadKind.STATIC,
                    applied_to="deck",
                    force=Quantity.parse("200 kN"),
                ),
            ],
        }
    )
    safe = spec.combination_evidence()
    assert safe is not None
    assert safe.status is CheckStatus.NOT_EVALUATED
    assert safe.unclassified == ("lateral_thrust",)

    forgotten = combination_evidence(spec.combination_set(), spec.combination_loads())
    assert forgotten.status is CheckStatus.PASS, "the mistake the short path removes"


def test_a_spec_with_no_combination_basis_has_no_combination_evidence():
    assert golden_bracket().combination_evidence() is None
