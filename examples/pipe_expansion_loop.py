"""Worked example: a piping expansion bend where the fitting SIF, not the pipe, governs.

When a hot pipe run is restrained at its anchors, thermal growth is forced into bending
that cycles every startup and shutdown — a fatigue problem ASME B31.3 screens with the
displacement stress range S_E against an allowable S_A. The catch is that a bend is not
straight pipe: as the line expands the elbow ovalizes and concentrates the stress, which
B31.3 captures with a stress-intensification factor (SIF).

This example runs the flexibility-analysis moment ranges (8 / 5 / 3 kN*m in-plane /
out-of-plane / torsional) through a DN100-class elbow (6 mm wall, 150 mm bend radius):

  * Treated as straight pipe (SIF = 1), S_E is 99 MPa — a comfortable 0.48 of the
    205 MPa allowable.
  * With the elbow's actual SIFs (i_i = 1.87, i_o = 1.56), S_E is 172 MPa — 0.84 of
    the allowable.

So the elbow works 73% harder than a straight-pipe stress calc predicts. Both still
pass here, but a check that ignores the SIF reports a margin that is not really there.

The example composes the three B31.3 flexibility closed-forms — the elbow SIFs, the
displacement stress range, and the allowable range.

Run it directly (``python examples/pipe_expansion_loop.py``);
:func:`loop_utilizations` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    asme_b313_allowable_displacement_stress_range,
    asme_b313_bend_stress_intensification,
    asme_b313_displacement_stress,
)
from anvilate.units import Quantity

WALL = Quantity.parse("6 mm")
BEND_RADIUS = Quantity.parse("150 mm")
MEAN_RADIUS = Quantity.parse("52 mm")
SECTION_MODULUS = Quantity.parse("100000 mm**3")

IN_PLANE_MOMENT = Quantity.parse("8 kN*m")
OUT_OF_PLANE_MOMENT = Quantity.parse("5 kN*m")
TORSIONAL_MOMENT = Quantity.parse("3 kN*m")

COLD_ALLOWABLE = Quantity.parse("138 MPa")  # S_c
HOT_ALLOWABLE = Quantity.parse("130 MPa")  # S_h


def loop_utilizations() -> dict[str, float]:
    """Return the S_E / S_A utilization for the elbow, with and without its SIF."""
    i_in, i_out = asme_b313_bend_stress_intensification(
        wall_thickness=WALL, bend_radius=BEND_RADIUS, mean_radius=MEAN_RADIUS
    )
    moments = {
        "in_plane_moment": IN_PLANE_MOMENT,
        "out_of_plane_moment": OUT_OF_PLANE_MOMENT,
        "torsional_moment": TORSIONAL_MOMENT,
        "section_modulus": SECTION_MODULUS,
    }
    intensified = asme_b313_displacement_stress(
        in_plane_sif=i_in, out_of_plane_sif=i_out, **moments
    )
    straight = asme_b313_displacement_stress(**moments)
    allowable = asme_b313_allowable_displacement_stress_range(
        cold_allowable=COLD_ALLOWABLE, hot_allowable=HOT_ALLOWABLE
    )
    s_a = allowable.to("MPa").magnitude
    return {
        "straight_pipe": straight.to("MPa").magnitude / s_a,
        "at_the_elbow": intensified.to("MPa").magnitude / s_a,
    }


def main() -> None:
    utils = loop_utilizations()
    for label, util in utils.items():
        print(f"{label:14s}: S_E/S_A = {util:.2f}")
    ratio = utils["at_the_elbow"] / utils["straight_pipe"]
    print(f"the elbow works {100 * (ratio - 1):.0f}% harder than the straight-pipe calc")


if __name__ == "__main__":
    main()
