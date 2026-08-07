"""Worked example: why a laser cutter has a thickness ceiling — the cut is a power balance.

Laser cutting has no tool and no force to run out of; what it runs out of is power. The beam has to
deliver enough energy to melt every scrap of metal the kerf sweeps up as it advances, so speed,
thickness, and power trade off against one another through a single balance. Slow the cut and the
same beam melts a thicker plate; speed it up and the melt front outpaces the power, the beam stops
reaching the underside, and the plate is scored but not severed. That is why every laser has a rated
thickness for each material — it is the point where the power balance runs out at a usable speed.

This example cuts mild steel (specific heat 500 J/kg·K, melting rise 1480 K, latent heat of fusion
270 kJ/kg) with a 2 kW beam coupling at 40% into a 0.3 mm kerf. The specific removal energy comes to
about 1.01 MJ/kg — the price per kilogram of kerf. At that energy the beam severs 5 mm plate at
about 4 m/min. Ask instead for the ceiling: at a slow, reliable 2 m/min the same 2 kW reaches about
10 mm before the balance fails. The example computes the removal energy, the speed on 5 mm, and max
thickness at 2 m/min, so the trade between speed and reach is explicit — the numbers that decide
whether a plate belongs on this machine or the next size up.

Run it directly (``python examples/laser_cut_thickness_limit.py``);
:func:`laser_cut_envelope` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    laser_cutting_speed,
    laser_max_cut_thickness,
    laser_specific_removal_energy,
)
from anvilate.units import Quantity

SPECIFIC_HEAT = Quantity.parse("500 J/(kg*K)")
MELTING_TEMPERATURE_RISE = Quantity.parse("1480 K")
LATENT_HEAT_OF_FUSION = Quantity.parse("270 kJ/kg")
DENSITY = Quantity.parse("7850 kg/m**3")
BEAM_POWER = Quantity.parse("2000 W")
COUPLING_EFFICIENCY = 0.40
KERF_WIDTH = Quantity.parse("0.3 mm")
DESIGN_THICKNESS = Quantity.parse("5 mm")
RELIABLE_SPEED = Quantity.parse("2 m/min")


def laser_cut_envelope() -> dict[str, float]:
    """Return the removal energy, the speed on 5 mm, and the thickness ceiling at 2 m/min."""
    e_m = laser_specific_removal_energy(
        specific_heat=SPECIFIC_HEAT,
        temperature_rise=MELTING_TEMPERATURE_RISE,
        latent_heat_of_fusion=LATENT_HEAT_OF_FUSION,
    )
    speed = laser_cutting_speed(
        beam_power=BEAM_POWER,
        coupling_efficiency=COUPLING_EFFICIENCY,
        thickness=DESIGN_THICKNESS,
        kerf_width=KERF_WIDTH,
        density=DENSITY,
        specific_removal_energy=e_m,
    )
    t_max = laser_max_cut_thickness(
        beam_power=BEAM_POWER,
        coupling_efficiency=COUPLING_EFFICIENCY,
        cutting_speed=RELIABLE_SPEED,
        kerf_width=KERF_WIDTH,
        density=DENSITY,
        specific_removal_energy=e_m,
    )
    return {
        "specific_removal_energy_mj_kg": e_m.to("MJ/kg").magnitude,
        "speed_on_5mm_m_min": speed.to("m/min").magnitude,
        "max_thickness_at_2m_min_mm": t_max.to("mm").magnitude,
    }


def main() -> None:
    d = laser_cut_envelope()
    print(f"specific removal energy: {d['specific_removal_energy_mj_kg']:.2f} MJ/kg")
    print(f"cutting speed on 5 mm plate: {d['speed_on_5mm_m_min']:.1f} m/min")
    print(
        f"thickness ceiling at 2 m/min: {d['max_thickness_at_2m_min_mm']:.1f} mm "
        f"-> thicker plate needs a slower cut or a bigger laser"
    )


if __name__ == "__main__":
    main()
