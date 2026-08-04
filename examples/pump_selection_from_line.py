"""Worked example: from a pipe run's losses to the motor and the pump type it needs.

A pump is sized by the system it serves, not chosen off a shelf. This example closes that
loop: it takes a water line — an 8 m static lift plus friction over 200 m of 150 mm pipe and a
set of fittings — computes the total dynamic head the pump must produce, then turns that head
and the design flow into the numbers that actually specify the pump. The hydraulic power is
what reaches the fluid; divided by the pump's efficiency it becomes the larger shaft power the
motor has to deliver (about 30% more here, at 70% efficiency). The specific speed then says
what *kind* of pump fits — a low value, squarely in centrifugal territory. It is the whole
chain from pipe geometry to a motor nameplate.

Run it directly (``python examples/pump_selection_from_line.py``);
:func:`pump_duty` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    darcy_friction_factor,
    darcy_weisbach_head_loss,
    minor_loss_head,
    pump_hydraulic_power,
    pump_shaft_power,
    pump_specific_speed,
    reynolds_number,
)
from anvilate.units import Quantity

FLOW_RATE = Quantity.parse("0.05 m**3/s")
DIAMETER = Quantity.parse("0.15 m")
LENGTH = Quantity.parse("200 m")
ROUGHNESS = Quantity.parse("0.045 mm")  # commercial steel
KINEMATIC_VISCOSITY = Quantity.parse("1e-6 m**2/s")  # water at 20 C
DENSITY = Quantity.parse("1000 kg/m**3")
STATIC_LIFT = Quantity.parse("8 m")
FITTING_K = 0.5 + 4 * 0.9 + 2 * 0.15 + 1.0  # entrance + 4 elbows + 2 valves + exit
PUMP_EFFICIENCY = 0.70
PUMP_SPEED = Quantity.parse("1450 rpm")


def pump_duty() -> dict[str, float]:
    """Return the total head (m), hydraulic and shaft power (kW), and specific speed."""
    area = 3.141592653589793 / 4 * DIAMETER.to("m").magnitude ** 2  # pi*D^2/4
    velocity = Quantity(magnitude=FLOW_RATE.to("m**3/s").magnitude / area, unit="m/s")
    re = reynolds_number(
        velocity=velocity, diameter=DIAMETER, kinematic_viscosity=KINEMATIC_VISCOSITY
    )
    f = darcy_friction_factor(
        reynolds=re, relative_roughness=ROUGHNESS.to("m").magnitude / DIAMETER.to("m").magnitude
    )
    friction = (
        darcy_weisbach_head_loss(
            friction_factor=f, length=LENGTH, diameter=DIAMETER, velocity=velocity
        )
        .to("m")
        .magnitude
    )
    fittings = minor_loss_head(loss_coefficient=FITTING_K, velocity=velocity).to("m").magnitude
    total_head_m = STATIC_LIFT.to("m").magnitude + friction + fittings
    total_head = Quantity(magnitude=total_head_m, unit="m")
    hydraulic = pump_hydraulic_power(flow_rate=FLOW_RATE, head=total_head, density=DENSITY)
    shaft = pump_shaft_power(hydraulic_power=hydraulic, efficiency=PUMP_EFFICIENCY)
    n_s = pump_specific_speed(rotational_speed=PUMP_SPEED, flow_rate=FLOW_RATE, head=total_head)
    return {
        "total_head_m": total_head_m,
        "hydraulic_power_kw": hydraulic.to("kW").magnitude,
        "shaft_power_kw": shaft.to("kW").magnitude,
        "specific_speed": n_s,
    }


def main() -> None:
    d = pump_duty()
    print(f"total dynamic head : {d['total_head_m']:.1f} m (static lift + friction + fittings)")
    print(f"hydraulic power    : {d['hydraulic_power_kw']:.1f} kW into the fluid")
    print(f"shaft power        : {d['shaft_power_kw']:.1f} kW at the motor (70% efficiency)")
    kind = "radial / centrifugal" if d["specific_speed"] < 1.0 else "mixed / axial flow"
    print(f"specific speed     : N_s = {d['specific_speed']:.2f} -> {kind} impeller")


if __name__ == "__main__":
    main()
