"""Worked example: the load a fixed-fixed beam carries past first yield.

Elastic design stops a beam at first yield -- the load that first takes any fibre to
the yield stress. For a fixed-fixed beam under a uniform load that happens at the
built-in ends, where the elastic moment w*L^2/12 is largest, so the first-yield load
is w_y = 12*M_y/L^2 with M_y = Z_e*S_y. But a ductile indeterminate beam does not
fail there: the ends yield into plastic hinges, the moment redistributes to midspan,
a third hinge forms, and only then does a mechanism collapse it -- at
w_c = 16*M_p/L^2 with M_p = Z_p*S_y.

The gap between the two is large, and it comes from two independent reserves. The
section shape factor Z_p/Z_e (1.5 for this rectangle) is how much more a fully
plastic section carries than a just-yielded one; the redistribution factor 16/12 is
how much more an indeterminate beam carries once its extra hinges form. Multiplied,
a rectangular fixed-fixed beam collapses at exactly 2.0x its first-yield load. Here a
6 m beam under 100 kN/m fails a 1.5 safety factor on the elastic first-yield load
(SF 1.25) but passes comfortably on the true plastic collapse load (2.50) -- the
elastic screen was rejecting a beam the structure carries with margin to spare.

The reserve is only real if the section is compact enough not to buckle locally and
the steel ductile enough to form and rotate the hinges; plastic design assumes both.
The section and material are declared inline.

Run it directly (``python examples/plastic_collapse_reserve.py``);
:func:`screen_collapse_reserve` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    fixed_fixed_plastic_collapse_udl,
    plastic_moment,
    rectangular_plastic_section_modulus,
    rectangular_second_moment,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

SPAN = Quantity.parse("6 m")
WIDTH = Quantity.parse("100 mm")
HEIGHT = Quantity.parse("300 mm")
YIELD = Quantity.parse("250 MPa")
APPLIED_UDL = Quantity.parse("100 kN/m")
REQUIRED_SAFETY_FACTOR = 1.5


def _elastic_first_yield_udl() -> Quantity:
    # First yield at the built-in ends: w_y = 12*M_y/L^2, M_y = Z_e*S_y.
    z_e = rectangular_second_moment(WIDTH, HEIGHT).to("mm**4").magnitude / (
        HEIGHT.to("mm").magnitude / 2
    )
    m_y = z_e * YIELD.to("MPa").magnitude  # N*mm
    length = SPAN.to("mm").magnitude
    return Quantity(magnitude=12 * m_y / length**2, unit="N/mm")  # N/mm = kN/m


def _plastic_collapse_udl() -> Quantity:
    m_p = plastic_moment(
        plastic_section_modulus=rectangular_plastic_section_modulus(WIDTH, HEIGHT),
        yield_strength=YIELD,
    )
    return fixed_fixed_plastic_collapse_udl(plastic_moment_capacity=m_p, span=SPAN)


def screen_collapse_reserve() -> Scorecard:
    """Screen the applied load against both the elastic first-yield load and the true
    plastic collapse load (safety factor = capacity / applied, required >= 1.5)."""
    applied = APPLIED_UDL.to("N/m").magnitude
    entries = [
        ScorecardEntry.from_safety_factor(
            "first-yield (elastic)",
            computed=_elastic_first_yield_udl().to("N/m").magnitude / applied,
            required=REQUIRED_SAFETY_FACTOR,
        ),
        ScorecardEntry.from_safety_factor(
            "plastic collapse",
            computed=_plastic_collapse_udl().to("N/m").magnitude / applied,
            required=REQUIRED_SAFETY_FACTOR,
        ),
    ]
    return Scorecard(entries=tuple(entries))


def main() -> None:
    print(f"elastic first-yield load: {_elastic_first_yield_udl().to('kN/m').magnitude:.0f} kN/m")
    print(f"plastic collapse load:    {_plastic_collapse_udl().to('kN/m').magnitude:.0f} kN/m")
    print(screen_collapse_reserve())


if __name__ == "__main__":
    main()
