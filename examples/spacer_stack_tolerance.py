"""Worked example: worst-case vs statistical tolerance stack on a shaft spacer stack.

A shaft carries five spacers in series, each machined to ±0.05 mm, and the design needs to know how
much the total stack length can drift so the retaining nut still lands in its thread window.

Adding the tolerances worst-case gives ±0.25 mm — the bound that is 100% guaranteed but assumes all
five spacers hit their limit the same way at once. Combining them statistically (root-sum-square)
gives only ±0.112 mm, less than half as much, because independent parts rarely all stray together.
The statistical number is the realistic production spread for a capable shop, so designing to it
(with a process-capability margin) lets the spacers keep their affordable ±0.05 mm instead of being
tightened to hold the worst-case bound.

Run it directly (``python examples/spacer_stack_tolerance.py``);
:func:`spacer_stack_tolerance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import rss_tolerance_stack, worst_case_tolerance_stack
from anvilate.units import Quantity

PART_TOLERANCE = Quantity.parse("0.05 mm")
PART_COUNT = 5


def spacer_stack_tolerance() -> dict[str, float]:
    """Return the worst-case and statistical (RSS) stack tolerances (mm) for the spacer stack."""
    tolerances = [PART_TOLERANCE] * PART_COUNT
    worst_case = worst_case_tolerance_stack(tolerances)
    rss = rss_tolerance_stack(tolerances)
    return {
        "worst_case_mm": worst_case.to("mm").magnitude,
        "rss_mm": rss.to("mm").magnitude,
    }


def main() -> None:
    d = spacer_stack_tolerance()
    print("Five ±0.05 mm spacers stacked on a shaft:")
    print(f"  worst-case stack : ±{d['worst_case_mm']:.3f} mm (100% guaranteed)")
    print(f"  statistical (RSS): ±{d['rss_mm']:.3f} mm (realistic spread)")


if __name__ == "__main__":
    main()
