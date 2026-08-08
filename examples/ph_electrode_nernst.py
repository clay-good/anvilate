"""Worked example: a pH electrode read through the Nernst equation.

A potentiometric sensor turns a concentration into a voltage through the Nernst equation, and
reading it means running that relation both ways: what slope the electrode should show per unit of
the measured quantity, and what concentration a measured voltage implies. A pH electrode is the
classic case — one hydrogen ion transferred, so it follows the one-electron Nernst slope.

This example works at 25 C (298.15 K). The one-electron Nernst slope is about 59.2 mV per decade, so
an ideal pH electrode shifts 59.2 mV per pH unit — the calibration slope a meter expects. Given
a standard (zero-offset) electrode reading -0.178 V, the Nernst inverse recovers a reaction quotient
of about 10^3, i.e. pH 3. The example reports the Nernst slope and the pH the measured voltage
implies.

Run it directly (``python examples/ph_electrode_nernst.py``);
:func:`read_ph_electrode` is also exercised in the test suite.
"""

from __future__ import annotations

from math import log10

from anvilate.analysis import nernst_reaction_quotient, nernst_slope
from anvilate.units import Quantity

TEMPERATURE = Quantity(magnitude=298.15, unit="K")
STANDARD_POTENTIAL = Quantity.parse("0 V")
MEASURED_POTENTIAL = Quantity.parse("-0.1775 V")
ELECTRONS = 1


def read_ph_electrode() -> dict[str, float]:
    """Return the Nernst slope (mV/decade) and the pH the measured potential implies."""
    slope = nernst_slope(temperature=TEMPERATURE, electrons_transferred=ELECTRONS)
    quotient = nernst_reaction_quotient(
        standard_potential=STANDARD_POTENTIAL,
        potential=MEASURED_POTENTIAL,
        temperature=TEMPERATURE,
        electrons_transferred=ELECTRONS,
    )
    # For H+ activity a, Q = 1/a here (products/reactants), so pH = -log10(a) = log10(Q).
    ph = log10(quotient)
    return {
        "nernst_slope_mv_per_decade": slope.to("mV").magnitude,
        "implied_ph": ph,
    }


def main() -> None:
    d = read_ph_electrode()
    print(f"Nernst slope: {d['nernst_slope_mv_per_decade']:.1f} mV/decade")
    print(f"pH implied by the reading: {d['implied_ph']:.1f}")


if __name__ == "__main__":
    main()
