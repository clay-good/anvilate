"""Worked example: the wind load on a sign, and why a gust hurts far more than the average.

A flat sign or billboard is a bluff body — the wind can't slip around it, so it pushes with nearly
its full dynamic pressure. The drag law puts a number on it: F_d = ½·ρ·V²·C_d·A, with a flat-plate
drag coefficient near 1.2. The part that catches designers out is the *square* on velocity: the
load doesn't scale with the wind speed, it scales with its square, so a gust that is only 40%
faster than the mean wind nearly doubles the force on the post and its footing. This example takes
a 3 × 2 m sign in a 30 m/s design wind, finds the drag, and then recomputes it for a 42 m/s gust to
show the jump. The post, the welds, and the foundation all have to carry the gust, not the average
— which is the whole reason wind codes work from a peak gust speed.

Run it directly (``python examples/sign_wind_drag.py``);
:func:`sign_wind_load` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import drag_force
from anvilate.units import Quantity

AIR_DENSITY = Quantity.parse("1.225 kg/m**3")
SIGN_AREA = Quantity.parse("6 m**2")  # 3 m x 2 m
DRAG_COEFFICIENT = 1.2  # flat plate / bluff body
MEAN_WIND = Quantity.parse("30 m/s")
GUST_WIND = Quantity.parse("42 m/s")  # 40% faster gust


def sign_wind_load() -> dict[str, float]:
    """Return the drag force (kN) at the mean wind and at the gust, and their ratio."""
    mean = (
        drag_force(
            density=AIR_DENSITY,
            velocity=MEAN_WIND,
            drag_coefficient=DRAG_COEFFICIENT,
            reference_area=SIGN_AREA,
        )
        .to("kN")
        .magnitude
    )
    gust = (
        drag_force(
            density=AIR_DENSITY,
            velocity=GUST_WIND,
            drag_coefficient=DRAG_COEFFICIENT,
            reference_area=SIGN_AREA,
        )
        .to("kN")
        .magnitude
    )
    return {
        "mean_load_kn": mean,
        "gust_load_kn": gust,
        "gust_over_mean": gust / mean,
    }


def main() -> None:
    w = sign_wind_load()
    print(f"mean wind (30 m/s) : {w['mean_load_kn']:.1f} kN on the sign")
    print(f"gust (42 m/s)      : {w['gust_load_kn']:.1f} kN")
    faster = 42 / 30 - 1
    print(
        f"  -> a {faster:.0%} faster gust is {w['gust_over_mean'] - 1:.0%} more load (the V^2 law)"
    )


if __name__ == "__main__":
    main()
