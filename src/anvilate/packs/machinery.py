"""The machinery discipline pack: declare a transmission shaft, get a Shigley scorecard.

The machinery pack serves the machine designer the way :mod:`anvilate.packs.structural`
serves the steel designer. A :class:`TransmissionShaft` declares a solid round shaft's
diameter, the steady bending moment and torque on it, and the material it is cut from;
:func:`screen_shaft` screens the three checks that size a real shaft and that disagree with
each other often enough to be worth running together — static yielding under combined
bending and torsion, torsional windup over the shaft's length, and the fully-reversed
fatigue a *rotating* shaft sees that the static check cannot see at all. Each rolls into a
cited PASS/FAIL entry, no silent green.

**The three checks share one knob and disagree about it.** Static strength goes as d³,
fatigue as d³ against a different allowable, and twist as d⁴ — so which one governs moves
with the shaft's length and its material, and a shaft sized on the static check alone is
routinely the wrong diameter. That is the reason this screen exists as one card rather than
three calls: every failing entry names ``diameter`` and says what value clears *its* limit,
and the largest of them is the shaft.

The loads are the caller's. The screen is Shigley theory on a prismatic solid round shaft
with no stress-concentration factors of its own — a keyway, a fillet or a shoulder is
carried in through the fatigue factors on the endurance limit the caller supplies — and the
engineer of record owns the design.
"""

from __future__ import annotations

from pydantic import ConfigDict

from ..analysis import (
    BALL_BEARING_LIFE_EXPONENT,
    agma_bending_stress,
    agma_contact_stress,
    bearing_equivalent_dynamic_load,
    bearing_equivalent_static_load,
    bearing_life_hours,
    bearing_rating_for_life,
    bearing_static_safety_factor,
    gear_pitch_diameter,
    gear_tangential_load,
    key_bearing_stress,
    key_length_for_torque,
    key_shear_stress,
    minimum_teeth_to_avoid_undercut,
    shaft_diameter_de_goodman,
    shaft_diameter_for_bending_torsion,
    shaft_twist_angle,
    shaft_von_mises_stress,
    spur_gear_contact_ratio,
)
from ..derivation import Derivation, SymbolValue
from ..scorecard import CheckStatus, Direction, RepairHint, Scorecard, ScorecardEntry
from ..units import Quantity
from ._guarded import GuardedInputs

__all__ = [
    "RollingBearing",
    "ShaftKey",
    "SpurGearMesh",
    "TransmissionShaft",
    "screen_gear_mesh",
    "screen_rolling_bearing",
    "screen_shaft",
    "screen_shaft_key",
]

_STATIC_REFERENCE = "Shigley §7-4 shaft design for stress (distortion energy)"
_TWIST_REFERENCE = "Shigley shaft deflection, θ = T·L/(G·J)"
_FATIGUE_REFERENCE = "Shigley Eq. 7-8, DE-Goodman rotating-shaft fatigue"
_BENDING_REFERENCE = "AGMA 2001 / ISO 6336 tooth-root bending stress"
_PITTING_REFERENCE = "AGMA 2001 / ISO 6336 pitting resistance"
_CONTACT_RATIO_REFERENCE = "Shigley, transverse contact ratio for smooth load transfer"
_UNDERCUT_REFERENCE = "Shigley, rack-generation undercut limit N_min = 2·k/sin²φ"
_KEY_SHEAR_REFERENCE = "Shigley, parallel key shear across the width"
_KEY_BEARING_REFERENCE = "Shigley, parallel key side bearing on the half height"
# Cited to the textbook, deliberately, and it is worth saying why rather than leaving the
# next reader to wonder. The two rules are ISO 281's and ISO 76's, and `analysis/bearing.py`
# records that provenance in its own docstrings. A scorecard entry naming a normative
# standard has to name its EDITION (docs/standards-effectivity.md), and nothing in this
# repository identifies which edition of either these forms came out of: L10 = (C/P)^p with
# p = 3 and 10/3, and s₀ = C₀/P₀, are unchanged across their editions. Inventing one would
# manufacture exactly the confidently-wrong citation that ratchet exists to prevent, so the
# entry cites the book the closed form is actually taken from, which is complete as it
# stands. Reading the standards is how these become ISO citations.
_BEARING_LIFE_REFERENCE = "Shigley, rolling-bearing rating life L10 = (C/P)^p"
_BEARING_STATIC_REFERENCE = "Shigley, bearing static load rating s₀ = C₀/P₀"


