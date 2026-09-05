"""The last of the renderings nothing in the suite had ever read.

`docs/api/unrendered-strings.txt` was a ratchet over the classes that write their own
`__str__` and that no test ever called. It started at 80 and this file pays off the
remainder — the ones that need a constructed object rather than an enum member, which is
why they outlived the 57 that fell to a property sweep in `tests/test_contract.py`.

The defect family is always the same: a rendering that **drops the field distinguishing
two objects from each other**. `BTH1Allowables` carried five allowable stresses and
printed three. So the question asked of each fixture here is not "does it look right" but
"is there a field I can change without the reader seeing it change" — and every field for
which the answer is yes has to be named in `_SUMMARISED` with the reason it is a working
number rather than an answer. Two were not summaries and are fixed:

* a beam result printed σ_max and δ_max and not `max_moment`, which its own docstring
  calls "the number a reviewer checks first";
* a riveted joint printed an efficiency and the mode that governs and not
  `joint_strength` — the load the joint actually carries, so two joints a factor of ten
  apart in capacity rendered identically.
"""

from __future__ import annotations

import enum

import pytest

from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _fixtures() -> dict[str, object]:
    """One constructed instance per debt entry, built through the real producers.

    Built through the producers and not by keyword, because a rendering read against a
    hand-written object only says the format string is self-consistent. Two classes appear
    twice: `NozzleReinforcement` and `BranchReinforcement` print `deficit` only on the
    inadequate branch, and a fixture that is always adequate would have the sweep below
    excuse a field that is rendered.
    """
    from anvilate.agenteval import ToolCall
    from anvilate.analysis.aluminum import (
        AlloyProperties,
        EdgeSupport,
        TemperGroup,
        aluminum_compression_strength,
    )
    from anvilate.analysis.beam import cantilever_end_load
    from anvilate.analysis.cold_formed_steel import ElasticBuckling, dsm_compression_strength
    from anvilate.analysis.embodied_carbon import (
        CarbonFactor,
        ModuleScope,
        carbon_contribution,
        embodied_carbon_estimate,
    )
    from anvilate.analysis.interference import interference_fit
    from anvilate.analysis.pressure_vessel import (
        asme_appendix_2_flange_moments,
        asme_appendix_2_shape_factors,
        asme_b313_branch_reinforcement,
        asme_ug37_nozzle_reinforcement,
        thick_wall_sphere,
        thin_wall_cylinder,
    )
    from anvilate.analysis.rivet import riveted_joint_efficiency
    from anvilate.analysis.stress import combine_axial_bending
    from anvilate.callouts import CalloutSet, FreeTextNote
    from anvilate.derivation import DerivationAbsence, Underived
    from anvilate.standards.fatigue import WeldDetailCategory, WeldStressKind
    from anvilate.tolerance.explicit import SymmetricTolerance
    from anvilate.tolerance.general import general_tolerance
    from anvilate.tolerance.iso286 import standard_tolerance

    heat_affected = AlloyProperties(
        name="6061-T6 (weld-affected)",
        compressive_yield=_q("103 MPa"),
        tensile_yield=_q("103 MPa"),
        tensile_ultimate=_q("165 MPa"),
        elastic_modulus=_q("70000 MPa"),
        temper_group=TemperGroup.ARTIFICIALLY_AGED,
        source="ADM Table A.3.5, read by the user",
    )
    alloy = AlloyProperties(
        name="6061-T6",
        compressive_yield=_q("241 MPa"),
        tensile_yield=_q("241 MPa"),
        tensile_ultimate=_q("262 MPa"),
        elastic_modulus=_q("70000 MPa"),
        temper_group=TemperGroup.ARTIFICIALLY_AGED,
        source="ADM Table A.3.4, read by the user",
        weld_affected=heat_affected,
    )
    factor = CarbonFactor(
        material="steel, hot-rolled section",
        value=1.55,
        scope=ModuleScope.A1_A3,
        source="generic federal dataset, cited by the engineer of record",
        band_low=0.75,
        band_high=1.50,
    )
    note = FreeTextNote(text="break all sharp edges")

    return {
        "ToolCall": ToolCall(tool="run_validation", failed=True, error="unknown field 'laod'"),
        "AluminumCompressionStrength": aluminum_compression_strength(
            properties=alloy,
            slenderness=60.0,
            flat_width=_q("60 mm"),
            thickness=_q("6 mm"),
            edge_support=EdgeSupport.BOTH_EDGES,
            welded=True,
        ),
        "BeamBendingResult": cantilever_end_load(
            force=_q("5 kN"),
            length=_q("2 m"),
            second_moment=_q("1e7 mm**4"),
            extreme_fibre=_q("100 mm"),
            elastic_modulus=_q("200 GPa"),
        ),
        "DSMStrength": dsm_compression_strength(
            yield_load=_q("300 kN"),
            elastic_buckling=ElasticBuckling(
                local=_q("60 kN"),
                distortional=_q("900 kN"),
                global_=_q("3000 kN"),
                source="CUFSM finite-strip analysis, run 2026-09-02",
            ),
        ),
        "EmbodiedCarbonEstimate": embodied_carbon_estimate(
            [
                carbon_contribution(label="finished part", mass=_q("12 kg"), factor=factor),
                carbon_contribution(label="process loss", mass=_q("22 kg"), factor=factor),
            ]
        ),
        "InterferenceFit": interference_fit(
            radial_interference=_q("0.03 mm"),
            interface_diameter=_q("50 mm"),
            hub_outer_diameter=_q("100 mm"),
            hub_modulus=_q("200 GPa"),
            hub_poisson=0.3,
            shaft_modulus=_q("200 GPa"),
            shaft_poisson=0.3,
        ),
        "BranchReinforcement (adequate)": asme_b313_branch_reinforcement(
            run_outside_diameter=_q("300 mm"),
            run_wall=_q("12 mm"),
            run_pressure_design_thickness=_q("6 mm"),
            branch_outside_diameter=_q("100 mm"),
            branch_wall=_q("8 mm"),
            branch_pressure_design_thickness=_q("3 mm"),
            mechanical_allowance=_q("1 mm"),
        ),
        "BranchReinforcement (short)": asme_b313_branch_reinforcement(
            run_outside_diameter=_q("300 mm"),
            run_wall=_q("7 mm"),
            run_pressure_design_thickness=_q("6 mm"),
            branch_outside_diameter=_q("200 mm"),
            branch_wall=_q("4 mm"),
            branch_pressure_design_thickness=_q("3 mm"),
            mechanical_allowance=_q("0.5 mm"),
        ),
        "FlangeMoments": asme_appendix_2_flange_moments(
            inside_diameter=_q("200 mm"),
            bolt_circle_diameter=_q("300 mm"),
            gasket_diameter=_q("250 mm"),
            pressure=_q("2 MPa"),
            operating_bolt_load=_q("500 kN"),
            seating_bolt_load=_q("600 kN"),
        ),
        "FlangeShapeFactors": asme_appendix_2_shape_factors(
            outside_diameter=_q("400 mm"), inside_diameter=_q("200 mm")
        ),
        "NozzleReinforcement (adequate)": asme_ug37_nozzle_reinforcement(
            shell_thickness=_q("20 mm"),
            shell_required_thickness=_q("10 mm"),
            nozzle_outside_diameter=_q("100 mm"),
            nozzle_thickness=_q("10 mm"),
            nozzle_required_thickness=_q("4 mm"),
            corrosion_allowance=_q("1 mm"),
            weld_leg=_q("6 mm"),
        ),
        "NozzleReinforcement (short)": asme_ug37_nozzle_reinforcement(
            shell_thickness=_q("11 mm"),
            shell_required_thickness=_q("10 mm"),
            nozzle_outside_diameter=_q("300 mm"),
            nozzle_thickness=_q("5 mm"),
            nozzle_required_thickness=_q("4 mm"),
            corrosion_allowance=_q("1 mm"),
            weld_leg=_q("3 mm"),
        ),
        "ThickWallSphereStress": thick_wall_sphere(
            pressure=_q("10 MPa"), radius=_q("100 mm"), wall_thickness=_q("20 mm")
        ),
        "ThinWallStress": thin_wall_cylinder(
            pressure=_q("2 MPa"), radius=_q("500 mm"), wall_thickness=_q("10 mm")
        ),
        "RivetedJointStrength": riveted_joint_efficiency(
            pitch=_q("80 mm"),
            rivet_diameter=_q("20 mm"),
            plate_thickness=_q("10 mm"),
            allowable_tension=_q("120 MPa"),
            allowable_shear=_q("90 MPa"),
            allowable_bearing=_q("200 MPa"),
        ),
        "CombinedNormalStress": combine_axial_bending(
            axial_stress=_q("50 MPa"), bending_stress=_q("80 MPa")
        ),
        "CalloutSet": CalloutSet(callouts=(note,)),
        "FreeTextNote": note,
        "Underived": Underived(
            kind=DerivationAbsence.LOOKUP,
            reason="the allowable is read from a table with no published closed form",
        ),
        "WeldDetailCategory": WeldDetailCategory(
            standard="EN 1993-1-9",
            edition="2005",
            table="Table 8.4",
            description="transverse attachment, L <= 50 mm",
            detail_category=_q("80 MPa"),
            stress_kind=WeldStressKind.NORMAL,
        ),
        "ResolvedTolerance": SymmetricTolerance(plus_minus=_q("0.1 mm")).resolve(_q("35 mm")),
        "GeneralTolerance": general_tolerance(_q("35 mm")),
        "StandardTolerance": standard_tolerance(_q("50 mm"), 7),
    }


