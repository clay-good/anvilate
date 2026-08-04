"""Worked example: two dimensionless numbers that decide how to solve a quench.

Transient conduction — a hot part plunged into a quench — is governed by two numbers, and computing
them first tells you which solution method is even valid. This example quenches a steel slab of
25 mm
half-thickness in oil. The Biot number Bi = h·L/k asks whether the part cools as one uniform lump or
develops an internal gradient: here Bi = 0.25, above the 0.1 lumped-capacitance limit, so the simple
single-temperature model would be wrong and a distributed (Heisler-chart) solution is needed. The
Fourier number Fo = α·t/L² is the dimensionless clock: after a minute it reaches 1.25, well past the
0.2 mark where the one-term Heisler approximation becomes accurate. Together they place the problem
squarely in the one-term-Heisler regime — not lumped, but far enough into the transient to use the
simple chart formula. Getting these two numbers before reaching for an equation is what keeps a
transient analysis from using the wrong tool.

Run it directly (``python examples/quenched_billet_transient.py``);
:func:`quench_regime` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import biot_number, fourier_number
from anvilate.units import Quantity

HALF_THICKNESS = Quantity.parse("0.025 m")
OIL_COEFFICIENT = Quantity.parse("500 W/(m**2*K)")
STEEL_CONDUCTIVITY = Quantity.parse("50 W/(m*K)")
STEEL_DIFFUSIVITY = Quantity.parse("1.3e-5 m**2/s")
QUENCH_TIME = Quantity.parse("60 s")


def quench_regime() -> dict[str, float]:
    """Return the Biot and Fourier numbers of the quench."""
    bi = biot_number(
        heat_transfer_coefficient=OIL_COEFFICIENT,
        characteristic_length=HALF_THICKNESS,
        thermal_conductivity=STEEL_CONDUCTIVITY,
    )
    fo = fourier_number(
        thermal_diffusivity=STEEL_DIFFUSIVITY,
        time=QUENCH_TIME,
        characteristic_length=HALF_THICKNESS,
    )
    return {"biot": bi, "fourier": fo}


def main() -> None:
    q = quench_regime()
    lumped = "lumped OK" if q["biot"] < 0.1 else "NOT lumped — internal gradient"
    developed = "one-term Heisler valid" if q["fourier"] > 0.2 else "early transient"
    print(f"Biot number    : {q['biot']:.2f} ({lumped})")
    print(f"Fourier number : {q['fourier']:.2f} ({developed})")
    print("  -> Bi and Fo pick the method: not lumped, but far enough in for the one-term chart")


if __name__ == "__main__":
    main()