class TransmissionShaft(GuardedInputs):
    """A solid round shaft carrying steady bending and torque, and its screen inputs.

    ``diameter`` d is the shaft diameter at the section being screened, ``bending_moment`` M
    and ``torque`` T the steady loads there, and ``yield_strength`` S_y the material's yield
    stress. The two optional groups each switch on one further check rather than being
    assumed: ``length`` and ``shear_modulus`` with ``allowable_twist`` give the windup check,
    and ``endurance_limit`` with ``ultimate_strength`` give the rotating-shaft fatigue check.
    An absent group is reported ``NOT_EVALUATED`` and names what is missing — a shaft
    screened for static yielding only is a shaft with no fatigue verdict, not a shaft that
    passed one.

    ``endurance_limit`` is the *corrected* endurance limit: the Marin factors, and any
    fatigue stress concentration from a keyway or fillet, are applied by the caller before
    the value arrives here, because they are properties of the shaft's surface and geometry
    rather than of the loads this model carries.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    diameter: Quantity
    bending_moment: Quantity
    torque: Quantity
    yield_strength: Quantity
    length: Quantity | None = None
    shear_modulus: Quantity | None = None
    allowable_twist: Quantity | None = None
    endurance_limit: Quantity | None = None
    ultimate_strength: Quantity | None = None


def _not_evaluated(name: str, detail: str, reference: str) -> ScorecardEntry:
    """One check the caller did not supply the inputs for, said out loud."""
    return ScorecardEntry(
        name=name, status=CheckStatus.NOT_EVALUATED, detail=detail, reference=reference
    )


def _static_entry(shaft: TransmissionShaft, required_safety_factor: float) -> ScorecardEntry:
    """Combined bending and torsion against yield, by the distortion-energy criterion."""
    equivalent = shaft_von_mises_stress(
        bending_moment=shaft.bending_moment, torque=shaft.torque, diameter=shaft.diameter
    )
    sigma = equivalent.to("MPa").magnitude
    yield_mpa = shaft.yield_strength.to("MPa").magnitude
    # A shaft with no moment and no torque has nothing to screen, not infinite reserve —
    # the same `None` -> NOT_EVALUATED the twenty sibling screens spell out.
    safety = yield_mpa / sigma if sigma > 0 else None
    derivation = Derivation(
        symbolic="σ' = 32·√(M² + 0.75·T²)/(π·d³)",
        inputs=(
            SymbolValue(
                symbol="M",
                description="steady bending moment at the section",
                value=shaft.bending_moment,
                unit="N*mm",
            ),
            SymbolValue(
                symbol="T",
                description="steady torque at the section",
                value=shaft.torque,
                unit="N*mm",
            ),
            SymbolValue(symbol="d", description="shaft diameter", value=shaft.diameter, unit="mm"),
        ),
        result=SymbolValue(
            symbol="σ'",
            description="von Mises stress at the shaft surface",
            value=equivalent,
            unit="MPa",
        ),
        citation=_STATIC_REFERENCE,
    )
    entry = ScorecardEntry.from_safety_factor(
        "combined bending and torsion", computed=safety, required=required_safety_factor
    ).model_copy(update={"reference": _STATIC_REFERENCE, "derivation": derivation})
    if entry.status is CheckStatus.FAIL:
        # The library's own inverse of the formula above, at the required margin — not a
        # scaling of the shortfall, which would be the same answer only because σ' happens
        # to go as 1/d³, and would stop being the same answer the day a factor moved.
        required_diameter = shaft_diameter_for_bending_torsion(
            bending_moment=shaft.bending_moment,
            torque=shaft.torque,
            yield_strength=shaft.yield_strength,
            required_safety_factor=required_safety_factor,
        )
        entry = entry.model_copy(
            update={
                "repair_hint": RepairHint.solved(
                    "diameter",
                    direction=Direction.INCREASE,
                    value=required_diameter.to("mm").magnitude,
                    unit="mm",
                    provenance="shaft_diameter_for_bending_torsion at the required margin",
                )
            }
        )
    return entry


def _twist_entry(shaft: TransmissionShaft, required_safety_factor: float) -> ScorecardEntry:
    """Torsional windup over the shaft's length against the caller's allowable."""
    length, modulus, limit = shaft.length, shaft.shear_modulus, shaft.allowable_twist
    missing = [
        name
        for name, value in (
            ("length", length),
            ("shear_modulus", modulus),
            ("allowable_twist", limit),
        )
        if value is None
    ]
    if length is None or modulus is None or limit is None:
        return _not_evaluated(
            "torsional twist",
            f"not evaluated — θ = T·L/(G·J) needs {', '.join(missing)}, which this shaft "
            f"does not declare",
            _TWIST_REFERENCE,
        )
    twist = shaft_twist_angle(
        torque=shaft.torque,
        length=length,
        diameter=shaft.diameter,
        shear_modulus=modulus,
    )
    theta = twist.to("degree").magnitude
    allowable = limit.to("degree").magnitude
    safety = allowable / theta if theta > 0 else None
    derivation = Derivation(
        symbolic="θ = 32·T·L/(π·G·d⁴)",
        inputs=(
            SymbolValue(symbol="T", description="applied torque", value=shaft.torque, unit="N*mm"),
            SymbolValue(
                symbol="L",
                description="twisting length of the shaft",
                value=length,
                unit="mm",
            ),
            SymbolValue(
                symbol="G",
                description="shear (rigidity) modulus of the shaft material",
                value=modulus,
                unit="MPa",
            ),
            SymbolValue(symbol="d", description="shaft diameter", value=shaft.diameter, unit="mm"),
        ),
        result=SymbolValue(
            symbol="θ",
            description="angle of twist end to end",
            value=twist,
            unit="degree",
        ),
        citation=_TWIST_REFERENCE,
    )
    entry = ScorecardEntry.from_safety_factor(
        "torsional twist", computed=safety, required=required_safety_factor
    ).model_copy(update={"reference": _TWIST_REFERENCE, "derivation": derivation})
    if entry.status is CheckStatus.FAIL:
        # θ goes as 1/d⁴ with everything else held, so the diameter that lands the required
        # margin is exact rather than a search: d·(n·θ/θ_allow)^(1/4). This is the one of
        # the three levers with a fourth-power exponent, which is why the three answers
        # separate — a shaft that fails twist by a factor of four needs 41% more diameter
        # where the same shortfall on the static check would need 59%.
        entry = entry.model_copy(
            update={
                "repair_hint": RepairHint.solved(
                    "diameter",
                    direction=Direction.INCREASE,
                    value=shaft.diameter.to("mm").magnitude
                    * (required_safety_factor * theta / allowable) ** 0.25,
                    unit="mm",
                    provenance="θ = T·L/(G·J) inverted for d at the required margin",
                )
            }
        )
    return entry


def _fatigue_entry(shaft: TransmissionShaft, required_safety_factor: float) -> ScorecardEntry:
    """Fully-reversed bending with steady torque, by DE-Goodman."""
    endurance, ultimate = shaft.endurance_limit, shaft.ultimate_strength
    missing = [
        name
        for name, value in (
            ("endurance_limit", endurance),
            ("ultimate_strength", ultimate),
        )
        if value is None
    ]
    if endurance is None or ultimate is None:
        return _not_evaluated(
            "rotating-shaft fatigue",
            f"not evaluated — the DE-Goodman criterion needs {', '.join(missing)}, which "
            f"this shaft does not declare; a static verdict is not a fatigue verdict",
            _FATIGUE_REFERENCE,
        )
    moment = shaft.bending_moment.to("N*mm").magnitude
    torque = shaft.torque.to("N*mm").magnitude
    if moment <= 0.0 and torque <= 0.0:
        return _not_evaluated(
            "rotating-shaft fatigue",
            "not evaluated — the shaft carries neither a bending moment nor a torque, so "
            "the Goodman criterion has nothing to evaluate",
            _FATIGUE_REFERENCE,
        )
    # The whole DE-Goodman bracket scales as 1/d³, so the design factor at the declared
    # diameter is exactly (d/d₁)³ against the diameter the criterion demands at n = 1. That
    # identity is what turns an inverse-only criterion into a safety factor, and it is
    # pinned by a test that solves the inverse back at the factor this computes.
    unit_diameter = shaft_diameter_de_goodman(
        alternating_bending_moment=shaft.bending_moment,
        mean_torque=shaft.torque,
        endurance_limit=endurance,
        ultimate_strength=ultimate,
        required_safety_factor=1.0,
    )
    d_1 = unit_diameter.to("mm").magnitude
    d = shaft.diameter.to("mm").magnitude
    safety = (d / d_1) ** 3 if d_1 > 0 else None
    derivation = Derivation(
        symbolic="n_f = (d/d₁)³",
        inputs=(
            SymbolValue(
                symbol="d", description="declared shaft diameter", value=shaft.diameter, unit="mm"
            ),
            SymbolValue(
                symbol="d₁",
                description=(
                    "least diameter the DE-Goodman criterion allows at n = 1, from the "
                    "reversed bending M, the steady torque T, the corrected endurance limit "
                    "S_e and the ultimate strength S_ut"
                ),
                value=unit_diameter,
                unit="mm",
            ),
        ),
        result=SymbolValue(
            symbol="n_f",
            description="fatigue design factor; the DE-Goodman bracket goes as 1/d³",
            value=safety,
        ),
        citation=_FATIGUE_REFERENCE,
    )
    entry = ScorecardEntry.from_safety_factor(
        "rotating-shaft fatigue", computed=safety, required=required_safety_factor
    ).model_copy(update={"reference": _FATIGUE_REFERENCE, "derivation": derivation})
    if entry.status is CheckStatus.FAIL:
        required_diameter = shaft_diameter_de_goodman(
            alternating_bending_moment=shaft.bending_moment,
            mean_torque=shaft.torque,
            endurance_limit=endurance,
            ultimate_strength=ultimate,
            required_safety_factor=required_safety_factor,
        )
        entry = entry.model_copy(
            update={
                "repair_hint": RepairHint.solved(
                    "diameter",
                    direction=Direction.INCREASE,
                    value=required_diameter.to("mm").magnitude,
                    unit="mm",
                    provenance="shaft_diameter_de_goodman at the required margin",
                )
            }
        )
    return entry


def screen_shaft(
    shaft: TransmissionShaft,
    *,
    required_safety_factor: float = 2.0,
) -> Scorecard:
    """Screen a :class:`TransmissionShaft` for strength, twist and fatigue, and return its card.

    Screens the static distortion-energy stress against yield, the end-to-end torsional
    twist against the declared allowable, and the DE-Goodman rotating-shaft fatigue factor,
    each against ``required_safety_factor`` (2.0, the middle of the range Shigley recommends
    for a shaft — nothing in these formulas carries a code margin of its own). Returns a
    :class:`~anvilate.scorecard.Scorecard` with a cited entry for each; a check whose inputs
    the shaft does not declare is ``NOT_EVALUATED`` and says which input is missing.

    Every failing entry names ``diameter`` and carries the value that clears its own limit.
    They will not agree — static and fatigue go as d³ against different allowables and twist
    as d⁴ — and the shaft is the largest of them.
    """
    return Scorecard(
        entries=(
            _static_entry(shaft, required_safety_factor),
            _twist_entry(shaft, required_safety_factor),
            _fatigue_entry(shaft, required_safety_factor),
        )
    )


class SpurGearMesh(GuardedInputs):
    """A standard spur-gear mesh and its screen inputs.

    ``pinion_teeth`` N₁ and ``gear_teeth`` N₂ with ``module`` m and ``pressure_angle`` φ (in
    degrees) fix the geometry; ``face_width`` b and ``pinion_torque`` T fix the loading. The
    two AGMA geometry factors and the two allowable stresses are the caller's, from the
    charts and the material's rating — this screen rates the mesh, it does not look a gear
    steel up. So are the derating factors, each defaulting to 1.0 and each a decision:
    leaving ``dynamic_factor`` at 1.0 says the mesh is quiet and slow, which for a real
    drive it is not.

    ``minimum_contact_ratio`` is the transverse contact ratio the mesh has to reach for the
    load to hand over smoothly from one tooth pair to the next; 1.2 is the usual floor and
    anything at or under 1.0 is a mesh that stops carrying load between teeth.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    pinion_teeth: int
    gear_teeth: int
    module: Quantity
    face_width: Quantity
    pressure_angle: float
    pinion_torque: Quantity
    bending_geometry_factor: float
    contact_geometry_factor: float
    allowable_bending_stress: Quantity
    allowable_contact_stress: Quantity
    pinion_modulus: Quantity
    gear_modulus: Quantity
    minimum_contact_ratio: float = 1.2
    overload_factor: float = 1.0
    dynamic_factor: float = 1.0
    size_factor: float = 1.0
    load_distribution_factor: float = 1.0
    rim_thickness_factor: float = 1.0
    surface_condition_factor: float = 1.0


