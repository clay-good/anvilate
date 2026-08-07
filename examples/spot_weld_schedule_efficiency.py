"""Worked example: why a spot welder needs thousands of amps — most heat never reaches the weld.

Resistance spot welding melts a nugget with the workpiece's own resistance: pass a big current
through the clamped sheets and the interface heats by Joule's law, Q = I²·R·t. The trouble is that
the copper electrodes are water-cooled and the surrounding sheet is a big heat sink, so most of the
Joule heat conducts away before it can do any melting. Only a small fraction — often about a tenth —
actually goes into the nugget. That poor efficiency, combined with the very short weld times used to
avoid distortion, is exactly why the current has to be enormous: the machine must generate ten times
the heat the nugget needs, in a fifth of a second.

This example welds two steel sheets. The nugget — about 25 mm³ of steel — needs roughly 198 J to
reach melting and fuse (density 7850 kg/m³, specific heat 500 J/kg·K, a 1480 K rise, latent heat
270 kJ/kg). At a typical 10% thermal efficiency the machine must actually generate about 1982 J at
the interface. Through a contact resistance of 100 µΩ over a 0.2 s weld, delivering that heat needs
a current of about 10 kA. The example reports the nugget melting energy, the Joule heat that implies
10% efficiency, and the current a 0.2 s schedule needs to supply it — the chain from nugget size to
weld schedule, and the reason the number lands in kiloamperes.

Run it directly (``python examples/spot_weld_schedule_efficiency.py``);
:func:`spot_weld_schedule` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    spot_weld_current_for_heat,
    spot_weld_heat_generated,
    spot_weld_nugget_melting_energy,
)
from anvilate.units import Quantity

NUGGET_VOLUME = Quantity.parse("25 mm**3")
STEEL_DENSITY = Quantity.parse("7850 kg/m**3")
STEEL_SPECIFIC_HEAT = Quantity.parse("500 J/(kg*K)")
MELTING_TEMPERATURE_RISE = Quantity.parse("1480 K")
LATENT_HEAT_OF_FUSION = Quantity.parse("270 kJ/kg")
THERMAL_EFFICIENCY = 0.10
CONTACT_RESISTANCE = Quantity.parse("100 uohm")
WELD_TIME = Quantity.parse("0.2 s")


def spot_weld_schedule() -> dict[str, float]:
    """Return the nugget melting energy, the Joule heat at 10% efficiency, and the current."""
    nugget_energy = spot_weld_nugget_melting_energy(
        nugget_volume=NUGGET_VOLUME,
        density=STEEL_DENSITY,
        specific_heat=STEEL_SPECIFIC_HEAT,
        temperature_rise=MELTING_TEMPERATURE_RISE,
        latent_heat_of_fusion=LATENT_HEAT_OF_FUSION,
    )
    required_heat = Quantity(
        magnitude=nugget_energy.to("J").magnitude / THERMAL_EFFICIENCY, unit="J"
    )
    current = spot_weld_current_for_heat(
        target_heat=required_heat, contact_resistance=CONTACT_RESISTANCE, weld_time=WELD_TIME
    )
    # Confirm that current back-produces the required heat through Joule's law.
    check_heat = spot_weld_heat_generated(
        weld_current=current, contact_resistance=CONTACT_RESISTANCE, weld_time=WELD_TIME
    )
    return {
        "nugget_energy_j": nugget_energy.to("J").magnitude,
        "required_heat_j": required_heat.to("J").magnitude,
        "weld_current_ka": current.to("kA").magnitude,
        "check_heat_j": check_heat.to("J").magnitude,
    }


def main() -> None:
    d = spot_weld_schedule()
    print(f"nugget melting energy: {d['nugget_energy_j']:.0f} J")
    print(f"Joule heat needed at 10% efficiency: {d['required_heat_j']:.0f} J")
    print(
        f"weld current for a 0.2 s schedule: {d['weld_current_ka']:.1f} kA "
        f"-> kiloamperes, because most heat is lost"
    )


if __name__ == "__main__":
    main()
