"""Worked example: elastic wave speeds in steel for ultrasonic testing and seismology.

A solid carries mechanical waves at speeds fixed by its stiffness and density, and the three modes
travel at different speeds. An ultrasonic flaw detector uses the bar or longitudinal speed to turn
an echo time into a depth; a seismograph uses the gap between the fast P-wave and the slower S-wave
to tell how far away an earthquake was. This example computes all three for structural steel.

Steel (Young's modulus 200 GPa, shear modulus 80 GPa, bulk modulus 160 GPa, density 7850 kg/m^3)
carries a thin-bar longitudinal wave at about 5050 m/s — the number an ultrasonic thickness gauge is
calibrated to. Its shear wave is slower, about 3190 m/s, because shear stiffness is below tensile
stiffness. In the bulk, the surrounding material stiffens the longitudinal P-wave to about 5830 m/s,
the fastest mode and the first arrival on a seismograph. The example reports the bar, shear, and
bulk P-wave speeds.

Run it directly (``python examples/steel_ultrasonic_wave_speeds.py``);
:func:`steel_wave_speeds` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    bar_wave_speed,
    bulk_longitudinal_wave_speed,
    shear_wave_speed,
)
from anvilate.units import Quantity

YOUNGS_MODULUS = Quantity.parse("200 GPa")
SHEAR_MODULUS = Quantity.parse("80 GPa")
BULK_MODULUS = Quantity.parse("160 GPa")
DENSITY = Quantity(magnitude=7850.0, unit="kg/m**3")


def steel_wave_speeds() -> dict[str, float]:
    """Return the bar longitudinal, shear, and bulk P-wave speeds of steel (m/s)."""
    bar = bar_wave_speed(elastic_modulus=YOUNGS_MODULUS, density=DENSITY)
    shear = shear_wave_speed(shear_modulus=SHEAR_MODULUS, density=DENSITY)
    p_wave = bulk_longitudinal_wave_speed(
        bulk_modulus=BULK_MODULUS, shear_modulus=SHEAR_MODULUS, density=DENSITY
    )
    return {
        "bar_wave_speed_m_s": bar.to("m/s").magnitude,
        "shear_wave_speed_m_s": shear.to("m/s").magnitude,
        "p_wave_speed_m_s": p_wave.to("m/s").magnitude,
    }


def main() -> None:
    d = steel_wave_speeds()
    print(f"thin-bar longitudinal speed: {d['bar_wave_speed_m_s']:.0f} m/s")
    print(f"shear (S-wave) speed: {d['shear_wave_speed_m_s']:.0f} m/s")
    print(f"bulk P-wave speed: {d['p_wave_speed_m_s']:.0f} m/s")


if __name__ == "__main__":
    main()
