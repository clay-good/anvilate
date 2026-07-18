"""Worked example: the softer rail foundation is the harder one on the rail.

A crane wheel presses down on a rail, and the rail rests not on discrete supports
but on a continuous elastic foundation -- a grouted bed, an elastomeric pad, the
soil under a sleeper. Hetenyi's beam-on-elastic-foundation theory says the wheel
load spreads out over a length set by the characteristic parameter
beta = (k / 4EI)^(1/4), and the rail's peak bending moment right under the wheel is
M_max = P / (4*beta).

The counterintuitive part is the foundation stiffness. A *stiffer* bed (larger k)
gives a larger beta, concentrates the load over a shorter length -- and *lowers*
the peak moment, because the nearby foundation carries more of the wheel. A *softer*
bed lets the load spread out, so the rail must bend further and carry a higher
moment itself. Here the same 100 kN wheel on the same rail sees 254 MPa on a stiff
grout bed (k = 100) but 380 MPa on a soft pad (k = 20): the stiff bed passes the
1.5 safety factor on the 480 MPa rail steel (SF 1.89) while the soft pad fails
(1.26). The intuition that a firmer support is the more demanding case is exactly
backwards for a beam on an elastic foundation.

The rail section (I, section modulus) and the foundation moduli are declared inline
like any design input.

Run it directly (``python examples/crane_rail_on_foundation.py``);
:func:`screen_crane_rail` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import beam_on_elastic_foundation_max_moment
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

WHEEL_LOAD = Quantity.parse("100 kN")
RAIL_SECOND_MOMENT = Quantity.parse("1.7e6 mm**4")
RAIL_SECTION_MODULUS = Quantity.parse("34000 mm**3")
RAIL_ELASTIC_MODULUS = Quantity.parse("210 GPa")
RAIL_YIELD = Quantity.parse("480 MPa")
REQUIRED_SAFETY_FACTOR = 1.5

FOUNDATIONS = {
    "stiff grout bed (k 100)": Quantity.parse("100 N/mm**2"),
    "soft elastomeric pad (k 20)": Quantity.parse("20 N/mm**2"),
}


def _rail_bending_stress(foundation_modulus: Quantity) -> Quantity:
    moment = beam_on_elastic_foundation_max_moment(
        load=WHEEL_LOAD,
        foundation_modulus=foundation_modulus,
        elastic_modulus=RAIL_ELASTIC_MODULUS,
        second_moment=RAIL_SECOND_MOMENT,
    )
    stress = moment.to("N*mm").magnitude / RAIL_SECTION_MODULUS.to("mm**3").magnitude
    return Quantity(magnitude=stress, unit="MPa")


def screen_crane_rail() -> Scorecard:
    """Screen the rail bending stress against yield for each foundation stiffness
    (safety factor = yield / peak bending stress, required >= 1.5)."""
    yield_strength = RAIL_YIELD.to("MPa").magnitude
    entries = []
    for name, foundation_modulus in FOUNDATIONS.items():
        stress = _rail_bending_stress(foundation_modulus).to("MPa").magnitude
        entries.append(
            ScorecardEntry.from_safety_factor(
                name,
                computed=yield_strength / stress,
                required=REQUIRED_SAFETY_FACTOR,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, foundation_modulus in FOUNDATIONS.items():
        stress = _rail_bending_stress(foundation_modulus)
        print(f"{name}: peak rail bending stress {stress.to('MPa').magnitude:.0f} MPa")
    print(screen_crane_rail())


if __name__ == "__main__":
    main()
