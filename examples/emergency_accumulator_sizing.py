"""Worked example: sizing an accumulator for one emergency clamp stroke.

A hydraulic press keeps a safety clamp engaged from a gas-charged accumulator, so that a pump or
power failure still leaves enough stored fluid to hold — or complete — one clamp stroke. The
clamp cylinder needs 3.6 L of oil, and the system works between 100 and 200 bar; the accumulator
is nitrogen-precharged to 90 bar (below the 100 bar minimum, or it empties before the clamp is
done).

This example does the sizing both ways. First it sizes the accumulator for the 3.6 L stroke on a
fast, adiabatic release (n = 1.4, the honest assumption for an emergency dump that happens in a
fraction of a second) and gets a ~10 L bottle. Then it checks how much that same bottle delivers
on a slow, isothermal cycle (n = 1) — 4.5 L, a full 0.9 L more, because gas that has time to shed
heat gives back more of its stored volume. The lesson is that the polytropic exponent is a sizing
input, not a detail: size on the adiabatic case (the one that delivers *less*), and the slow-cycle
margin comes for free.

Run it directly (``python examples/emergency_accumulator_sizing.py``);
:func:`clamp_accumulator` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import accumulator_size_for_volume, accumulator_usable_volume
from anvilate.units import Quantity

STROKE_VOLUME = Quantity.parse("3.6 L")  # oil the clamp cylinder needs
PRECHARGE = Quantity.parse("90 bar")  # nitrogen precharge, below the 100 bar minimum
MIN_PRESSURE = Quantity.parse("100 bar")
MAX_PRESSURE = Quantity.parse("200 bar")


def clamp_accumulator() -> dict[str, float]:
    """Return the adiabatic size for the stroke, and the isothermal delivery of that bottle."""
    size = accumulator_size_for_volume(
        required_volume=STROKE_VOLUME,
        precharge_pressure=PRECHARGE,
        minimum_pressure=MIN_PRESSURE,
        maximum_pressure=MAX_PRESSURE,
        polytropic_exponent=1.4,
    )
    isothermal_delivery = accumulator_usable_volume(
        total_volume=size,
        precharge_pressure=PRECHARGE,
        minimum_pressure=MIN_PRESSURE,
        maximum_pressure=MAX_PRESSURE,
        polytropic_exponent=1.0,
    )
    return {
        "size_l": size.to("L").magnitude,
        "isothermal_l": isothermal_delivery.to("L").magnitude,
    }


def main() -> None:
    r = clamp_accumulator()
    print(f"accumulator size (adiabatic, n=1.4) : {r['size_l']:.2f} L for a 3.6 L stroke")
    print(f"same bottle, slow cycle (n=1.0)     : delivers {r['isothermal_l']:.2f} L")
    print("  -> size on the adiabatic case; the slow-cycle margin comes for free")


if __name__ == "__main__":
    main()
