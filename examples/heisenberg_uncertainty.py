"""Worked example: Heisenberg uncertainty limits on a confined electron.

Quantum mechanics forbids knowing certain pairs of quantities to arbitrary precision at once. Pin an
electron down in space and its momentum must spread; give a state a short life and its energy blurs.
The uncertainty principle sets the best-case (minimum) spreads.

Confining an electron to an atom-sized region of 0.1 nm forces a momentum uncertainty of at least
about 5.3e-25 kg·m/s — a large spread for so light a particle, which is why bound electrons have
substantial kinetic energy. Conversely, a state that lives only 1 ns has an energy uncertainty of at
least about 3.3e-7 eV, the natural linewidth that broadens its spectral line. This example reports
the minimum momentum uncertainty for a 0.1 nm confinement and the minimum energy uncertainty for a
1 ns state lifetime.

Run it directly (``python examples/heisenberg_uncertainty.py``);
:func:`uncertainty_limits` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    minimum_energy_uncertainty,
    minimum_momentum_uncertainty,
)
from anvilate.units import Quantity

CONFINEMENT = Quantity(magnitude=1e-10, unit="m")  # 0.1 nm, atomic scale
STATE_LIFETIME = Quantity(magnitude=1e-9, unit="s")  # 1 ns


def uncertainty_limits() -> dict[str, float]:
    """Return the minimum momentum uncertainty and the minimum energy uncertainty."""
    dp = minimum_momentum_uncertainty(position_uncertainty=CONFINEMENT)
    de = minimum_energy_uncertainty(lifetime=STATE_LIFETIME)
    return {
        "momentum_uncertainty_kg_m_s": dp.to("kg*m/s").magnitude,
        "energy_uncertainty_ev": de.to("eV").magnitude,
    }


def main() -> None:
    d = uncertainty_limits()
    print(f"min momentum uncertainty (0.1 nm): {d['momentum_uncertainty_kg_m_s']:.3e} kg m/s")
    print(f"min energy uncertainty (1 ns): {d['energy_uncertainty_ev']:.3e} eV")


if __name__ == "__main__":
    main()
