"""Worked example: colligative properties of salt water — de-icing and desalination.

Colligative properties depend only on how many dissolved particles are present, so one solute —
table salt — shows up in two very different engineering problems. Spread on a road it lowers water's
freezing point and keeps ice from forming; held back by a membrane it exerts an osmotic pressure
that a desalination plant must overcome. Both follow from the particle concentration and van 't Hoff
factor (2 for NaCl, which splits into Na+ and Cl-).

This example takes seawater-strength salt. As a 1.0 molal NaCl solution, the freezing-point
depression is about 3.7 K (i = 2, Kf = 1.86 K*kg/mol) — why brine stays liquid well below 0 C. As a
0.6 mol/L NaCl solution at 25 C, the osmotic pressure is about 29.7 bar, so a reverse-osmosis plant
must push above roughly 30 bar just to start moving pure water across the membrane, before any flow.
The example reports the freezing-point depression and the osmotic pressure.

Run it directly (``python examples/road_salt_and_osmosis.py``);
:func:`salt_water_properties` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import freezing_point_depression, osmotic_pressure
from anvilate.units import Quantity

NACL_VANT_HOFF = 2.0
DE_ICING_MOLALITY = Quantity(magnitude=1.0, unit="mol/kg")
WATER_KF = Quantity(magnitude=1.86, unit="K*kg/mol")
SEAWATER_CONCENTRATION = Quantity(magnitude=0.6, unit="mol/L")
TEMPERATURE = Quantity(magnitude=298.15, unit="K")


def salt_water_properties() -> dict[str, float]:
    """Return the NaCl freezing-point depression and the reverse-osmosis osmotic pressure."""
    depression = freezing_point_depression(
        molality=DE_ICING_MOLALITY,
        cryoscopic_constant=WATER_KF,
        vant_hoff_factor=NACL_VANT_HOFF,
    )
    pressure = osmotic_pressure(
        concentration=SEAWATER_CONCENTRATION,
        temperature=TEMPERATURE,
        vant_hoff_factor=NACL_VANT_HOFF,
    )
    return {
        "freezing_point_depression_k": depression.to("K").magnitude,
        "osmotic_pressure_bar": pressure.to("bar").magnitude,
    }


def main() -> None:
    d = salt_water_properties()
    print(f"freezing-point depression (1 molal NaCl): {d['freezing_point_depression_k']:.1f} K")
    print(f"osmotic pressure (0.6 mol/L NaCl): {d['osmotic_pressure_bar']:.0f} bar")


if __name__ == "__main__":
    main()
