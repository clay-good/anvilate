"""Worked example: the single-stage vapor enrichment of a benzene-toluene mixture.

Benzene and toluene are the textbook easy-to-distill pair. At about 92 °C their pure vapor pressures
are roughly 178 kPa (benzene, the light component) and 74 kPa (toluene), so the relative volatility
is α ≈ 2.4. Starting from a liquid that is 40 mol% benzene, what does one equilibrium stage do?

Raoult's law gives benzene's partial pressure over that liquid as 0.40 × 178 ≈ 71 kPa, and the
equilibrium vapor composition works out to y ≈ 0.62 mol% benzene — the vapor is markedly richer in
the light component than the 40% liquid it boiled from. That one-stage jump, repeated up a column,
is exactly what a distillation tower stacks to reach a pure product; the larger α is, the fewer
stages it takes.

Run it directly (``python examples/distillation_benzene_toluene_equilibrium.py``);
:func:`benzene_toluene_stage` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    equilibrium_vapor_mole_fraction,
    raoult_partial_pressure,
    relative_volatility,
)
from anvilate.units import Quantity

BENZENE_VAPOR_PRESSURE = Quantity.parse("178 kPa")
TOLUENE_VAPOR_PRESSURE = Quantity.parse("74 kPa")
LIQUID_BENZENE_FRACTION = 0.40


def benzene_toluene_stage() -> dict[str, float]:
    """Return the relative volatility, benzene partial pressure (kPa), and equilibrium vapor y."""
    alpha = relative_volatility(
        light_vapor_pressure=BENZENE_VAPOR_PRESSURE,
        heavy_vapor_pressure=TOLUENE_VAPOR_PRESSURE,
    )
    p_benzene = raoult_partial_pressure(
        liquid_mole_fraction=LIQUID_BENZENE_FRACTION,
        pure_vapor_pressure=BENZENE_VAPOR_PRESSURE,
    )
    y = equilibrium_vapor_mole_fraction(
        liquid_mole_fraction=LIQUID_BENZENE_FRACTION, relative_volatility=alpha
    )
    return {
        "relative_volatility": alpha,
        "benzene_partial_pressure_kpa": p_benzene.to("kPa").magnitude,
        "vapor_benzene_fraction": y,
    }


def main() -> None:
    d = benzene_toluene_stage()
    print("Benzene-toluene, 40 mol% benzene liquid at ~92 C:")
    print(f"  relative volatility α : {d['relative_volatility']:.2f}")
    print(f"  benzene partial P     : {d['benzene_partial_pressure_kpa']:.1f} kPa")
    print(f"  vapor benzene fraction: {d['vapor_benzene_fraction']:.3f} (richer than 0.40 liquid)")


if __name__ == "__main__":
    main()