def _mesh_loads(mesh: SpurGearMesh) -> tuple[Quantity, Quantity]:
    """The pinion pitch diameter and the tangential load the torque puts on the tooth."""
    pitch_diameter = gear_pitch_diameter(module=mesh.module, teeth=mesh.pinion_teeth)
    return pitch_diameter, gear_tangential_load(
        torque=mesh.pinion_torque, pitch_diameter=pitch_diameter
    )


def _bending_entry(mesh: SpurGearMesh, required_safety_factor: float) -> ScorecardEntry:
    """AGMA tooth-root bending stress against the allowable."""
    pitch_diameter, tangential = _mesh_loads(mesh)
    stress = agma_bending_stress(
        tangential_load=tangential,
        module=mesh.module,
        face_width=mesh.face_width,
        geometry_factor=mesh.bending_geometry_factor,
        overload_factor=mesh.overload_factor,
        dynamic_factor=mesh.dynamic_factor,
        size_factor=mesh.size_factor,
        load_distribution_factor=mesh.load_distribution_factor,
        rim_thickness_factor=mesh.rim_thickness_factor,
    )
    sigma = stress.to("MPa").magnitude
    allowable = mesh.allowable_bending_stress.to("MPa").magnitude
    safety = allowable / sigma if sigma > 0 else None
    derivation = Derivation(
        symbolic="σ = W_t·K_o·K_v·K_s·K_H·K_B/(b·m·Y_J)",
        inputs=(
            SymbolValue(
                symbol="W_t",
                description="tangential tooth load, 2·T/d₁",
                value=tangential,
                unit="N",
            ),
            SymbolValue(symbol="b", description="face width", value=mesh.face_width, unit="mm"),
            SymbolValue(symbol="m", description="transverse module", value=mesh.module, unit="mm"),
            SymbolValue(
                symbol="Y_J",
                description="AGMA bending geometry (J) factor",
                value=mesh.bending_geometry_factor,
            ),
            SymbolValue(symbol="K_o", description="overload factor", value=mesh.overload_factor),
            SymbolValue(symbol="K_v", description="dynamic factor", value=mesh.dynamic_factor),
            SymbolValue(symbol="K_s", description="size factor", value=mesh.size_factor),
            SymbolValue(
                symbol="K_H",
                description="load distribution factor",
                value=mesh.load_distribution_factor,
            ),
            SymbolValue(
                symbol="K_B", description="rim thickness factor", value=mesh.rim_thickness_factor
            ),
        ),
        result=SymbolValue(
            symbol="σ", description="tooth-root bending stress", value=stress, unit="MPa"
        ),
        citation=_BENDING_REFERENCE,
    )
    entry = ScorecardEntry.from_safety_factor(
        "tooth-root bending", computed=safety, required=required_safety_factor
    ).model_copy(update={"reference": _BENDING_REFERENCE, "derivation": derivation})
    if entry.status is CheckStatus.FAIL:
        # `agma_module_for_bending_stress` is NOT the hint. It solves at a FIXED tangential
        # load, and this screen's given is the pinion TORQUE — so W_t = 2·T/(m·N₁) shrinks
        # as the module grows and the module enters the stress twice: σ ∝ 1/m². The
        # library's inverse would name a module that lands the mesh well past the margin,
        # and naming a value that is not the least one is how a hint stops being usable.
        entry = entry.model_copy(
            update={
                "repair_hint": RepairHint.solved(
                    "module",
                    direction=Direction.INCREASE,
                    value=mesh.module.to("mm").magnitude
                    * (sigma * required_safety_factor / allowable) ** 0.5,
                    unit="mm",
                    provenance="σ ∝ 1/m² at a fixed pinion torque, solved at the margin",
                )
            }
        )
    return entry


