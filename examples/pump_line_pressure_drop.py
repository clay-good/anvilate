"""Worked example: the fittings on a pipe run cost as much head as tens of meters of pipe.

Sizing a pump means adding up everything the fluid loses on the way. The straight pipe is
the obvious part — Darcy-Weisbach friction over its length — but the entrance, the valves,
the elbows and the exit each take their own bite, and on a run with any real number of
fittings those minor losses are not minor. This example pushes water at 2 m/s through 100 m
of 100 mm commercial-steel line with a typical set of fittings, finds the friction head and
the fitting head separately, and shows the fittings alone add the equivalent of nearly 30 m
of extra pipe — the difference between a pump that works and one that's a size too small.
Every loss then converts to the pressure the pump must actually supply.

Run it directly (``python examples/pump_line_pressure_drop.py``);
:func:`line_losses` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    darcy_friction_factor,
    darcy_weisbach_head_loss,
    minor_loss_head,
    pipe_pressure_drop,
    reynolds_number,
)
from anvilate.units import Quantity

VELOCITY = Quantity.parse("2 m/s")
DIAMETER = Quantity.parse("0.1 m")
LENGTH = Quantity.parse("100 m")
ROUGHNESS = Quantity.parse("0.045 mm")  # commercial steel
KINEMATIC_VISCOSITY = Quantity.parse("1e-6 m**2/s")  # water at 20 C
DENSITY = Quantity.parse("998 kg/m**3")

# Fitting loss coefficients: entrance + 2 gate valves + 4 elbows + exit.
FITTING_K = 0.5 + 2 * 0.15 + 4 * 0.9 + 1.0


def line_losses() -> dict[str, float]:
    """Return the friction and fitting heads, equivalent fitting length (m), and drop (kPa)."""
    re = reynolds_number(
        velocity=VELOCITY, diameter=DIAMETER, kinematic_viscosity=KINEMATIC_VISCOSITY
    )
    rel_roughness = ROUGHNESS.to("m").magnitude / DIAMETER.to("m").magnitude
    f = darcy_friction_factor(reynolds=re, relative_roughness=rel_roughness)
    friction = (
        darcy_weisbach_head_loss(
            friction_factor=f, length=LENGTH, diameter=DIAMETER, velocity=VELOCITY
        )
        .to("m")
        .magnitude
    )
    fittings = minor_loss_head(loss_coefficient=FITTING_K, velocity=VELOCITY).to("m").magnitude
    total_head = Quantity(magnitude=friction + fittings, unit="m")
    drop = pipe_pressure_drop(head_loss=total_head, density=DENSITY).to("kPa").magnitude
    # Length of straight pipe that would lose the same head as the fittings: f*(L_eq/D) = sum K.
    equivalent_length = FITTING_K * DIAMETER.to("m").magnitude / f
    return {
        "reynolds": re,
        "friction_factor": f,
        "friction_head_m": friction,
        "fitting_head_m": fittings,
        "equivalent_fitting_length_m": equivalent_length,
        "pressure_drop_kpa": drop,
    }


def main() -> None:
    r = line_losses()
    print(f"Reynolds number : {r['reynolds']:,.0f}  (turbulent), f = {r['friction_factor']:.4f}")
    print(f"friction head   : {r['friction_head_m']:.2f} m over 100 m of pipe")
    print(f"fitting head    : {r['fitting_head_m']:.2f} m from the valves, elbows, entrance, exit")
    eq = r["equivalent_fitting_length_m"]
    print(f"  -> those fittings lose as much head as {eq:.0f} m of extra straight pipe")
    print(f"pump must supply : {r['pressure_drop_kpa']:.1f} kPa to overcome the run")


if __name__ == "__main__":
    main()
