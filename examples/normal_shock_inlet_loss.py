"""Worked example: what a supersonic inlet pays for a normal shock — static up, total pressure lost.

When a supersonic stream is forced to go subsonic — at the lip of a jet engine inlet, ahead of a
blunt body, or in an over-expanded nozzle — it does so through a normal shock: a paper-thin front
across which the flow jumps discontinuously. Two things happen at once. The static pressure leaps,
which is useful (an inlet wants to recover pressure), but the stagnation pressure drops, which is
pure loss — the shock is irreversible, and that lost total pressure is thrust and efficiency gone.
The stronger the shock, the more static pressure it recovers but the more total pressure it wastes,
which is exactly why supersonic inlets decelerate the flow through several weak oblique shocks
rather than one strong normal shock.

This example takes air (γ = 1.4) arriving at Mach 2 and passes it through a normal shock. Behind the
shock the flow is subsonic at about Mach 0.58 — every normal shock leaves subsonic flow. The static
pressure jumps by a factor of 4.5, a large and useful rise. But the stagnation pressure recovers
only about 72% across the shock; nearly a third of the total pressure is destroyed in one front.
The example reports the downstream Mach, the static pressure ratio, and the stagnation-pressure
recovery, so the bargain a normal shock strikes — static pressure gained at total pressure lost — is
explicit.

Run it directly (``python examples/normal_shock_inlet_loss.py``);
:func:`normal_shock` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    normal_shock_downstream_mach,
    normal_shock_pressure_ratio,
    normal_shock_stagnation_pressure_ratio,
)

UPSTREAM_MACH = 2.0
HEAT_CAPACITY_RATIO = 1.4  # air


def normal_shock() -> dict[str, float]:
    """Return the downstream Mach, the static pressure jump, and the stagnation recovery."""
    return {
        "downstream_mach": normal_shock_downstream_mach(
            upstream_mach=UPSTREAM_MACH, heat_capacity_ratio=HEAT_CAPACITY_RATIO
        ),
        "static_pressure_ratio": normal_shock_pressure_ratio(
            upstream_mach=UPSTREAM_MACH, heat_capacity_ratio=HEAT_CAPACITY_RATIO
        ),
        "stagnation_pressure_recovery": normal_shock_stagnation_pressure_ratio(
            upstream_mach=UPSTREAM_MACH, heat_capacity_ratio=HEAT_CAPACITY_RATIO
        ),
    }


def main() -> None:
    d = normal_shock()
    print(f"upstream Mach 2.0 -> downstream Mach {d['downstream_mach']:.2f} (subsonic)")
    print(f"static pressure ratio p2/p1: {d['static_pressure_ratio']:.1f}x")
    print(
        f"stagnation-pressure recovery: {d['stagnation_pressure_recovery']:.0%} "
        f"-> ~28% of total pressure destroyed"
    )


if __name__ == "__main__":
    main()
