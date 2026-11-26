"""Worked example: the edition, not the cabinet, tripled the anchor force.

A switchgear cabinet is bolted to the roof slab of a four-storey steel ordinary
concentrically braced frame. Nothing about the cabinet changes between ASCE/SEI 7-16 and
ASCE/SEI 7-22 — same mass, same bolts, same roof. The design force does, by a factor of
**3.33**: **2,256 N** by the 2016 equation and **7,520 N** by the 2022 one. A reviewer
handed the smaller number has no way to tell which edition it came from, which is why
every force here carries its own.

The 2022 figure is not even the equation's answer. Eq. 13.3-1 gives **8,298 N** and
Eq. 13.3-2's cap of 1.6·S_DS·I_p·W_p holds it at 7,520 N, so the cap is doing real work on
an ordinary piece of equipment rather than sitting in the standard as a formality.

Where the factor of three comes from is worth seeing, because it is not one effect. At the
roof the 2022 height factor H_f is **3.49** against the 2016 linear rule's 3.0, which is
small. The building's ductility then divides by R_μ = **1.34**, which *helps*. What does it
is the component: 2016 credited a cabinet with R_p = 2.5 of its own ductility, while 2022
asks whether the cabinet resonates with the building and, for one that does, multiplies by
C_AR/R_po = 2.2/1.3. The old equation gave a rigid component a ductility reduction that
structural dynamics does not support, and the rewrite took it away.

Into the anchors, at the pattern this cabinet sits on, that is **6,956 N** of tension in
each of the two windward bolts and **1,880 N** of shear in each of the four.

The concurrent vertical force of §13.3.1.6 is **940 N**, a fifth of the cabinet's weight,
and it lightens what resists the overturning moment. It is worth **3.5%** more anchor
tension and no more — without it the tension is **6,721 N** — and the reason is the one
the anchorage module already reports: the weight was only resisting **15%** of the moment
to begin with. On tall equipment on a tight bolt pattern the vertical term is a rounding
error, and the lever is everything.

**None of the coefficients here are bundled.** The standard's Tables 13.5-1 and 13.6-1 are
copyrighted. Every coefficient below is declared with the public document it was read from
— NIST GCR 18-917-43, the ATC-120 report behind the 2022 rewrite, which prints its own
C_AR table and the archetype's R and Ω_0 — and a real project replaces each with the row
its adopted edition's table gives.

Run it directly (``python examples/roof_cabinet_component_force_by_edition.py``);
:func:`roof_cabinet_component_force_by_edition` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis.anchorage import AnchorageDemand, AnchorPosition, anchor_pattern_demand
from anvilate.analysis.nonstructural_seismic import (
    ComponentForce,
    TabulatedCoefficient,
    component_seismic_design_force_asce_7_16,
    component_seismic_design_force_asce_7_22,
    component_vertical_seismic_force,
    height_amplification_factor,
    structure_ductility_reduction_factor,
)
from anvilate.units import Quantity, render

Q = Quantity.parse

#: The cabinet: a floor-standing switchgear enclosure, operating weight as a force.
CABINET_WEIGHT = Q("4700 N")
#: Its centre of gravity above the slab.
CABINET_CENTROID = Q("1050 mm")
#: Short-period design spectral acceleration, the value the ATC-120 archetypes are run at.
DESIGN_SPECTRAL_ACCELERATION = 1.0
#: At the roof, so z/h is 1.
HEIGHT_RATIO = 1.0

#: The supporting structure, from NIST GCR 18-917-43: a four-storey steel ordinary
#: concentrically braced frame, 56 ft tall, T_a = 0.020 x 56^0.75 (its §4.8), with
#: R = 3.25 and Omega_0 = 2 (its Table 4-3).
STRUCTURE_PERIOD = Q("0.41 s")
STRUCTURE_R = 3.25
STRUCTURE_OMEGA = 2.0

#: Table 4-2, roof or elevated floor, more likely to be in resonance, moderate ductility.
RESONANCE_DUCTILITY = TabulatedCoefficient(
    symbol="C_AR",
    value=2.2,
    table="NIST GCR 18-917-43 Table 4-2 — roof, likely resonance, moderate ductility",
)
#: Its §4.3.4.4 reserve-strength factor, which the Provisions kept as R_po.
COMPONENT_STRENGTH = TabulatedCoefficient(
    symbol="R_po",
    value=1.3,
    table="NIST GCR 18-917-43 §4.3.4.4 — component reserve strength margin factor",
)
#: ASCE/SEI 7-16's cabinet row, as NIST GCR 18-917-43 §4.9.2 quotes it.
AMPLIFICATION = TabulatedCoefficient(
    symbol="a_p",
    value=1.0,
    table="ASCE/SEI 7-16 Table 13.5-1 cabinet row, quoted in NIST GCR 18-917-43 §4.9.2",
)
RESPONSE_MODIFICATION = TabulatedCoefficient(
    symbol="R_p",
    value=2.5,
    table="ASCE/SEI 7-16 Table 13.5-1 cabinet row, quoted in NIST GCR 18-917-43 §4.9.2",
)


def _anchors() -> tuple[AnchorPosition, ...]:
    """Four anchors on a 600 x 500 mm pattern, the cabinet's base channel."""
    return (
        AnchorPosition(tag="front_left", x=Q("-300 mm"), y=Q("-250 mm")),
        AnchorPosition(tag="front_right", x=Q("300 mm"), y=Q("-250 mm")),
        AnchorPosition(tag="back_left", x=Q("-300 mm"), y=Q("250 mm")),
        AnchorPosition(tag="back_right", x=Q("300 mm"), y=Q("250 mm")),
    )