def _pitting_entry(mesh: SpurGearMesh, required_safety_factor: float) -> ScorecardEntry:
    """AGMA pitting-resistance (contact) stress against the allowable."""
    pitch_diameter, tangential = _mesh_loads(mesh)
    stress = agma_contact_stress(
        tangential_load=tangential,
        pinion_pitch_diameter=pitch_diameter,
        face_width=mesh.face_width,
        geometry_factor=mesh.contact_geometry_factor,
        modulus_pinion=mesh.pinion_modulus,
        modulus_gear=mesh.gear_modulus,
        overload_factor=mesh.overload_factor,
        dynamic_factor=mesh.dynamic_factor,
        size_factor=mesh.size_factor,
        load_distribution_factor=mesh.load_distribution_factor,
        surface_condition_factor=mesh.surface_condition_factor,
    )
    sigma = stress.to("MPa").magnitude
    allowable = mesh.allowable_contact_stress.to("MPa").magnitude
    safety = allowable / sigma if sigma > 0 else None
    derivation = Derivation(
        symbolic="σ_c = C_p·√(W_t·K_o·K_v·K_s·K_H·C_f/(d₁·b·I))",
        inputs=(
            SymbolValue(
                symbol="C_p",
                description="elastic coefficient from the two moduli and Poisson ratios",
                value=Quantity(magnitude=_elastic_coefficient(mesh), unit="MPa**0.5"),
                unit="MPa**0.5",
            ),
            SymbolValue(
                symbol="W_t", description="tangential tooth load", value=tangential, unit="N"
            ),
            SymbolValue(
                symbol="d₁",
                description="pinion pitch diameter, m·N₁",
                value=pitch_diameter,
                unit="mm",
            ),
            SymbolValue(symbol="b", description="face width", value=mesh.face_width, unit="mm"),
            SymbolValue(
                symbol="I",
                description="AGMA pitting geometry (I) factor",
                value=mesh.contact_geometry_factor,
            ),
            SymbolValue(symbol="K_o", description="overload factor", value=mesh.overload_factor),
            SymbolValue(symbol="K_v", description="dynamic factor", value=mesh.dynamic_factor),
            SymbolValue(symbol="K_s", description="size factor", value=mesh.size_factor),
            SymbolValue(
                symbol="K_H",
                description="load distribution factor",
                value=mesh.load_distribution_factor,
            ),
            SymbolValue(
                symbol="C_f",
                description="surface condition factor",
                value=mesh.surface_condition_factor,
            ),
        ),
        result=SymbolValue(
            symbol="σ_c", description="surface contact stress", value=stress, unit="MPa"
        ),
        citation=_PITTING_REFERENCE,
    )
    entry = ScorecardEntry.from_safety_factor(
        "surface pitting", computed=safety, required=required_safety_factor
    ).model_copy(update={"reference": _PITTING_REFERENCE, "derivation": derivation})
    if entry.status is CheckStatus.FAIL:
        # W_t/d₁ = 2·T/(m·N₁)² at a fixed torque, and it is the only place the module
        # reaches, so σ_c ∝ 1/m — a FIRST power where bending is a second. That is why the
        # two checks name two different modules, and why the pitting one is the larger jump
        # for the same shortfall.
        entry = entry.model_copy(
            update={
                "repair_hint": RepairHint.solved(
                    "module",
                    direction=Direction.INCREASE,
                    value=mesh.module.to("mm").magnitude
                    * sigma
                    * required_safety_factor
                    / allowable,
                    unit="mm",
                    provenance="σ_c ∝ 1/m at a fixed pinion torque, solved at the margin",
                )
            }
        )
    return entry


