"""Worked example: sizing the reinforcement in a concrete floor beam.

A reinforced-concrete beam is a composite: concrete takes the compression, steel the
tension. At ultimate strength the concrete crushes in a rectangular stress block and
the bars yield, and the moment the section carries is the steel force times the
internal lever arm — M_n = A_s·f_y·(d − a/2), with the block depth a set by force
balance. The whole of flexural RC design turns on that one relation and its inverse.

A 300 mm × 600 mm floor beam (effective depth 550 mm) in 30 MPa concrete with 420 MPa
bars is reinforced with 1500 mm² of steel — about three No. 25 bars. That develops a
nominal moment of 321 kN·m. Ask the section to carry a larger 400 kN·m demand and the
design inverse says it needs 1914 mm² — roughly a fourth bar. Neither number was
guessed: the forward gives the capacity of a chosen bar layout, the inverse the steel
a demand requires.

Anvilate evaluates the ACI 318 §22.3 closed form; the concrete and steel strengths are
the engineer's inputs, and the tension-controlled ductility check and the φ = 0.90
strength-reduction factor are theirs to apply on top. Run it directly
(``python examples/rc_floor_beam.py``); :func:`beam_capacity` and
:func:`steel_for_demand` are exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import rc_beam_nominal_moment, rc_tension_steel_for_moment
from anvilate.units import Quantity

CONCRETE_STRENGTH = Quantity.parse("30 MPa")  # f'c
STEEL_YIELD = Quantity.parse("420 MPa")  # f_y (Grade 420 bars)
BEAM_WIDTH = Quantity.parse("300 mm")
EFFECTIVE_DEPTH = Quantity.parse("550 mm")

PROVIDED_STEEL = Quantity.parse("1500 mm**2")  # ~3 No. 25 bars
DEMAND_MOMENT = Quantity.parse("400 kN*m")


def beam_capacity() -> Quantity:
    """The nominal moment the provided reinforcement develops."""
    return rc_beam_nominal_moment(
        steel_area=PROVIDED_STEEL,
        steel_yield=STEEL_YIELD,
        concrete_strength=CONCRETE_STRENGTH,
        beam_width=BEAM_WIDTH,
        effective_depth=EFFECTIVE_DEPTH,
    )


def steel_for_demand() -> Quantity:
    """The tension steel a larger moment demand requires (the design inverse)."""
    return rc_tension_steel_for_moment(
        required_moment=DEMAND_MOMENT,
        steel_yield=STEEL_YIELD,
        concrete_strength=CONCRETE_STRENGTH,
        beam_width=BEAM_WIDTH,
        effective_depth=EFFECTIVE_DEPTH,
    )


def main() -> None:
    cap = beam_capacity().to("kN*m").magnitude
    print(f"Provided {PROVIDED_STEEL} develops M_n = {cap:.0f} kN·m")
    need = steel_for_demand().to("mm**2").magnitude
    print(f"A {DEMAND_MOMENT} demand needs {need:.0f} mm² of tension steel")


if __name__ == "__main__":
    main()
