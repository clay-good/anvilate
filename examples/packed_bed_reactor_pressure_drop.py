"""Worked example: pressure drop of air through a catalyst packed bed.

A packed-bed reactor holds 2 m of 5 mm catalyst pellets, and air flows up through it at a
superficial velocity of 0.3 m/s (the volumetric flow divided by the empty column area). Before
sizing the blower, the engineer needs the pressure drop the bed imposes — and first the bed's void
fraction, which follows from two density measurements: the pellets pour to a bulk density of about
960 kg/m³ and the solid alumina itself is ~1600 kg/m³.

Those give a void fraction ε = 1 − 960/1600 = 0.40 (a typical loosely packed bed), and the Ergun
equation then returns a pressure drop of roughly 1.1 kPa over the 2 m bed — modest here, but it
climbs steeply if the pellets are made finer or the bed packs denser, which is the trade-off Ergun
makes visible.

Run it directly (``python examples/packed_bed_reactor_pressure_drop.py``);
:func:`packed_bed_drop` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import ergun_pressure_drop, packed_bed_void_fraction
from anvilate.units import Quantity

BED_LENGTH = Quantity.parse("2 m")
PARTICLE_DIAMETER = Quantity.parse("5 mm")
SUPERFICIAL_VELOCITY = Quantity.parse("0.3 m/s")
AIR_DENSITY = Quantity.parse("1.2 kg/m**3")
AIR_VISCOSITY = Quantity.parse("1.8e-5 Pa*s")
BULK_DENSITY = Quantity.parse("960 kg/m**3")
PARTICLE_DENSITY = Quantity.parse("1600 kg/m**3")


def packed_bed_drop() -> dict[str, float]:
    """Return the bed void fraction and the Ergun pressure drop (kPa) for the catalyst bed."""
    eps = packed_bed_void_fraction(bulk_density=BULK_DENSITY, particle_density=PARTICLE_DENSITY)
    dp = ergun_pressure_drop(
        bed_length=BED_LENGTH,
        particle_diameter=PARTICLE_DIAMETER,
        void_fraction=eps,
        superficial_velocity=SUPERFICIAL_VELOCITY,
        fluid_density=AIR_DENSITY,
        fluid_viscosity=AIR_VISCOSITY,
    )
    return {
        "void_fraction": eps,
        "pressure_drop_kpa": dp.to("kPa").magnitude,
    }


def main() -> None:
    d = packed_bed_drop()
    print("Air through a 2 m catalyst bed, 5 mm pellets, U = 0.3 m/s:")
    print(f"  void fraction         : {d['void_fraction']:.3f}")
    print(f"  Ergun pressure drop   : {d['pressure_drop_kpa']:.2f} kPa")


if __name__ == "__main__":
    main()
