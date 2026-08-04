"""Worked example: why a diesel beats a gasoline engine — the air-standard cycle efficiencies.

The ideal thermal efficiency of an engine follows from how hard it squeezes the charge. This
example compares three air-standard cycles on air (γ = 1.4). A gasoline (Otto) engine at a
compression ratio of 10 — about as high as knock allows — reaches an ideal 60%. At that same
compression ratio a diesel cycle is actually a touch lower, because burning at constant pressure
over a cutoff ratio costs a little. The reason diesels win in practice is that they compress far
harder: run the diesel at a compression ratio of 18 and its efficiency climbs past the knock-limited
gasoline engine. The example also sizes a gas-turbine (Brayton) cycle at a pressure ratio of 15 for
contrast. These are ceilings — real engines fall well short — but they show which knob each engine
turns for efficiency.

Run it directly (``python examples/engine_cycle_efficiency.py``);
:func:`cycle_efficiencies` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    brayton_cycle_efficiency,
    diesel_cycle_efficiency,
    otto_cycle_efficiency,
)


def cycle_efficiencies() -> dict[str, float]:
    """Return the ideal efficiencies of Otto, diesel (two compressions), and Brayton cycles."""
    return {
        "otto_r10": otto_cycle_efficiency(compression_ratio=10) * 100.0,
        "diesel_r10": diesel_cycle_efficiency(compression_ratio=10, cutoff_ratio=2) * 100.0,
        "diesel_r18": diesel_cycle_efficiency(compression_ratio=18, cutoff_ratio=2) * 100.0,
        "brayton_rp15": brayton_cycle_efficiency(pressure_ratio=15) * 100.0,
    }


def main() -> None:
    c = cycle_efficiencies()
    print(f"gasoline / Otto  (r=10)      : {c['otto_r10']:.0f}%")
    print(f"diesel cycle     (r=10, rc=2): {c['diesel_r10']:.0f}% (lower at equal compression)")
    print(f"diesel cycle     (r=18, rc=2): {c['diesel_r18']:.0f}% (higher compression wins)")
    print(f"gas turbine / Brayton (rp=15): {c['brayton_rp15']:.0f}%")
    print("  -> Otto is knock-limited on r; the diesel's higher compression is why it edges ahead")


if __name__ == "__main__":
    main()
