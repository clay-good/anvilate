"""Worked example: why the lab beaker is borosilicate and the tumbler is not.

Pour boiling water into a cold glass and it may crack; do it to a Pyrex beaker and
it will not. Both are glass with about the same 50 MPa tensile strength, and glass
is brittle, so a surface put into tension near that value fractures. What separates
them is how much tension a sudden temperature change raises.

When a surface is quenched, it wants to shrink but the warm interior holds it, and
the resulting biaxial surface tension is sigma = E*alpha*dT/(1-nu) -- proportional
to the thermal expansion coefficient. Under a 150 K shock the soda-lime tumbler
(alpha = 9e-6/K) develops 121 MPa of surface tension, well over its 50 MPa strength
(0.41): it shatters. The borosilicate beaker's alpha is nearly three times lower
(3.3e-6/K), so the same shock raises only 40 MPa -- below strength, with margin
(1.26): it survives.

Thermal-shock resistance is not about being stronger; it is about expanding less.
The low-expansion glass wins the quench not by holding more stress but by
generating less, which is the whole reason cookware and labware are borosilicate.
The strengths and expansion coefficients are material data, declared inline like
any allowable.

Run it directly (``python examples/glass_thermal_shock.py``);
:func:`screen_thermal_shock` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import thermal_shock_stress
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

QUENCH = Quantity.parse("150 K")
TENSILE_STRENGTH = Quantity.parse("50 MPa")

GLASSES = {
    "soda-lime tumbler": {
        "elastic_modulus": Quantity.parse("70 GPa"),
        "thermal_expansion_coefficient": Quantity.parse("9e-6 1/K"),
        "poisson": 0.22,
    },
    "borosilicate beaker": {
        "elastic_modulus": Quantity.parse("64 GPa"),
        "thermal_expansion_coefficient": Quantity.parse("3.3e-6 1/K"),
        "poisson": 0.20,
    },
}


def shock_stress(props: dict) -> Quantity:
    """The thermal-shock surface stress of a glass under the quench."""
    return thermal_shock_stress(
        elastic_modulus=props["elastic_modulus"],
        thermal_expansion_coefficient=props["thermal_expansion_coefficient"],
        temperature_change=QUENCH,
        poisson=props["poisson"],
    )


def screen_thermal_shock() -> Scorecard:
    """Screen each glass: its thermal-shock surface tension must stay under the
    tensile strength (safety factor = strength / shock stress)."""
    strength = TENSILE_STRENGTH.to("MPa").magnitude
    entries = [
        ScorecardEntry.from_safety_factor(
            name, computed=strength / shock_stress(props).to("MPa").magnitude, required=1.0
        )
        for name, props in GLASSES.items()
    ]
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, props in GLASSES.items():
        print(f"{name}: shock stress {shock_stress(props).to('MPa').magnitude:.0f} MPa")
    print(screen_thermal_shock())


if __name__ == "__main__":
    main()
