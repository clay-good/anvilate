"""Worked example: a battery's capacity collapse at a fast discharge rate (Peukert's law).

A lead-acid battery's amp-hour rating is quoted at a slow discharge; drain it fast and it gives much
less. Peukert's law predicts the shortfall from a single exponent, and getting it wrong is why an
off-grid or UPS bank sized on nameplate capacity comes up short under a heavy load. This example
takes a 100 Ah battery rated at its 20-hour rate and asks what a fast load actually gets.

The battery is rated 100 Ah at the 5 A (20-hour) rate, with a Peukert exponent of 1.2 (typical
lead-acid). Drawn at 20 A — four times the rated current — a naive C/I would predict 5 hours, but
Peukert's law gives only about 3.79 hours, and the delivered capacity drops from 100 Ah to about
76 Ah. Feeding those two operating points back in recovers the 1.2 exponent, the way a battery's
Peukert number is measured. The example reports the runtime at 20 A, the delivered capacity, and the
exponent recovered from the two rates.

Run it directly (``python examples/battery_fast_discharge.py``);
:func:`fast_discharge` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    peukert_effective_capacity,
    peukert_exponent_from_two_rates,
    peukert_runtime,
)
from anvilate.units import Quantity

RATED_CAPACITY = Quantity.parse("100 A*hr")
RATED_CURRENT = Quantity.parse("5 A")
DISCHARGE_CURRENT = Quantity.parse("20 A")
PEUKERT_EXPONENT = 1.2


def fast_discharge() -> dict[str, float]:
    """Return the 20 A runtime, the delivered capacity, and the exponent from two rates."""
    runtime = peukert_runtime(
        rated_capacity=RATED_CAPACITY,
        rated_current=RATED_CURRENT,
        discharge_current=DISCHARGE_CURRENT,
        peukert_exponent=PEUKERT_EXPONENT,
    )
    capacity = peukert_effective_capacity(
        rated_capacity=RATED_CAPACITY,
        rated_current=RATED_CURRENT,
        discharge_current=DISCHARGE_CURRENT,
        peukert_exponent=PEUKERT_EXPONENT,
    )
    rated_runtime = Quantity(
        magnitude=RATED_CAPACITY.to("A*hr").magnitude / RATED_CURRENT.to("A").magnitude, unit="hr"
    )
    exponent = peukert_exponent_from_two_rates(
        current_low=RATED_CURRENT,
        runtime_low=rated_runtime,
        current_high=DISCHARGE_CURRENT,
        runtime_high=runtime,
    )
    return {
        "runtime_at_20a_hr": runtime.to("hr").magnitude,
        "delivered_capacity_ah": capacity.to("A*hr").magnitude,
        "recovered_exponent": exponent,
    }


def main() -> None:
    d = fast_discharge()
    print(f"runtime at 20 A: {d['runtime_at_20a_hr']:.2f} hr")
    print(f"delivered capacity: {d['delivered_capacity_ah']:.0f} Ah")
    print(f"Peukert exponent from two rates: {d['recovered_exponent']:.2f}")


if __name__ == "__main__":
    main()