def _elastic_coefficient(mesh: SpurGearMesh) -> float:
    """C_p in √MPa, recovered from the stress the library computes at a unit mesh.

    Written this way rather than as a second copy of the formula: a derivation line that
    restates an expression the module already owns is the duplication the render-truth gate
    exists to catch, one level up.
    """
    unit_load = Quantity(magnitude=1.0, unit="N")
    unit_length = Quantity(magnitude=1.0, unit="mm")
    reference = agma_contact_stress(
        tangential_load=unit_load,
        pinion_pitch_diameter=unit_length,
        face_width=unit_length,
        geometry_factor=1.0,
        modulus_pinion=mesh.pinion_modulus,
        modulus_gear=mesh.gear_modulus,
    )
    return reference.to("MPa").magnitude


def _contact_ratio_entry(mesh: SpurGearMesh) -> ScorecardEntry:
    """The transverse contact ratio against the mesh's own declared floor.

    Judged against 1.0 on the *ratio to the declared floor*, not against the stress checks'
    safety factor: a contact ratio is a geometric threshold for smooth load transfer, and
    demanding 1.5× of a threshold is demanding a different threshold.
    """
    ratio = spur_gear_contact_ratio(
        module=mesh.module,
        pinion_teeth=mesh.pinion_teeth,
        gear_teeth=mesh.gear_teeth,
        pressure_angle=mesh.pressure_angle,
    )
    derivation = Derivation(
        symbolic="U = m_p/m_min",
        inputs=(
            SymbolValue(
                symbol="m_p",
                description=(
                    f"transverse contact ratio of a {mesh.pinion_teeth}/{mesh.gear_teeth} "
                    f"mesh at {mesh.pressure_angle:g}°"
                ),
                value=ratio,
            ),
            SymbolValue(
                symbol="m_min",
                description="the contact ratio this mesh declares it needs",
                value=mesh.minimum_contact_ratio,
            ),
        ),
        result=SymbolValue(
            symbol="U",
            description="contact ratio as a multiple of the declared floor",
            value=ratio / mesh.minimum_contact_ratio,
        ),
        citation=_CONTACT_RATIO_REFERENCE,
    )
    entry = ScorecardEntry.from_safety_factor(
        "contact ratio", computed=ratio / mesh.minimum_contact_ratio, required=1.0
    ).model_copy(update={"reference": _CONTACT_RATIO_REFERENCE, "derivation": derivation})
    if entry.status is CheckStatus.FAIL:
        # The module is NOT the lever here and this is the interesting part of the check:
        # the contact ratio is scale-invariant — every length in it is a multiple of m — so
        # a bigger gear does nothing. What moves it is the tooth form, and a lower pressure
        # angle raises it monotonically over the whole practical range (swept in
        # tests/test_machinery_pack.py). Directional and not solved: the closed form runs
        # through the base-circle geometry and does not invert.
        entry = entry.model_copy(
            update={
                "repair_hint": RepairHint.directional(
                    "pressure_angle",
                    direction=Direction.DECREASE,
                    provenance=(
                        "contact ratio falls monotonically with pressure angle over "
                        "14.5°-30°; the module cannot move it at all"
                    ),
                )
            }
        )
    return entry


