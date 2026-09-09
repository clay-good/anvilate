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
    shaft_diameter_de_goodman,
    shaft_diameter_for_bending_torsion,
    shaft_twist_angle,
    shaft_von_mises_stress,
)
from ..derivation import Derivation, SymbolValue
from ..scorecard import CheckStatus, Direction, RepairHint, Scorecard, ScorecardEntry
from ..units import Quantity
from ._guarded import GuardedInputs

__all__ = [
    "TransmissionShaft",
    "screen_shaft",
]

_STATIC_REFERENCE = "Shigley §7-4 shaft design for stress (distortion energy)"
_TWIST_REFERENCE = "Shigley shaft deflection, θ = T·L/(G·J)"
_FATIGUE_REFERENCE = "Shigley Eq. 7-8, DE-Goodman rotating-shaft fatigue"


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
