"""Worked example: the cut size and grade efficiency of a cyclone dust collector.

A cyclone cleaning a dusty air stream has a 0.15 m inlet, and the gas enters at 15 m/s making about
5 effective turns through the body. The dust is 2000 kg/m³ mineral particles in air
(μ = 1.8e-5 Pa·s, ρ = 1.2 kg/m³). What size does it collect at 50%, and how well does it catch a
10 µm particle?

Lapple's model gives a cut diameter of about 5.1 µm — particles that size are caught half the time.
The grade-efficiency curve then puts a 10 µm particle (twice the cut) at ~80% collection, while a
fine 2 µm particle slips through at only ~13%. That falloff toward the fine end is why a cyclone is
used as a rough pre-cleaner ahead of a bag filter, not as a final filter on its own.

Run it directly (``python examples/cyclone_dust_collector_cut_size.py``);
:func:`cyclone_performance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import cyclone_collection_efficiency, cyclone_cut_diameter
from anvilate.units import Quantity

GAS_VISCOSITY = Quantity.parse("1.8e-5 Pa*s")
INLET_WIDTH = Quantity.parse("0.15 m")
EFFECTIVE_TURNS = 5.0
INLET_VELOCITY = Quantity.parse("15 m/s")
PARTICLE_DENSITY = Quantity.parse("2000 kg/m**3")
GAS_DENSITY = Quantity.parse("1.2 kg/m**3")


def cyclone_performance() -> dict[str, float]:
    """Return the cut diameter (µm) and the collection efficiency of a 10 µm particle."""
    d50 = cyclone_cut_diameter(
        gas_viscosity=GAS_VISCOSITY,
        inlet_width=INLET_WIDTH,
        effective_turns=EFFECTIVE_TURNS,
        inlet_velocity=INLET_VELOCITY,
        particle_density=PARTICLE_DENSITY,
        gas_density=GAS_DENSITY,
    )
    eta_10um = cyclone_collection_efficiency(
        particle_diameter=Quantity.parse("10 um"), cut_diameter=d50
    )
    return {
        "cut_diameter_um": d50.to("um").magnitude,
        "efficiency_10um": eta_10um,
    }


def main() -> None:
    d = cyclone_performance()
    print("Cyclone dust collector, 15 m/s inlet, 5 turns:")
    print(f"  cut diameter d50      : {d['cut_diameter_um']:.2f} um (50% collected)")
    print(f"  efficiency at 10 um   : {d['efficiency_10um'] * 100:.1f} %")


if __name__ == "__main__":
    main()
