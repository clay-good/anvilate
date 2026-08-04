"""Worked example: two ways to find a water main's head loss, and why utilities pick the shortcut.

A water main's friction loss can be found the rigorous way — a Reynolds number, a roughness
ratio, a Swamee-Jain friction factor, then Darcy-Weisbach — or the empirical way, Hazen-Williams,
which needs only a single roughness coefficient C and no fluid properties at all. This example
runs both on the same 150 mm cast-iron main carrying 50 L/s over 100 m and shows they land within
about 15% of each other. That closeness is the whole reason water utilities reach for
Hazen-Williams: for water near ambient temperature it is accurate enough and far simpler to
tabulate across a distribution network. The example also runs the capacity inverse — given a head
budget, how much flow the main can pass — the sizing question a network model actually asks.

Run it directly (``python examples/water_main_hazen_williams.py``);
:func:`main_head_loss` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import (
    darcy_friction_factor,
    darcy_weisbach_head_loss,
    hazen_williams_flow_capacity,
    hazen_williams_head_loss,
    reynolds_number,
)
from anvilate.units import Quantity

FLOW = Quantity.parse("0.05 m**3/s")  # 50 L/s
DIAMETER = Quantity.parse("0.15 m")
LENGTH = Quantity.parse("100 m")
ROUGHNESS = Quantity.parse("0.26 mm")  # cast iron, for the Darcy path
HW_COEFFICIENT = 130.0  # Hazen-Williams C for cast iron
KINEMATIC_VISCOSITY = Quantity.parse("1e-6 m**2/s")  # water at 20 C


def main_head_loss() -> dict[str, float]:
    """Return the Darcy and Hazen-Williams head losses (m) and the HW capacity (L/s)."""
    velocity = Quantity(
        magnitude=FLOW.to("m**3/s").magnitude / (pi / 4 * DIAMETER.to("m").magnitude ** 2),
        unit="m/s",
    )
    re = reynolds_number(
        velocity=velocity, diameter=DIAMETER, kinematic_viscosity=KINEMATIC_VISCOSITY
    )
    f = darcy_friction_factor(
        reynolds=re, relative_roughness=ROUGHNESS.to("m").magnitude / DIAMETER.to("m").magnitude
    )
    darcy = (
        darcy_weisbach_head_loss(
            friction_factor=f, length=LENGTH, diameter=DIAMETER, velocity=velocity
        )
        .to("m")
        .magnitude
    )
    hw = (
        hazen_williams_head_loss(
            flow_rate=FLOW,
            pipe_diameter=DIAMETER,
            length=LENGTH,
            roughness_coefficient=HW_COEFFICIENT,
        )
        .to("m")
        .magnitude
    )
    # Capacity inverse: the flow the main passes for a 6 m head budget.
    capacity = (
        hazen_williams_flow_capacity(
            head_loss=Quantity.parse("6 m"),
            pipe_diameter=DIAMETER,
            length=LENGTH,
            roughness_coefficient=HW_COEFFICIENT,
        )
        .to("m**3/s")
        .magnitude
    )
    return {
        "darcy_head_m": darcy,
        "hazen_williams_head_m": hw,
        "ratio": hw / darcy,
        "capacity_at_6m_lps": capacity * 1000.0,
    }


def main() -> None:
    r = main_head_loss()
    print(f"Darcy-Weisbach  : {r['darcy_head_m']:.2f} m (Reynolds + friction factor)")
    print(f"Hazen-Williams  : {r['hazen_williams_head_m']:.2f} m (just C = {HW_COEFFICIENT:.0f})")
    print(f"  agree within {abs(1 - r['ratio']) * 100:.0f}% — HW is the water-network shortcut")
    print(f"capacity @ 6 m head : {r['capacity_at_6m_lps']:.0f} L/s")


if __name__ == "__main__":
    main()
