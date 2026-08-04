"""Worked example: the hydraulic jump that keeps a spillway from scouring the river.

Water leaving the foot of a spillway is fast, shallow, and supercritical — exactly the flow that
would tear the riverbed apart downstream. A stilling basin fixes it by *forcing* a hydraulic jump:
the supercritical sheet slams into deeper tailwater and leaps up in a churning wall of white water,
trading its speed for depth and burning off the excess energy as turbulence. Designing the basin
means knowing two numbers — how deep the flow becomes after the jump (so the basin walls are tall
enough) and how much energy the jump destroys (which is the whole point). This example takes flow
leaving a spillway at 0.3 m depth and Froude 3.5 and computes both: the jump lifts the water to
about 1.3 m and dissipates a 0.7 m head of energy that would otherwise have scoured the channel.

Run it directly (``python examples/spillway_stilling_basin.py``);
:func:`jump_design` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import hydraulic_jump_downstream_depth, hydraulic_jump_energy_loss
from anvilate.units import Quantity

UPSTREAM_DEPTH = Quantity.parse("0.3 m")  # supercritical sheet at the spillway toe
UPSTREAM_FROUDE = 3.5  # Fr1 > 1


def jump_design() -> dict[str, float]:
    """Return the sequent depth (m), the depth ratio, and the energy dissipated (m)."""
    y2 = hydraulic_jump_downstream_depth(
        upstream_depth=UPSTREAM_DEPTH, upstream_froude_number=UPSTREAM_FROUDE
    )
    energy = hydraulic_jump_energy_loss(upstream_depth=UPSTREAM_DEPTH, downstream_depth=y2)
    y1 = UPSTREAM_DEPTH.to("m").magnitude
    return {
        "sequent_depth_m": y2.to("m").magnitude,
        "depth_ratio": y2.to("m").magnitude / y1,
        "energy_loss_m": energy.to("m").magnitude,
    }


def main() -> None:
    d = jump_design()
    print(f"upstream (supercritical) : 0.30 m at Fr = {UPSTREAM_FROUDE}")
    print(
        f"downstream (after jump)  : {d['sequent_depth_m']:.2f} m ({d['depth_ratio']:.1f}x deeper)"
    )
    print(f"energy dissipated        : {d['energy_loss_m']:.2f} m of head burned as turbulence")
    print("  -> the basin walls follow the sequent depth; the jump is the energy sink")


if __name__ == "__main__":
    main()
