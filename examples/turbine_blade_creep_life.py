"""Worked example: how far a small temperature rise cuts a hot component's creep life.

A component running under steady stress at high temperature fails by creep rupture long
before it yields, and the Larson-Miller parameter is the standard screen: at the service
stress the material's master curve gives a parameter P, and P together with the metal
temperature fixes the time to rupture. The sensitivity to temperature is the headline —
creep life is exponential in temperature, so a modest overshoot is expensive.

Here a blade alloy has a master-curve parameter P = 27,000 (constant C = 20) at its
operating stress. At the design metal temperature of 1050 K it should last on the order
of 518,000 hours, but the same 100 K hotter — an 1150 K excursion — collapses that to
about 3,000 hours: a ~99% loss of life for under a 10% temperature rise.

The example uses the Larson-Miller rupture-life inverse at two temperatures and the
temperature-limit inverse to report the hottest the blade may run for a 100,000-hour life.

Run it directly (``python examples/turbine_blade_creep_life.py``);
:func:`creep_life_summary` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    larson_miller_rupture_life,
    larson_miller_temperature_limit,
)
from anvilate.units import Quantity

PARAMETER = 27_000.0  # master-curve Larson-Miller parameter at the service stress
CONSTANT = 20.0
DESIGN_TEMPERATURE = Quantity.parse("1050 K")
EXCURSION_TEMPERATURE = Quantity.parse("1150 K")
TARGET_LIFE = Quantity.parse("100000 hour")


def creep_life_summary() -> dict[str, float]:
    """Return the rupture life at two temperatures and the temperature limit for the target life."""
    design_life = larson_miller_rupture_life(
        parameter=PARAMETER, temperature=DESIGN_TEMPERATURE, constant=CONSTANT
    )
    excursion_life = larson_miller_rupture_life(
        parameter=PARAMETER, temperature=EXCURSION_TEMPERATURE, constant=CONSTANT
    )
    temperature_limit = larson_miller_temperature_limit(
        parameter=PARAMETER, rupture_time=TARGET_LIFE, constant=CONSTANT
    )
    return {
        "design_life_hours": design_life.to("hour").magnitude,
        "excursion_life_hours": excursion_life.to("hour").magnitude,
        "temperature_limit_K": temperature_limit.to("K").magnitude,
    }


def main() -> None:
    summary = creep_life_summary()
    design = summary["design_life_hours"]
    excursion = summary["excursion_life_hours"]
    shorter = 100 * (1 - excursion / design)
    print(f"rupture life at 1050 K: {design:,.0f} hours")
    print(f"rupture life at 1150 K: {excursion:,.0f} hours  ({shorter:.0f}% shorter)")
    print(f"hottest for a 100,000 h life: {summary['temperature_limit_K']:.0f} K")


if __name__ == "__main__":
    main()