_DERIVATION = "the derivation, rendered by `Derivation` and not by this sentence"

# (class qualname, field) -> why the reader does not need to see it move.
#
# Every entry is a claim, and `test_the_summary_table_carries_no_exemption_nothing_needs`
# makes it one that can be wrong: an exemption for a field the rendering *does* reach is
# struck, so this table cannot quietly grow to cover a real omission later.
_SUMMARISED: dict[tuple[str, str], str] = {
    # The three ADM limit states are the working numbers behind `nominal`; the rendering
    # gives the answer and names which state set it. `parent_nominal` and
    # `weld_affected_nominal` are the same screen on each property set, and the rendering
    # says in words which one governed ("in the weld-affected zone").
    ("AluminumCompressionStrength", "yielding"): "a working limit state behind `nominal`",
    ("AluminumCompressionStrength", "local_buckling"): "a working limit state behind `nominal`",
    ("AluminumCompressionStrength", "member_buckling"): "a working limit state behind `nominal`",
    ("AluminumCompressionStrength", "parent_nominal"): "the same screen on the parent metal",
    ("AluminumCompressionStrength", "weld_affected_nominal"): "the same screen on the HAZ",
    ("AluminumCompressionStrength", "elastic_local_buckling"): "the §B.5.6 F_e behind the states",
    ("AluminumCompressionStrength", "local_member_interaction"): (
        "the §E.4 reduction is already in `member_buckling`, so the flag says the check "
        "was made, not what the answer is"
    ),
    ("AluminumCompressionStrength", "governing_formula"): _DERIVATION,
    ("AluminumCompressionStrength", "governing_inputs"): _DERIVATION,
    ("BeamBendingResult", "deflection_formula"): _DERIVATION,
    ("BeamBendingResult", "deflection_inputs"): _DERIVATION,
    ("DSMStrength", "global_strength"): "a working DSM curve behind `nominal`",
    ("DSMStrength", "local_strength"): "a working DSM curve behind `nominal`",
    ("DSMStrength", "distortional_strength"): "a working DSM curve behind `nominal`",
    ("DSMStrength", "governing_formula"): _DERIVATION,
    ("DSMStrength", "governing_inputs"): _DERIVATION,
    ("EmbodiedCarbonEstimate", "contributions"): (
        "the itemised lines the total sums; `dominant` is the one a reader asks for and "
        "it is a line of its own, not a number this sentence can hold"
    ),
    ("BranchReinforcement", "run_excess"): "an area summed into `available`",
    ("BranchReinforcement", "branch_excess"): "an area summed into `available`",
    ("BranchReinforcement", "added"): "an area summed into `available`",
    ("BranchReinforcement", "half_width"): "the reinforcement zone `available` is measured over",
    ("BranchReinforcement", "height"): "the reinforcement zone `available` is measured over",
    ("BranchReinforcement", "zone_limited_by_run"): "which zone bound applied, not the verdict",
    ("NozzleReinforcement", "shell_excess"): "an area summed into `available`",
    ("NozzleReinforcement", "nozzle_excess"): "an area summed into `available`",
    ("NozzleReinforcement", "weld_area"): "an area summed into `available`",
    ("FlangeMoments", "end_force"): "a force the two moments are assembled from",
    ("FlangeMoments", "total_end_force"): "a force the two moments are assembled from",
    ("FlangeMoments", "face_force"): "a force the two moments are assembled from",
    ("FlangeMoments", "gasket_force"): "a force the two moments are assembled from",
    ("FlangeMoments", "end_arm"): "a lever arm the two moments are assembled from",
    ("FlangeMoments", "face_arm"): "a lever arm the two moments are assembled from",
    ("FlangeMoments", "gasket_arm"): "a lever arm the two moments are assembled from",
    ("RivetedJointStrength", "tearing_strength"): "a failure mode `joint_strength` is the least of",
    ("RivetedJointStrength", "shearing_strength"): (
        "a failure mode `joint_strength` is the least of"
    ),
    ("RivetedJointStrength", "crushing_strength"): (
        "a failure mode `joint_strength` is the least of"
    ),
    ("RivetedJointStrength", "solid_plate_strength"): "the denominator of `efficiency`",
    ("FreeTextNote", "kind"): "a Literal that never varies within the class",
    ("FreeTextNote", "sequence"): (
        "what tells two notes of identical text at one scope apart in the characteristic "
        "id; the rendering is the note's words and two notes with the same words say the "
        "same thing"
    ),
    ("GeneralTolerance", "size_range"): "the ISO 2768 row `deviation` was read from",
    ("GeneralTolerance", "source"): "provenance, carried into the citation not the sentence",
    ("StandardTolerance", "size_range"): "the ISO 286 row `width` was read from",
    ("StandardTolerance", "source"): "provenance, carried into the citation not the sentence",
}


