"""Worked example: why shot peening is timed to 98%, not 100% — coverage nears but never arrives.

Shot peening lays a compressive skin on a fatigue-critical part by pelting it with hard shot, each
impact a dimple. The strengthening only counts where the surface has been struck, so peening is
specified by coverage — the dimpled fraction. The catch is statistics: shot lands at random, and as
the surface fills, more and more impacts fall on metal already dimpled. Coverage therefore rises
fast and then crawls, following C = 1 − exp(−λ·t), an exponential that closes on 100% but never
reaches it. No finite exposure gives total coverage, so the industry draws the line at 98% and calls
that "full." Heavier peening is then quoted as a multiple: 200% coverage means twice the 98% time.

This example peens with a shot stream that dimples 0.3 mm craters at a flux of 500 impacts per mm²
per second, a coverage rate of about 35 per second. Full coverage (98%) needs an exposure of about
0.11 s per spot. Running the same spot for twice that — 200% coverage — pushes the dimpled fraction
to about 99.96%, showing how little the extra time adds and why coverage is a poor stopping signal
past saturation. The example reports the coverage rate, the 98% exposure, and the coverage reached
at 200% exposure, so the diminishing return that motivates the 98% convention is explicit.

Run it directly (``python examples/shot_peening_coverage_time.py``);
:func:`peening_schedule` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    peening_coverage,
    peening_impact_coverage_rate,
    peening_time_for_coverage,
)
from anvilate.units import Quantity

DIMPLE_DIAMETER = Quantity.parse("0.3 mm")
IMPACT_FLUX = Quantity.parse("500 1/(mm**2*s)")
FULL_COVERAGE = 0.98


def peening_schedule() -> dict[str, float]:
    """Return the coverage rate, the 98% exposure, and the coverage reached at 200% exposure."""
    rate = peening_impact_coverage_rate(dimple_diameter=DIMPLE_DIAMETER, impact_flux=IMPACT_FLUX)
    t_full = peening_time_for_coverage(coverage_rate=rate, target_coverage=FULL_COVERAGE)
    t_double = Quantity(magnitude=2.0 * t_full.to("s").magnitude, unit="s")
    coverage_at_200 = peening_coverage(coverage_rate=rate, exposure_time=t_double)
    return {
        "coverage_rate_per_s": rate.to("1/s").magnitude,
        "full_coverage_time_s": t_full.to("s").magnitude,
        "coverage_at_200_percent": coverage_at_200,
    }


def main() -> None:
    d = peening_schedule()
    print(f"coverage rate: {d['coverage_rate_per_s']:.1f} per second")
    print(f"98% (full) coverage exposure: {d['full_coverage_time_s']:.3f} s per spot")
    print(
        f"coverage at 200% exposure: {d['coverage_at_200_percent']:.4%} "
        f"-> doubling the time barely moves it"
    )


if __name__ == "__main__":
    main()
