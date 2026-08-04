"""Worked example: sizing the press for an upset forging — why friction, not yield, sets the load.

Forging a billet flat looks like it should cost only what it takes to yield the metal — flow stress
times area. It costs far more, and the reason is friction. As the work spreads sideways under the
die, friction fights that outward flow and piles the pressure up toward the centre of the contact,
the "friction hill." The flatter the forging gets, the taller that hill, so the press force climbs
well above the bare yield load — the effect that governs press selection.

This example upsets a steel disc from 40 mm down to 25 mm tall at a 100 mm diameter. The 40-to-25
squeeze is a true strain of about 0.47, and with a strength coefficient of 600 MPa and a
strain-hardening exponent of 0.22 the metal's flow stress at that strain is about 508 MPa. On area
alone (a frictionless ideal) that would need about 3,990 kN — roughly 400 tonnes. But with a die
friction coefficient of 0.2 the friction hill multiplies the pressure by about 1.27, and the real
load climbs to about 5,060 kN, near 515 tonnes: a quarter more press, bought entirely by friction.
Squeeze the same disc to half the height and the friction hill grows again, pushing the load higher
still — the reason big forgings are struck in stages and lubricated hard. The example computes the
strain, the flow stress, and the load with and without friction so the friction penalty is explicit.

Run it directly (``python examples/forging_press_sizing.py``);
:func:`press_sizing` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    flow_stress_power_law,
    forging_true_strain,
    open_die_forging_load,
)
from anvilate.units import Quantity

INITIAL_HEIGHT = Quantity.parse("40 mm")
FINAL_HEIGHT = Quantity.parse("25 mm")
RADIUS = Quantity.parse("50 mm")  # 100 mm diameter disc
STRENGTH_COEFFICIENT = Quantity.parse("600 MPa")
STRAIN_HARDENING_EXPONENT = 0.22
FRICTION_COEFFICIENT = 0.2


def press_sizing() -> dict[str, float]:
    """Return the true strain, flow stress, and forging load with and without die friction."""
    strain = forging_true_strain(initial_height=INITIAL_HEIGHT, final_height=FINAL_HEIGHT)
    flow_stress = flow_stress_power_law(
        strength_coefficient=STRENGTH_COEFFICIENT,
        true_strain=strain,
        strain_hardening_exponent=STRAIN_HARDENING_EXPONENT,
    )
    load = open_die_forging_load(
        flow_stress=flow_stress,
        radius=RADIUS,
        height=FINAL_HEIGHT,
        friction_coefficient=FRICTION_COEFFICIENT,
    )
    frictionless = open_die_forging_load(
        flow_stress=flow_stress,
        radius=RADIUS,
        height=FINAL_HEIGHT,
        friction_coefficient=0.0,
    )
    return {
        "true_strain": strain,
        "flow_stress_mpa": flow_stress.to("MPa").magnitude,
        "load_kn": load.to("kN").magnitude,
        "frictionless_kn": frictionless.to("kN").magnitude,
    }


def main() -> None:
    p = press_sizing()
    print(f"true strain      : {p['true_strain']:.2f} (40 -> 25 mm upset)")
    print(f"flow stress      : {p['flow_stress_mpa']:.0f} MPa (Hollomon, K*eps^n)")
    print(
        f"frictionless load: {p['frictionless_kn']:.0f} kN "
        f"(~{p['frictionless_kn'] / 9.80665:.0f} tonnes, sigma*A)"
    )
    print(
        f"with friction    : {p['load_kn']:.0f} kN "
        f"(~{p['load_kn'] / 9.80665:.0f} tonnes, the friction hill adds "
        f"{p['load_kn'] / p['frictionless_kn'] - 1:.0%})"
    )
    print("  -> friction, not yield, sets the press; struck in stages and lubricated hard")


if __name__ == "__main__":
    main()