def _mutated(value: object) -> object | None:
    """A different value of the same kind, or ``None`` where there is no obvious one."""
    if isinstance(value, Quantity):
        return Quantity(magnitude=value.magnitude * 3.0 + 7.0, unit=value.unit)
    if isinstance(value, bool):
        return not value
    if isinstance(value, enum.Enum):
        others = [member for member in type(value) if member is not value]
        return others[0] if others else None
    if isinstance(value, int):
        return value + 17
    if isinstance(value, float):
        return value * 3.0 + 7.0
    if isinstance(value, str):
        return value + " (mutated)"
    if isinstance(value, tuple):
        return value[:-1] if len(value) > 1 else None
    return None


def _invisible_fields(obj: object) -> set[str]:
    """The fields of ``obj`` a reader cannot see change in its rendering."""
    cls = type(obj)
    carried = {name: getattr(obj, name) for name in cls.model_fields}
    base = str(obj)
    invisible = set()
    for name, value in carried.items():
        replacement = _mutated(value)
        if replacement is None:
            continue
        # `model_construct` and not `model_copy`: the point is to render a value the
        # validators would refuse (a `nominal` that is no longer the smallest of three),
        # because a reader is shown the rendering and not the invariant.
        twin = cls.model_construct(**{**carried, name: replacement})
        if str(twin) == base:
            invisible.add(name)
    return invisible


