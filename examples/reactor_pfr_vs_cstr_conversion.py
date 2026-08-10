"""Worked example: why a plug-flow reactor beats a stirred tank at the same Damköhler number.

A first-order reaction runs at rate constant k = 0.5 /s, and the fluid spends a mean residence time
τ = 4 s in the reactor. That fixes the Damköhler number Da = k·τ = 2 — the one dimensionless group
that decides how much reactant is consumed. This example asks the sizing question every reactor
engineer faces: for that same Da, how much conversion does a plug-flow reactor (PFR) reach versus a
continuous stirred-tank reactor (CSTR)?

The PFR, where fluid moves as unmixed plugs each reacting as it travels, converts X = 1 − exp(−Da) ≈
86.5%. The CSTR, perfectly mixed so the whole vessel sits at the low outlet concentration, manages
only X = Da/(1 + Da) ≈ 66.7%. The PFR wins for any positive-order reaction — which is why reaching a
target conversion takes a larger CSTR than PFR, the classic reactor-sizing trade-off.

Run it directly (``python examples/reactor_pfr_vs_cstr_conversion.py``);
:func:`reactor_conversion` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    cstr_conversion_first_order,
    damkohler_number_first_order,
    pfr_conversion_first_order,
)
from anvilate.units import Quantity

RATE_CONSTANT = Quantity.parse("0.5 1/s")
RESIDENCE_TIME = Quantity.parse("4 s")


def reactor_conversion() -> dict[str, float]:
    """Return the Damköhler number and the PFR and CSTR conversions for a first-order reaction."""
    da = damkohler_number_first_order(rate_constant=RATE_CONSTANT, residence_time=RESIDENCE_TIME)
    return {
        "damkohler_number": da,
        "pfr_conversion": pfr_conversion_first_order(damkohler_number=da),
        "cstr_conversion": cstr_conversion_first_order(damkohler_number=da),
    }


def main() -> None:
    d = reactor_conversion()
    print("First-order reaction, k = 0.5 /s, tau = 4 s:")
    print(f"  Damkohler number Da   : {d['damkohler_number']:.2f}")
    print(f"  PFR conversion        : {d['pfr_conversion'] * 100:.1f} %")
    print(f"  CSTR conversion       : {d['cstr_conversion'] * 100:.1f} % (a stirred tank lags)")


if __name__ == "__main__":
    main()
