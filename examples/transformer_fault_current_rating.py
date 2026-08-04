"""Worked example: the fault current a transformer can deliver, and the breaker rating it demands.

Every breaker and panel downstream of a transformer has to be able to interrupt the worst fault the
transformer can feed without exploding — its AIC (ampere interrupting capacity) rating. That worst
case is set by the transformer's own impedance: a stiffer (lower-impedance) transformer holds
voltage better under load but delivers a *harder* fault. This example takes a 1000 kVA, 480 V
transformer and finds its full-load current, then the available bolted fault current at 5.75%
impedance — near 21 kA, so the downstream gear needs at least a 22 kA (commonly 25 kA) rating. It
re-runs the fault at a stiffer 4% impedance to show the same transformer, differently wound, pushing
the fault past 30 kA and forcing a higher-rated (35 kA) bus.

Run it directly (``python examples/transformer_fault_current_rating.py``);
:func:`fault_study` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    transformer_available_fault_current,
    transformer_full_load_current,
)
from anvilate.units import Quantity

RATING = Quantity.parse("1000 kVA")
SECONDARY_VOLTAGE = Quantity.parse("480 V")


def fault_study() -> dict[str, float]:
    """Return the full-load current and the available fault current at two impedances (amperes)."""
    fla = transformer_full_load_current(apparent_power=RATING, line_voltage=SECONDARY_VOLTAGE)
    standard = transformer_available_fault_current(full_load_current=fla, impedance_percent=5.75)
    stiff = transformer_available_fault_current(full_load_current=fla, impedance_percent=4.0)
    return {
        "full_load_a": fla.to("A").magnitude,
        "fault_5p75_a": standard.to("A").magnitude,
        "fault_4p0_a": stiff.to("A").magnitude,
    }


def main() -> None:
    s = fault_study()
    print(f"full-load current      : {s['full_load_a']:.0f} A")
    print(f"available fault @5.75%Z : {s['fault_5p75_a'] / 1000:.1f} kA -> needs >=25 kA gear")
    print(f"available fault @4.0%Z  : {s['fault_4p0_a'] / 1000:.1f} kA -> needs >=35 kA gear")
    print("  -> lower impedance holds voltage better but delivers a harder fault")


if __name__ == "__main__":
    main()