def _undercut_entry(mesh: SpurGearMesh) -> ScorecardEntry:
    """The pinion tooth count against the rack-generation undercut limit."""
    least = minimum_teeth_to_avoid_undercut(pressure_angle=mesh.pressure_angle)
    derivation = Derivation(
        symbolic="U = N₁/N_min",
        inputs=(
            SymbolValue(symbol="N₁", description="pinion tooth count", value=mesh.pinion_teeth),
            SymbolValue(
                symbol="N_min",
                description=(
                    f"fewest teeth that generate without undercut at "
                    f"{mesh.pressure_angle:g}°, ⌈2·k/sin²φ⌉"
                ),
                value=least,
            ),
        ),
        result=SymbolValue(
            symbol="U",
            description="pinion teeth as a multiple of the undercut limit",
            value=mesh.pinion_teeth / least,
        ),
        citation=_UNDERCUT_REFERENCE,
    )
    entry = ScorecardEntry.from_safety_factor(
        "undercut", computed=mesh.pinion_teeth / least, required=1.0
    ).model_copy(update={"reference": _UNDERCUT_REFERENCE, "derivation": derivation})
    if entry.status is CheckStatus.FAIL:
        entry = entry.model_copy(
            update={
                "repair_hint": RepairHint.solved(
                    "pinion_teeth",
                    direction=Direction.INCREASE,
                    value=float(least),
                    unit="teeth",
                    provenance="rack-generation limit ⌈2·k/sin²φ⌉ itself",
                    whole=True,
                )
            }
        )
    return entry


def screen_gear_mesh(
    mesh: SpurGearMesh,
    *,
    required_safety_factor: float = 1.2,
) -> Scorecard:
    """Screen a :class:`SpurGearMesh` for strength, pitting and tooth form, and return its card.

    Screens AGMA tooth-root bending and pitting resistance against
    ``required_safety_factor`` (1.2, the usual minimum on a rated gear), and the transverse
    contact ratio and the undercut limit against their own thresholds — a geometric
    threshold takes no design margin on top. Returns a
    :class:`~anvilate.scorecard.Scorecard` with a cited entry for each.

    **The four checks are moved by three different parameters.** Bending and pitting both
    take ``module``, at a second power and a first; the contact ratio is scale-invariant and
    takes only the pressure angle; and undercut takes the pinion tooth count. A mesh that
    fails on more than one of them cannot be fixed by moving one number.
    """
    return Scorecard(
        entries=(
            _bending_entry(mesh, required_safety_factor),
            _pitting_entry(mesh, required_safety_factor),
            _contact_ratio_entry(mesh),
            _undercut_entry(mesh),
        )
    )


class ShaftKey(GuardedInputs):
    """A parallel key in a shaft-and-hub joint, and its screen inputs.

    ``shaft_diameter`` d, ``key_width`` w, ``key_height`` h and ``key_length`` L describe the
    key; ``torque`` T is what it transmits. The two allowables are the caller's, and they are
    two different quantities against two different areas — shear across the key's width, and
    side bearing on half its height.

    A key is the weakest part of a drive on purpose: it is the cheap part that is meant to go
    first. That is only true if somebody checked, and a shaft that passes every one of its
    own limits tells you nothing about the joint that drives it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    shaft_diameter: Quantity
    key_width: Quantity
    key_height: Quantity
    key_length: Quantity
    torque: Quantity
    allowable_shear: Quantity
    allowable_bearing: Quantity


def _key_length_hint(key: ShaftKey, required_safety_factor: float, mode: str) -> RepairHint:
    """The key length one limit state needs at the required margin.

    Solved by the library's own inverse with the allowables derated — a margin on the
    allowable is exactly what a safety factor on this check means, and dividing there rather
    than scaling the length afterwards keeps the two limit states' answers independent.
    """
    requirement = key_length_for_torque(
        torque=key.torque,
        shaft_diameter=key.shaft_diameter,
        key_width=key.key_width,
        key_height=key.key_height,
        allowable_shear=Quantity(
            magnitude=key.allowable_shear.to("MPa").magnitude / required_safety_factor,
            unit="MPa",
        ),
        allowable_bearing=Quantity(
            magnitude=key.allowable_bearing.to("MPa").magnitude / required_safety_factor,
            unit="MPa",
        ),
    )
    length = requirement.shear_length if mode == "shear" else requirement.bearing_length
    return RepairHint.solved(
        "key_length",
        direction=Direction.INCREASE,
        value=length.to("mm").magnitude,
        unit="mm",
        provenance=f"key_length_for_torque's {mode} length at the derated allowable",
    )


def _key_shear_entry(key: ShaftKey, required_safety_factor: float) -> ScorecardEntry:
    """Shear across the key's width at the shaft surface."""
    stress = key_shear_stress(
        torque=key.torque,
        shaft_diameter=key.shaft_diameter,
        key_width=key.key_width,
        key_length=key.key_length,
    )
    tau = stress.to("MPa").magnitude
    allowable = key.allowable_shear.to("MPa").magnitude
    safety = allowable / tau if tau > 0 else None
    derivation = Derivation(
        symbolic="τ = 2·T/(d·w·L)",
        inputs=(
            SymbolValue(
                symbol="T", description="transmitted torque", value=key.torque, unit="N*mm"
            ),
            SymbolValue(
                symbol="d", description="shaft diameter", value=key.shaft_diameter, unit="mm"
            ),
            SymbolValue(symbol="w", description="key width", value=key.key_width, unit="mm"),
            SymbolValue(symbol="L", description="key length", value=key.key_length, unit="mm"),
        ),
        result=SymbolValue(
            symbol="τ", description="shear stress across the key", value=stress, unit="MPa"
        ),
        citation=_KEY_SHEAR_REFERENCE,
    )
    entry = ScorecardEntry.from_safety_factor(
        "key shear", computed=safety, required=required_safety_factor
    ).model_copy(update={"reference": _KEY_SHEAR_REFERENCE, "derivation": derivation})
    if entry.status is CheckStatus.FAIL:
        entry = entry.model_copy(
            update={"repair_hint": _key_length_hint(key, required_safety_factor, "shear")}
        )
    return entry