def height_factor() -> float:
    """H_f at the roof of this archetype, by Eq. 13.3-4."""
    return height_amplification_factor(
        height_ratio=HEIGHT_RATIO, fundamental_period=STRUCTURE_PERIOD
    )


def ductility_factor() -> float:
    """R_μ for this archetype, by Eq. 13.3-6."""
    return structure_ductility_reduction_factor(
        response_modification_factor=STRUCTURE_R, overstrength_factor=STRUCTURE_OMEGA
    )


def force_2022() -> ComponentForce:
    """The 2022-edition horizontal design force on the cabinet."""
    return component_seismic_design_force_asce_7_22(
        design_spectral_acceleration=DESIGN_SPECTRAL_ACCELERATION,
        component_weight=CABINET_WEIGHT,
        height_amplification=height_factor(),
        ductility_reduction=ductility_factor(),
        resonance_ductility=RESONANCE_DUCTILITY,
        component_strength=COMPONENT_STRENGTH,
    )


def force_2016() -> ComponentForce:
    """The 2016-edition horizontal design force on the same cabinet."""
    return component_seismic_design_force_asce_7_16(
        design_spectral_acceleration=DESIGN_SPECTRAL_ACCELERATION,
        component_weight=CABINET_WEIGHT,
        height_ratio=HEIGHT_RATIO,
        amplification=AMPLIFICATION,
        response_modification=RESPONSE_MODIFICATION,
    )


def vertical_force() -> Quantity:
    """The concurrent vertical force of §13.3.1.6, which lightens the resisting weight."""
    return component_vertical_seismic_force(
        design_spectral_acceleration=DESIGN_SPECTRAL_ACCELERATION,
        component_weight=CABINET_WEIGHT,
    )


def anchor_demand(*, with_vertical: bool) -> AnchorageDemand:
    """What the anchors carry under the 2022 force, with or without the vertical term."""
    weight = CABINET_WEIGHT
    if with_vertical:
        weight = Quantity(
            magnitude=CABINET_WEIGHT.magnitude - vertical_force().magnitude,
            unit=CABINET_WEIGHT.unit,
        )
    return anchor_pattern_demand(
        anchors=_anchors(),
        weight=weight,
        lateral_force=force_2022().force,
        height=CABINET_CENTROID,
        direction=(0.0, 1.0),
    )


def roof_cabinet_component_force_by_edition() -> dict[str, float]:
    """The figures this example's prose turns on."""
    new, old = force_2022(), force_2016()
    lightened, full = anchor_demand(with_vertical=True), anchor_demand(with_vertical=False)
    tension = lightened.governing.tension.to("N").magnitude
    unlightened = full.governing.tension.to("N").magnitude
    return {
        "force_2016_n": old.force.to("N").magnitude,
        "force_2022_n": new.force.to("N").magnitude,
        "force_2022_uncapped_n": new.from_equation.to("N").magnitude,
        "edition_ratio": new.force.to("N").magnitude / old.force.to("N").magnitude,
        "height_factor": height_factor(),
        "ductility_factor": ductility_factor(),
        "vertical_force_n": vertical_force().to("N").magnitude,
        "anchor_tension_n": tension,
        "anchor_tension_without_vertical_n": unlightened,
        "vertical_term_percent": 100.0 * (tension / unlightened - 1.0),
        "weight_share_percent": 100.0 * full.stability_ratio,
        "anchor_shear_n": lightened.governing.shear.to("N").magnitude,
    }


def main() -> None:
    print("--- the same cabinet, two editions")
    print(f"  ASCE/SEI 7-16: {force_2016()}")
    print(f"  ASCE/SEI 7-22: {force_2022()}")
    print(f"  H_f = {height_factor():.2f}, R_mu = {ductility_factor():.2f}")
    print(f"  concurrent vertical: {render(vertical_force(), pretty=True)}")
    print()
    print("--- into the anchors, under the 2022 force")
    demand = anchor_demand(with_vertical=True)
    print(f"  {demand}")
    for anchor in demand.anchors:
        print(f"    {anchor}")
    print()
    for name, value in roof_cabinet_component_force_by_edition().items():
        print(f"{name}: {value:.4g}")


if __name__ == "__main__":
    main()
