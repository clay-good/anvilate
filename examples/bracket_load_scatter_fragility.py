"""Worked example: a bracket that passes on paper but is fragile under scatter.

A nominal safety factor is computed from single best-guess inputs. But a tie-rod
bracket carries a service load an engineer often knows only to a wide band — a
crane hook, a process surge, a wind gust. If that load is uncertain to ±15%, a
comfortable-looking margin can hide a real chance of falling short of the required
factor. That gap is exactly the silent green this library exists to catch.

The bracket is an A36 tension member, 200 mm² net area, holding a 29.4 kN service
load. Its capacity is the yield strength times the area, so the nominal safety
factor is (250 MPa · 200 mm²) / 29.4 kN = 1.70 — clear of the 1.5 the job
requires. On paper it passes.

Now let the load scatter (15% CoV, the dominant unknown) and the material vary a
little (5% CoV on yield), and sample the safety factor ten thousand ways. The mean
is still about 1.7, but the safety factor drops below the required 1.5 in roughly
one run in five — a shortfall probability no single-point check reports. The
sensitivity ranking says what to pin down first: the load, by a wide margin, drives
the scatter; tightening the material spec would barely move it.

The lesson is that a margin is a distribution, not a number. When the governing
input is uncertain, the honest result is a probability of shortfall and a pointer
to the input that matters — a load factor to negotiate, or a test to run — not a
lone green check.

This is screening, not certified reliability: the probability is only as trustworthy
as the ±bands the engineer asserts. Run it directly
(``python examples/bracket_load_scatter_fragility.py``); :func:`screen_bracket` is
exercised in the test suite.
"""

from __future__ import annotations

from anvilate.uncertainty import MarginUncertainty, Normal, sample_margin

REQUIRED_SF = 1.5  # the safety factor the job requires

# The bracket, as single best-guess numbers.
YIELD_MPA = 250.0  # A36 yield strength
AREA_MM2 = 200.0  # net tension area
LOAD_KN_NOMINAL = 29.4  # service load — the uncertain one


def _safety_factor(values) -> float:
    """SF = capacity / load = (yield · area) / load, in consistent kN."""
    capacity_kn = values["yield_strength"] * values["area"] / 1000.0  # MPa·mm² -> N -> kN
    return capacity_kn / values["load"]


def nominal_safety_factor() -> float:
    """The single-point safety factor from the best-guess inputs."""
    return _safety_factor({"yield_strength": YIELD_MPA, "area": AREA_MM2, "load": LOAD_KN_NOMINAL})


def screen_bracket(*, seed: int = 20260803, samples: int = 20000) -> MarginUncertainty:
    """Propagate the input scatter into a distribution of the safety factor."""
    inputs = {
        # The load is the dominant unknown: 15% coefficient of variation.
        "load": Normal(mean=LOAD_KN_NOMINAL, std=0.15 * LOAD_KN_NOMINAL),
        # The material varies a little around its spec: 5% CoV on yield.
        "yield_strength": Normal(mean=YIELD_MPA, std=0.05 * YIELD_MPA),
        # The section is cut to a tight tolerance: treat the area as fixed.
        "area": Normal(mean=AREA_MM2, std=0.0),
    }
    return sample_margin(_safety_factor, inputs, required=REQUIRED_SF, seed=seed, samples=samples)


def main() -> None:
    print(f"Nominal safety factor: {nominal_safety_factor():.2f} (required {REQUIRED_SF})")
    result = screen_bracket()
    print(result)
    band = f"{result.lower:.2f}..{result.upper:.2f}"
    print(f"  central {result.coverage:.0%} band: {band}")
    print(f"  fragile at 5%? {result.is_fragile(threshold=0.05)}")
    print("  what drives the scatter:")
    for s in result.sensitivities:
        print(f"    {s.name}: {s.variance_share:.0%} of the variance")


if __name__ == "__main__":
    main()
