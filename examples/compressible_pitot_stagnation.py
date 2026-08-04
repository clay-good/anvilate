"""Worked example: the stagnation ratios on a transonic aircraft, and where Bernoulli breaks.

A Pitot tube reads stagnation (total) pressure — the pressure of the airstream brought to rest — and
turns it into airspeed. At low speed the incompressible Bernoulli form is fine, but as an aircraft
approaches the transonic range the air compresses as it stagnates, and the simple form undercounts.
This example works the three isentropic stagnation ratios at Mach 0.85 for air (γ = 1.4): the
temperature, pressure, and density each rise as the flow stops. It then contrasts the true
compressible pressure ratio with the incompressible approximation 1 + γ/2·M² a low-speed instrument
assumes — the compressible ratio is about 1.60 against the incompressible 1.51, a ~6% gap that would
read as a several-percent airspeed error if left uncorrected. The example also checks the ideal-gas
identity p₀/p = (ρ₀/ρ)·(T₀/T), which the three ratios satisfy exactly.

Run it directly (``python examples/compressible_pitot_stagnation.py``);
:func:`stagnation_ratios` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    stagnation_density_ratio,
    stagnation_pressure_ratio,
    stagnation_temperature_ratio,
)

MACH = 0.85  # transonic
HEAT_CAPACITY_RATIO = 1.4  # air


def stagnation_ratios() -> dict[str, float]:
    """Return the three stagnation ratios and the incompressible pressure approximation."""
    return {
        "temperature_ratio": stagnation_temperature_ratio(
            mach_number=MACH, heat_capacity_ratio=HEAT_CAPACITY_RATIO
        ),
        "pressure_ratio": stagnation_pressure_ratio(
            mach_number=MACH, heat_capacity_ratio=HEAT_CAPACITY_RATIO
        ),
        "density_ratio": stagnation_density_ratio(
            mach_number=MACH, heat_capacity_ratio=HEAT_CAPACITY_RATIO
        ),
        "incompressible_pressure_ratio": 1.0 + HEAT_CAPACITY_RATIO / 2.0 * MACH**2,
    }


def main() -> None:
    r = stagnation_ratios()
    print(f"T0/T (Mach 0.85)          : {r['temperature_ratio']:.4f}")
    print(f"p0/p compressible         : {r['pressure_ratio']:.4f}")
    print(f"rho0/rho                  : {r['density_ratio']:.4f}")
    print(f"p0/p incompressible (1+γM²/2): {r['incompressible_pressure_ratio']:.4f} (undercounts)")
    identity = r["density_ratio"] * r["temperature_ratio"]
    print(f"ideal-gas check p0/p = ρ0/ρ·T0/T : {identity:.4f} (matches the compressible p0/p)")


if __name__ == "__main__":
    main()