_FIXTURES = _fixtures()
_CASES = sorted(_FIXTURES)


def _invisible_to_the_class() -> dict[str, set[str]]:
    """Per class, the fields no fixture of it lets the reader see change.

    The union over fixtures and not per fixture: `deficit` is rendered on the inadequate
    branch and is nothing to say on the adequate one, and a field a reader can see in the
    case where it means something is rendered.
    """
    by_class: dict[str, set[str]] = {}
    for obj in _FIXTURES.values():
        qualname = type(obj).__qualname__
        hidden = _invisible_fields(obj)
        by_class[qualname] = by_class[qualname] & hidden if qualname in by_class else hidden
    return by_class


_INVISIBLE = _invisible_to_the_class()


def test_the_debt_list_this_file_pays_off_is_empty_and_the_fixtures_cover_it():
    """The ratchet file is the gate; this asserts the payoff really was the whole list."""
    from pathlib import Path

    listed = [
        line.strip()
        for line in (Path(__file__).resolve().parents[1] / "docs/api/unrendered-strings.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert listed == [], (
        "renderings are recorded as unread again. Pay them off here rather than letting "
        f"the list grow back: {listed}"
    )
    assert len({type(obj).__qualname__ for obj in _FIXTURES.values()}) == 21


@pytest.mark.parametrize("label", _CASES)
def test_a_rendering_nothing_had_read_says_something(label):
    """The floor: it renders, it is not blank, and it leaks no placeholder."""
    rendered = str(_FIXTURES[label])
    assert rendered.strip(), f"{label} renders as blank"
    assert "None" not in rendered, f"{label} renders a placeholder: {rendered!r}"
    assert " object at 0x" not in rendered, f"{label} leaks a default repr: {rendered!r}"


@pytest.mark.parametrize("qualname", sorted(_INVISIBLE))
def test_every_field_a_rendering_carries_reaches_the_reader_or_is_a_declared_summary(qualname):
    """Change one field; the reader has to see it change, or it is a working number.

    This is the BTH-1 question generalised: five allowables carried, three printed, and
    the suite green because nothing rendered the object. Here every field of every debt
    entry is moved in turn and the rendering compared.
    """
    undeclared = {field for field in _INVISIBLE[qualname] if (qualname, field) not in _SUMMARISED}
    assert not undeclared, (
        f"{qualname} carries {sorted(undeclared)} and a reader cannot see them change. "
        "Either render them, or add each to _SUMMARISED with the reason it is a working "
        "number rather than one of this object's answers"
    )


def test_the_summary_table_carries_no_exemption_nothing_needs():
    """An exemption for a field that *is* rendered is struck, so the table cannot rot.

    Without this the table is the escape hatch that lets the next omission be waved
    through: adding a line is cheaper than rendering the field.
    """
    probed = sum(len(type(obj).model_fields) for obj in _FIXTURES.values())
    assert probed >= 100, f"only {probed} fields were probed; the sweep is near empty"

    needed = {(qualname, field) for qualname, fields in _INVISIBLE.items() for field in fields}
    stale = sorted(set(_SUMMARISED) - needed)
    assert not stale, (
        "these are declared as summarised and the rendering reaches them (or the field is "
        f"gone). Strike them from _SUMMARISED: {stale}"
    )


def test_a_beam_result_prints_the_moment_a_reviewer_checks_first():
    """It printed σ_max and δ_max only, and `max_moment` is the third answer it carries.

    Its own docstring calls the moment "the number a reviewer checks first and the one
    that carries into a section-sizing or a connection design". Two cantilevers with the
    same peak stress and deflection and different moments — a different section under a
    different load — rendered as the same line.
    """
    result = _FIXTURES["BeamBendingResult"]
    rendered = str(result)
    assert str(result.max_moment.to("kN*m")) in rendered
    assert str(result.max_bending_stress.to("MPa")) in rendered
    assert str(result.max_deflection.to("mm")) in rendered


def test_a_riveted_joint_prints_the_load_it_carries():
    """Efficiency is a ratio, and it was the only number the rendering had.

    A joint good for 28 kN per pitch and one good for 280 kN rendered identically at the
    same efficiency, which is exactly the ratio's job: it is deliberately independent of
    scale. `joint_strength` is the load, and `governing_mode` names which failure mode
    set it.
    """
    joint = _FIXTURES["RivetedJointStrength"]
    rendered = str(joint)
    assert str(joint.joint_strength.to("kN")) in rendered
    assert joint.governing_mode in rendered
    assert f"{joint.efficiency:.1%}" in rendered
