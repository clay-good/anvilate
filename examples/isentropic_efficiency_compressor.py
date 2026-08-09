"""Worked example: what a real compressor stage actually costs above the reversible ideal.

Textbook compressor sizing quotes the isentropic (reversible) discharge temperature and work, but no
real machine reaches it — bearing drag, tip leakage, and turbulence make the gas come out hotter and
the shaft work higher. This example takes a single air stage at a 7:1 pressure ratio from 300 K,
gets the isentropic discharge temperature from the adiabatic-compression relation, then applies an
82% isentropic efficiency to find the actual discharge temperature and the resulting extra work.

The isentropic outlet is 523 K; the real stage overshoots to 572 K, and because the temperature rise
is what the shaft work pays for, the actual work is 1/0.82 = 1.22x the ideal — a 22% penalty that a
cycle analysis assuming reversible compression would miss entirely. The recovered efficiency closes
the loop: feeding the actual and isentropic temperatures back returns exactly the 0.82 that produced
them.

Run it directly (``python examples/isentropic_efficiency_compressor.py``);
:func:`compressor_stage` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    adiabatic_discharge_temperature,
    compressor_actual_discharge_temperature,
    compressor_isentropic_efficiency,
)
from anvilate.units import Quantity

INLET_TEMPERATURE = Quantity.parse("300 K")
PRESSURE_RATIO = 7.0
HEAT_CAPACITY_RATIO = 1.4
ISENTROPIC_EFFICIENCY = 0.82


def compressor_stage() -> dict[str, float]:
    """Return the isentropic and actual discharge temperatures (K) and the work penalty factor."""
    t2s = adiabatic_discharge_temperature(
        inlet_temperature=INLET_TEMPERATURE,
        pressure_ratio=PRESSURE_RATIO,
        heat_capacity_ratio=HEAT_CAPACITY_RATIO,
    )
    t2a = compressor_actual_discharge_temperature(
        inlet_temperature=INLET_TEMPERATURE,
        isentropic_outlet_temperature=t2s,
        isentropic_efficiency=ISENTROPIC_EFFICIENCY,
    )
    # Recover the efficiency from the temperatures to confirm the round-trip.
    eta_back = compressor_isentropic_efficiency(
        inlet_temperature=INLET_TEMPERATURE,
        isentropic_outlet_temperature=t2s,
        actual_outlet_temperature=t2a,
    )
    t1 = INLET_TEMPERATURE.to("K").magnitude
    t2s_k = t2s.to("K").magnitude
    t2a_k = t2a.to("K").magnitude
    return {
        "isentropic_outlet_k": t2s_k,
        "actual_outlet_k": t2a_k,
        # Work is proportional to the temperature rise, so the penalty is (T2a-T1)/(T2s-T1) = 1/eta.
        "work_penalty_factor": (t2a_k - t1) / (t2s_k - t1),
        "recovered_efficiency": eta_back,
    }


def main() -> None:
    s = compressor_stage()
    print("air compressor stage, 7:1, inlet 300 K, eta_s = 0.82:")
    print(f"  isentropic discharge : {s['isentropic_outlet_k']:.1f} K (reversible ideal)")
    print(f"  actual discharge     : {s['actual_outlet_k']:.1f} K (real machine, hotter)")
    print(f"  -> actual work is {s['work_penalty_factor']:.2f}x the ideal")
    print(f"  recovered efficiency : {s['recovered_efficiency']:.3f} (round-trips to 0.82)")


if __name__ == "__main__":
    main()
