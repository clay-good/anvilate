"""Worked example: the shaft that passed on torque alone.

A gear-driven line shaft transmits 500 N*m of torque. Sized the usual quick way
-- torsion only, against a shear-yield allowable -- a 30 mm shaft clears it at
SF 2.14 and gets cut. But the same gear that delivers the torque also pushes on
the shaft through its separating and tangential loads, and over the bearing span
that works out to a 300 N*m bending moment. Bending and torsion act together, and
the shaft surface does not care which one yields it: the distortion-energy (von
Mises) stress combines them, sigma' = sqrt(sigma^2 + 3*tau^2), and on the 30 mm
shaft that reads 199 MPa against a 350 MPa yield -- SF 1.76, under the required
2.0.

The combined sizing inverse says the shaft needs about 31.3 mm to carry both
loads at SF 2.0; a 35 mm stock shaft passes with SF 2.80. Same shaft, same loads;
the torsion-only screen was not conservative, it left out half the stress. This
is why the ASME/Shigley shaft equation sizes on M and T together.

The yield strength (350 MPa) and the torsion-only shear allowable (0.577*Sy, the
von Mises shear yield) are declared inline as engineering inputs.

Run it directly (``python examples/geared_shaft_sizing.py``);
:func:`screen_geared_shaft` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    CrossSection,
    bending_stress,
    shaft_diameter_for_bending_torsion,
    shaft_torsional_stress,
    strength_scorecard,
    von_mises_bending_torsion,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

BENDING_MOMENT = Quantity.parse("300 N*m")
TORQUE = Quantity.parse("500 N*m")
YIELD_STRENGTH = Quantity.parse("350 MPa")
SHEAR_ALLOWABLE = Quantity.parse("202 MPa")  # 0.577*Sy, the von Mises shear yield
CANDIDATE_DIAMETER = Quantity.parse("30 mm")  # sized on torsion alone
UPSIZED_DIAMETER = Quantity.parse("35 mm")  # sized for combined loading
REQUIRED_SF = 2.0


def _combined_von_mises(diameter: Quantity) -> Quantity:
    """The von Mises stress on a solid shaft carrying both loads at ``diameter``."""
    section = CrossSection.solid_circular(diameter=diameter)
    sigma = bending_stress(moment=BENDING_MOMENT, section_modulus=section.section_modulus)
    tau = shaft_torsional_stress(torque=TORQUE, diameter=diameter)
    return von_mises_bending_torsion(bending_stress=sigma, shear_stress=tau)


def combined_diameter_floor() -> Quantity:
    """The least diameter for both loads at the required safety factor."""
    return shaft_diameter_for_bending_torsion(
        bending_moment=BENDING_MOMENT,
        torque=TORQUE,
        yield_strength=YIELD_STRENGTH,
        required_safety_factor=REQUIRED_SF,
    )


def screen_geared_shaft() -> Scorecard:
    """Screen the 30 mm shaft two ways -- torsion only (the quick screen) and the
    combined von Mises criterion -- then the 35 mm upsize on the combined check."""
    torsion_only = shaft_torsional_stress(torque=TORQUE, diameter=CANDIDATE_DIAMETER)
    return Scorecard(
        entries=(
            strength_scorecard(
                "torsion-only screen @ 30 mm",
                stress=torsion_only,
                allowable=SHEAR_ALLOWABLE,
                required=REQUIRED_SF,
            ),
            strength_scorecard(
                "combined bending+torsion @ 30 mm",
                stress=_combined_von_mises(CANDIDATE_DIAMETER),
                allowable=YIELD_STRENGTH,
                required=REQUIRED_SF,
            ),
            strength_scorecard(
                "combined bending+torsion @ 35 mm",
                stress=_combined_von_mises(UPSIZED_DIAMETER),
                allowable=YIELD_STRENGTH,
                required=REQUIRED_SF,
            ),
        )
    )


def main() -> None:
    card = screen_geared_shaft()
    for entry in card.entries:
        print(entry)
    print(f"combined diameter floor: {combined_diameter_floor().to('mm').magnitude:.2f} mm")
    print(card)


if __name__ == "__main__":
    main()
