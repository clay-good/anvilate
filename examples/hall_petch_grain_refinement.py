"""Worked example: how much grain refinement a steel strength target needs.

A low-carbon steel has a friction stress of 50 MPa (its strength at very coarse grain) and a
Hall-Petch slope of 0.74 MPa·√m. As delivered its grains average 40 µm. A design calls for a yield
strength of 300 MPa — how fine must the grains be refined to reach it, and what does the current
grain size actually deliver?

At 40 µm the Hall-Petch relation gives only σ_y = 50 + 0.74/√(40e-6) ≈ 167 MPa. To reach 300 MPa the
grains must be refined to d = [0.74/(300−50 in MPa)]² ≈ 8.8 µm — a roughly four-fold refinement, the
kind a controlled-rolling or thermomechanical schedule is designed to produce.

Run it directly (``python examples/hall_petch_grain_refinement.py``);
:func:`grain_refinement_target` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    hall_petch_grain_diameter_for_yield,
    hall_petch_yield_strength,
)
from anvilate.units import Quantity

FRICTION_STRESS = Quantity.parse("50 MPa")
HALL_PETCH_SLOPE = Quantity.parse("0.74 MPa*m**0.5")
CURRENT_GRAIN = Quantity.parse("40 um")
TARGET_YIELD = Quantity.parse("300 MPa")


def grain_refinement_target() -> dict[str, float]:
    """Return the current yield strength (MPa) and the grain size (µm) a target yield requires."""
    current_yield = hall_petch_yield_strength(
        friction_stress=FRICTION_STRESS,
        strengthening_coefficient=HALL_PETCH_SLOPE,
        grain_diameter=CURRENT_GRAIN,
    )
    required_grain = hall_petch_grain_diameter_for_yield(
        friction_stress=FRICTION_STRESS,
        strengthening_coefficient=HALL_PETCH_SLOPE,
        yield_strength=TARGET_YIELD,
    )
    return {
        "current_yield_mpa": current_yield.to("MPa").magnitude,
        "required_grain_um": required_grain.to("um").magnitude,
    }


def main() -> None:
    d = grain_refinement_target()
    print("Low-carbon steel, sigma_0 = 50 MPa, k = 0.74 MPa*sqrt(m):")
    print(f"  yield at 40 um grain  : {d['current_yield_mpa']:.0f} MPa")
    print(f"  grain for 300 MPa     : {d['required_grain_um']:.1f} um")


if __name__ == "__main__":
    main()