def _key_bearing_entry(key: ShaftKey, required_safety_factor: float) -> ScorecardEntry:
    """Side bearing on the half of the key standing proud of the shaft."""
    stress = key_bearing_stress(
        torque=key.torque,
        shaft_diameter=key.shaft_diameter,
        key_height=key.key_height,
        key_length=key.key_length,
    )
    sigma = stress.to("MPa").magnitude
    allowable = key.allowable_bearing.to("MPa").magnitude
    safety = allowable / sigma if sigma > 0 else None
    derivation = Derivation(
        symbolic="σ_b = 4·T/(d·h·L)",
        inputs=(
            SymbolValue(
                symbol="T", description="transmitted torque", value=key.torque, unit="N*mm"
            ),
            SymbolValue(
                symbol="d", description="shaft diameter", value=key.shaft_diameter, unit="mm"
            ),
            SymbolValue(
                symbol="h",
                description="key height; half of it bears on the hub",
                value=key.key_height,
                unit="mm",
            ),
            SymbolValue(symbol="L", description="key length", value=key.key_length, unit="mm"),
        ),
        result=SymbolValue(
            symbol="σ_b", description="side bearing stress on the key", value=stress, unit="MPa"
        ),
        citation=_KEY_BEARING_REFERENCE,
    )
    entry = ScorecardEntry.from_safety_factor(
        "key side bearing", computed=safety, required=required_safety_factor
    ).model_copy(update={"reference": _KEY_BEARING_REFERENCE, "derivation": derivation})
    if entry.status is CheckStatus.FAIL:
        entry = entry.model_copy(
            update={"repair_hint": _key_length_hint(key, required_safety_factor, "bearing")}
        )
    return entry


def screen_shaft_key(
    key: ShaftKey,
    *,
    required_safety_factor: float = 2.0,
) -> Scorecard:
    """Screen a :class:`ShaftKey` for shear and side bearing, and return its scorecard.

    Screens both limit states against ``required_safety_factor`` (2.0 on a key, whose
    allowables are plain material strengths with no code margin in them). Returns a
    :class:`~anvilate.scorecard.Scorecard` with a cited entry for each.

    **The two checks name two different lengths**, in the same shape as the shear plate's
    two areas: shear acts across the key's width and bearing on half its height, so which
    one governs depends on the key's proportions rather than on the torque. A square key in
    a soft hub is governed by bearing and a flat one by shear, and the card says which.
    """
    return Scorecard(
        entries=(
            _key_shear_entry(key, required_safety_factor),
            _key_bearing_entry(key, required_safety_factor),
        )
    )


