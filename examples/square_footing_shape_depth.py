"""Worked example: the bearing capacity a strip formula throws away on a real footing.

Terzaghi's bearing-capacity equation is derived for an infinitely long strip footing at the
ground surface, but real footings are square or rectangular and buried below grade — and both of
those make them stronger. A square shape stiffens the failure surface (the cohesion and surcharge
terms gain, the self-weight term gives a little back), and embedment mobilizes the shear strength
of the soil beside the footing that the surface formula ignores. This example takes a 2 m square
footing founded 1.5 m down in a c-φ soil, runs the plain strip capacity, then applies the Vesić
shape and depth factors to each term and shows the corrected capacity is about 45% higher. Using
the strip value alone would oversize the footing — capacity the more complete formula recovers.

Run it directly (``python examples/square_footing_shape_depth.py``);
:func:`corrected_bearing` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    bearing_capacity_factors,
    bearing_depth_factors,
    bearing_shape_factors,
    terzaghi_bearing_capacity,
)
from anvilate.units import Quantity

FRICTION_ANGLE = 30.0
COHESION = Quantity.parse("25 kPa")
SURCHARGE = Quantity.parse("18 kPa")  # gamma * D_f = 12 * 1.5, say
UNIT_WEIGHT = Quantity.parse("18 kN/m**3")
WIDTH = Quantity.parse("2 m")  # square footing side (B = L)
LENGTH = Quantity.parse("2 m")
EMBEDMENT = Quantity.parse("1.5 m")


def corrected_bearing() -> dict[str, float]:
    """Return the strip and shape/depth-corrected ultimate bearing pressures (kPa)."""
    n = bearing_capacity_factors(friction_angle=FRICTION_ANGLE)
    common = {
        "cohesion": COHESION,
        "surcharge": SURCHARGE,
        "unit_weight": UNIT_WEIGHT,
        "width": WIDTH,
    }
    strip = (
        terzaghi_bearing_capacity(
            bearing_factor_c=n["N_c"],
            bearing_factor_q=n["N_q"],
            bearing_factor_gamma=n["N_gamma"],
            **common,
        )
        .to("kPa")
        .magnitude
    )
    s = bearing_shape_factors(
        footing_width=WIDTH,
        footing_length=LENGTH,
        friction_angle=FRICTION_ANGLE,
        bearing_factor_nq=n["N_q"],
        bearing_factor_nc=n["N_c"],
    )
    d = bearing_depth_factors(
        footing_width=WIDTH, embedment_depth=EMBEDMENT, friction_angle=FRICTION_ANGLE
    )
    corrected = (
        terzaghi_bearing_capacity(
            bearing_factor_c=n["N_c"] * s["s_c"] * d["d_c"],
            bearing_factor_q=n["N_q"] * s["s_q"] * d["d_q"],
            bearing_factor_gamma=n["N_gamma"] * s["s_gamma"] * d["d_gamma"],
            **common,
        )
        .to("kPa")
        .magnitude
    )
    return {
        "strip_kpa": strip,
        "corrected_kpa": corrected,
        "ratio": corrected / strip,
    }


def main() -> None:
    r = corrected_bearing()
    print(f"strip Terzaghi q_ult      : {r['strip_kpa']:.0f} kPa (surface, infinite strip)")
    print(f"shape + depth corrected   : {r['corrected_kpa']:.0f} kPa (2 m square, 1.5 m deep)")
    gain = (r["ratio"] - 1) * 100
    print(f"  -> {gain:.0f}% more capacity the strip formula leaves on the table")


if __name__ == "__main__":
    main()
