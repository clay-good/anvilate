"""Worked example: molecular speeds of air, and when a vacuum chamber goes free-molecular.

The kinetic theory sets two very different scales for a gas: how fast its molecules move (hundreds
of metres per second) and how far they travel between collisions (tens of nanometres at pressure).
The second scale is what matters to a vacuum system — once the mean free path grows to the size of
the chamber, molecules fly wall to wall without colliding, and the flow stops behaving like a
continuous fluid. This example finds the molecular speeds of air and the mean free path in a pumped-
down chamber.

For nitrogen at 300 K, the rms molecular speed is about 517 m/s and the mean speed about 476 m/s —
faster than a jet, yet net still air because the motion is random. At atmospheric pressure the mean
free path is only about 67 nm. Pump the chamber down to 0.1 Pa, though, and the mean free path grows
to about 68 mm — comparable to a small chamber, so the gas is free-molecular and continuum
assumptions fail. The example reports the rms and mean speeds and the mean free path at 0.1 Pa.

Run it directly (``python examples/vacuum_mean_free_path.py``);
:func:`vacuum_regime` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import mean_free_path, mean_molecular_speed, rms_molecular_speed
from anvilate.units import Quantity

TEMPERATURE = Quantity(magnitude=300.0, unit="K")
NITROGEN_MOLAR_MASS = Quantity(magnitude=0.028, unit="kg/mol")
MOLECULAR_DIAMETER = Quantity(magnitude=3.7e-10, unit="m")
VACUUM_PRESSURE = Quantity.parse("0.1 Pa")


def vacuum_regime() -> dict[str, float]:
    """Return the rms and mean molecular speeds of air and the mean free path at 0.1 Pa."""
    v_rms = rms_molecular_speed(temperature=TEMPERATURE, molar_mass=NITROGEN_MOLAR_MASS)
    v_mean = mean_molecular_speed(temperature=TEMPERATURE, molar_mass=NITROGEN_MOLAR_MASS)
    mfp = mean_free_path(
        temperature=TEMPERATURE,
        pressure=VACUUM_PRESSURE,
        molecular_diameter=MOLECULAR_DIAMETER,
    )
    return {
        "rms_speed_m_s": v_rms.to("m/s").magnitude,
        "mean_speed_m_s": v_mean.to("m/s").magnitude,
        "mean_free_path_mm_at_0p1pa": mfp.to("mm").magnitude,
    }


def main() -> None:
    d = vacuum_regime()
    print(f"rms molecular speed: {d['rms_speed_m_s']:.0f} m/s")
    print(f"mean molecular speed: {d['mean_speed_m_s']:.0f} m/s")
    print(f"mean free path at 0.1 Pa: {d['mean_free_path_mm_at_0p1pa']:.0f} mm")


if __name__ == "__main__":
    main()