class RollingBearing(GuardedInputs):
    """A rolling-element bearing in a running application, and its screen inputs.

    ``dynamic_load_rating`` C and ``static_load_rating`` C₀ are the catalogue's two ratings.
    ``radial_load`` and ``axial_load`` are the loads on it, combined into an equivalent load
    through the catalogue's ``radial_factor`` X and ``axial_factor`` Y — which are properties
    of the bearing series and its load ratio, and are the caller's to read off the table.
    ``speed`` and ``required_life_hours`` say what the application asks of it.

    ``life_exponent`` is 3 for a ball bearing and 10/3 for a roller bearing, and it is worth
    stating rather than defaulting: it is the exponent the whole life calculation turns on,
    and the two answers differ by a factor of two at an ordinary load ratio.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    dynamic_load_rating: Quantity
    static_load_rating: Quantity
    radial_load: Quantity
    axial_load: Quantity
    radial_factor: float
    axial_factor: float
    speed: Quantity
    required_life_hours: Quantity
    life_exponent: float = BALL_BEARING_LIFE_EXPONENT
    required_static_factor: float = 1.0


def _bearing_life_entry(unit: RollingBearing, required_safety_factor: float) -> ScorecardEntry:
    """The L10 rating life against the life the application asks for."""
    equivalent = bearing_equivalent_dynamic_load(
        radial_load=unit.radial_load,
        axial_load=unit.axial_load,
        radial_factor=unit.radial_factor,
        axial_factor=unit.axial_factor,
    )
    life = bearing_life_hours(
        dynamic_load_rating=unit.dynamic_load_rating,
        equivalent_load=equivalent,
        speed=unit.speed,
        life_exponent=unit.life_exponent,
    )
    reached = life.to("hour").magnitude
    wanted = unit.required_life_hours.to("hour").magnitude
    safety = reached / wanted if wanted > 0 else None
    # Revolutions, not hours, and the reason is worth stating. The textbook form
    # L_10h = (C/P)^p*10^6/(60*n) carries a bare 60 that converts minutes to hours — a unit
    # conversion written as a number — so the line cannot be evaluated as it stands. Worse,
    # pint reads a revolution as 2*pi radians, so the near miss is a factor of 2*pi rather
    # than an obvious one. Comparing revolutions to revolutions has neither problem, and the
    # ratio is the same one: the speed is constant across both sides.
    required_revolutions = wanted * 60.0 * unit.speed.to("rpm").magnitude
    derivation = Derivation(
        symbolic="U = (C/P)**p·10⁶/L_req",
        inputs=(
            SymbolValue(
                symbol="C",
                description="basic dynamic load rating from the catalogue",
                value=unit.dynamic_load_rating,
                unit="kN",
            ),
            SymbolValue(
                symbol="P",
                description="equivalent dynamic load, X·F_r + Y·F_a",
                value=equivalent,
                unit="kN",
            ),
            SymbolValue(
                symbol="p",
                description="life exponent; 3 for a ball bearing, 10/3 for a roller",
                value=unit.life_exponent,
            ),
            SymbolValue(
                symbol="L_req",
                description=(
                    f"the life asked for ({unit.required_life_hours}) as revolutions at "
                    f"{unit.speed}"
                ),
                value=required_revolutions,
            ),
        ),
        result=SymbolValue(
            symbol="U",
            description=f"rating life as a multiple of the life asked for; L₁₀ₕ = {life}",
            value=safety,
        ),
        citation=_BEARING_LIFE_REFERENCE,
    )
    entry = ScorecardEntry.from_safety_factor(
        "bearing rating life", computed=safety, required=required_safety_factor
    ).model_copy(update={"reference": _BEARING_LIFE_REFERENCE, "derivation": derivation})
    if entry.status is CheckStatus.FAIL:
        # The lever is the CATALOGUE RATING, not a dimension: a bearing is chosen, not
        # machined, and catalogues are indexed by C. The hint names the least C that reaches
        # the life at the margin, which is a number a reader looks up rather than a number
        # they have to search for.
        rating = bearing_rating_for_life(
            equivalent_load=equivalent,
            required_life_millions=wanted
            * required_safety_factor
            * 60.0
            * unit.speed.to("rpm").magnitude
            / 1.0e6,
            life_exponent=unit.life_exponent,
        )
        entry = entry.model_copy(
            update={
                "repair_hint": RepairHint.solved(
                    "dynamic_load_rating",
                    direction=Direction.INCREASE,
                    value=rating.to("kN").magnitude,
                    unit="kN",
                    provenance="bearing_rating_for_life at the required life and margin",
                )
            }
        )
    return entry


def _bearing_static_entry(unit: RollingBearing) -> ScorecardEntry:
    """The static load rating against the equivalent static load.

    Judged against the bearing's own ``required_static_factor`` and not against the life
    check's margin: s₀ is already a safety factor, and putting a second one on top of it
    asks for a rating nobody's catalogue table is written against.
    """
    static_load = bearing_equivalent_static_load(
        radial_load=unit.radial_load,
        axial_load=unit.axial_load,
        radial_factor=unit.radial_factor,
        axial_factor=unit.axial_factor,
    )
    factor = bearing_static_safety_factor(
        static_load_rating=unit.static_load_rating, equivalent_static_load=static_load
    )
    derivation = Derivation(
        symbolic="s₀ = C₀/P₀",
        inputs=(
            SymbolValue(
                symbol="C₀",
                description="basic static load rating from the catalogue",
                value=unit.static_load_rating,
                unit="kN",
            ),
            SymbolValue(
                symbol="P₀",
                description="equivalent static load, X·F_r + Y·F_a",
                value=static_load,
                unit="kN",
            ),
        ),
        result=SymbolValue(symbol="s₀", description="static load safety factor", value=factor),
        citation=_BEARING_STATIC_REFERENCE,
    )
    entry = ScorecardEntry.from_safety_factor(
        "bearing static capacity",
        computed=factor / unit.required_static_factor,
        required=1.0,
    ).model_copy(update={"reference": _BEARING_STATIC_REFERENCE, "derivation": derivation})
    if entry.status is CheckStatus.FAIL:
        entry = entry.model_copy(
            update={
                "repair_hint": RepairHint.solved(
                    "static_load_rating",
                    direction=Direction.INCREASE,
                    value=static_load.to("kN").magnitude * unit.required_static_factor,
                    unit="kN",
                    provenance="equivalent static load at the declared s₀",
                )
            }
        )
    return entry


def screen_rolling_bearing(
    unit: RollingBearing,
    *,
    required_safety_factor: float = 1.0,
) -> Scorecard:
    """Screen a :class:`RollingBearing` for rating life and static capacity, and return its card.

    Screens the L10 rating life against ``required_life_hours`` × ``required_safety_factor``
    (1.0 — the life the application asks for is already the requirement), and the static
    load rating against the bearing's own declared ``required_static_factor``. Returns a
    :class:`~anvilate.scorecard.Scorecard` with a cited entry for each.

    **Both levers are the catalogue's ratings rather than a dimension**, because a bearing is
    selected and not machined: a failing entry names the least C, or the least C₀, that
    clears its limit, which is what a reader takes to the table.
    """
    return Scorecard(
        entries=(
            _bearing_life_entry(unit, required_safety_factor),
            _bearing_static_entry(unit),
        )
    )
