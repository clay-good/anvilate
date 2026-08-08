"""Worked example: characterizing a laboratory plasma — frequency, screening, and collectivity.

An ionized gas is only a plasma if it behaves collectively, and three numbers establish that: the
plasma frequency (how fast the electrons oscillate, and the radio cutoff below which waves reflect),
the Debye length (how far a charge is screened), and the plasma parameter (how many particles share
a Debye sphere). This example computes them for a typical low-temperature laboratory plasma, like
the kind used to etch semiconductor wafers.

The plasma has an electron density of 1e18 /m^3 at an electron temperature of 1 eV (about 11,600 K).
Its plasma frequency is about 9 GHz, so microwaves below 9 GHz cannot penetrate it. Charges are
screened over a Debye length of about 7.4 micrometres, tiny compared with the chamber. And with
about 1720 electrons inside a Debye sphere — far more than one — the gas is a genuine collective
plasma, not merely ionized. The example reports the plasma frequency, Debye length, and parameter.

Run it directly (``python examples/laboratory_plasma.py``);
:func:`characterize_plasma` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import debye_length, plasma_frequency, plasma_parameter
from anvilate.units import Quantity

ELECTRON_DENSITY = Quantity(magnitude=1e18, unit="1/m**3")
ELECTRON_TEMPERATURE = Quantity(magnitude=11604.5, unit="K")  # 1 eV


def characterize_plasma() -> dict[str, float]:
    """Return the plasma frequency (GHz), the Debye length (um), and the plasma parameter."""
    f_p = plasma_frequency(electron_density=ELECTRON_DENSITY)
    lambda_d = debye_length(
        electron_density=ELECTRON_DENSITY, electron_temperature=ELECTRON_TEMPERATURE
    )
    n_d = plasma_parameter(
        electron_density=ELECTRON_DENSITY, electron_temperature=ELECTRON_TEMPERATURE
    )
    return {
        "plasma_frequency_ghz": f_p.to("GHz").magnitude,
        "debye_length_um": lambda_d.to("um").magnitude,
        "plasma_parameter": n_d,
    }


def main() -> None:
    d = characterize_plasma()
    print(f"plasma frequency: {d['plasma_frequency_ghz']:.1f} GHz")
    print(f"Debye length: {d['debye_length_um']:.1f} um")
    print(f"plasma parameter (particles per Debye sphere): {d['plasma_parameter']:.0f}")


if __name__ == "__main__":
    main()
