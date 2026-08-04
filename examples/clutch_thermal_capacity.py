"""Worked example: the heat a clutch soaks up per engagement, and why gripping harder won't cool it.

Sizing a clutch is two problems: the torque it must transmit, and the heat it must survive. The
torque comes from the friction geometry — but the heat is a separate, often-overlooked number, and
this example works it. A motor of 0.4 kg·m² inertia spinning at 300 rad/s engages a driven load of
1.5 kg·m² at rest; the clutch drags them to a common speed, and the kinetic energy lost in the slip
is dumped as heat into the friction faces. The striking result is that this energy depends only on
the inertias and the speed gap, not on the clutch torque: a stronger clutch reaches the common speed
faster but burns exactly the same total heat, so a clutch that overheats cannot be fixed by clamping
harder — only by more friction area, more mass, or better cooling. The example also shows the brake
limit, where the driven side is effectively infinite, and the clutch energy collapses to the full
½·I·ω² kinetic energy a brake would absorb.

Run it directly (``python examples/clutch_thermal_capacity.py``);
:func:`engagement_heat` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import brake_absorbed_energy, clutch_engagement_energy
from anvilate.units import Quantity

DRIVING_INERTIA = Quantity.parse("0.4 kg*m**2")
DRIVEN_INERTIA = Quantity.parse("1.5 kg*m**2")
SPEED_DIFFERENCE = Quantity.parse("300 rad/s")


def engagement_heat() -> dict[str, float]:
    """Return the clutch slip energy and the brake-limit energy of the driving side (kJ)."""
    slip = clutch_engagement_energy(
        driving_inertia=DRIVING_INERTIA,
        driven_inertia=DRIVEN_INERTIA,
        speed_difference=SPEED_DIFFERENCE,
    )
    brake_limit = brake_absorbed_energy(inertia=DRIVING_INERTIA, angular_velocity=SPEED_DIFFERENCE)
    return {
        "slip_energy_kj": slip.to("kJ").magnitude,
        "brake_limit_kj": brake_limit.to("kJ").magnitude,
    }


def main() -> None:
    e = engagement_heat()
    print(f"clutch slip energy per engagement : {e['slip_energy_kj']:.2f} kJ")
    print(f"brake-limit energy (½·I·ω²)       : {e['brake_limit_kj']:.2f} kJ")
    print(
        "  -> the slip heat is fixed by inertia and speed gap, not torque; grip harder ≠ run cooler"
    )


if __name__ == "__main__":
    main()
