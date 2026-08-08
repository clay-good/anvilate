"""Worked example: electron emission from a hot tungsten cathode.

A tungsten filament in a vacuum tube emits electrons two ways, and which one caps the current
depends on the operating point. The Richardson-Dushman law gives the emission-limited saturation
current the hot cathode can supply, the Schottky effect shows how an applied field lowers that
barrier, and the Child-Langmuir law gives the space-charge-limited current the diode gap will
actually pass.

A tungsten cathode (work function 4.5 eV) at 2500 K emits about 6,400 A/m^2 by Richardson-Dushman —
the saturation ceiling. A 10 MV/m surface field lowers the effective work function by about 0.12 eV,
which enhances that emission. In a planar diode with a 1 kV anode and a 1 mm gap, the Child-Langmuir
space-charge limit is about 74,000 A/m^2 — well above the cathode's saturation output, so here the
cathode temperature, not space charge, is the bottleneck. This example reports the Richardson
emission current, the Schottky barrier lowering, and the Child-Langmuir current.

Run it directly (``python examples/tungsten_cathode_emission.py``);
:func:`cathode_emission` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    child_langmuir_current_density,
    schottky_barrier_lowering,
    thermionic_current_density,
)
from anvilate.units import Quantity

TEMPERATURE = Quantity(magnitude=2500.0, unit="K")
WORK_FUNCTION = Quantity(magnitude=4.5, unit="eV")  # tungsten
SURFACE_FIELD = Quantity(magnitude=1e7, unit="V/m")  # 10 MV/m
ANODE_VOLTAGE = Quantity(magnitude=1000.0, unit="V")
GAP = Quantity(magnitude=1e-3, unit="m")


def cathode_emission() -> dict[str, float]:
    """Return the Richardson current, Schottky barrier lowering, and Child-Langmuir current."""
    j_rich = thermionic_current_density(temperature=TEMPERATURE, work_function=WORK_FUNCTION)
    d_w = schottky_barrier_lowering(electric_field=SURFACE_FIELD)
    j_cl = child_langmuir_current_density(anode_voltage=ANODE_VOLTAGE, gap=GAP)
    return {
        "richardson_current_a_m2": j_rich.to("A/m**2").magnitude,
        "schottky_lowering_ev": d_w.to("eV").magnitude,
        "child_langmuir_current_a_m2": j_cl.to("A/m**2").magnitude,
    }


def main() -> None:
    d = cathode_emission()
    print(f"Richardson emission: {d['richardson_current_a_m2']:.0f} A/m^2")
    print(f"Schottky barrier lowering: {d['schottky_lowering_ev']:.3f} eV")
    print(f"Child-Langmuir limit: {d['child_langmuir_current_a_m2']:.0f} A/m^2")


if __name__ == "__main__":
    main()
