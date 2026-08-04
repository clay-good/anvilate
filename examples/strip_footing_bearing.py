"""Worked example: what actually carries a strip footing, and how much embedment buys.

A long strip footing on sandy clay (φ = 30°, c = 25 kPa, γ = 18 kN/m³) fails when the soil
beneath it shears, at the Terzaghi ultimate pressure q_ult = c·N_c + q·N_q + ½·γ·B·N_γ. The
three terms are not equal partners: the cohesion term and the surcharge term (the weight of
soil sitting beside the footing at founding depth) each carry far more than the footing's own
self-weight term. That surcharge term is why burying a footing deeper raises its capacity for
free — the example founds the same footing at 0.5 m and at 1.5 m and shows the allowable
bearing pressure (q_ult over a factor of safety of 3) climb with depth, with no change to the
footing itself.

Run it directly (``python examples/strip_footing_bearing.py``);
:func:`footing_capacity` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import bearing_capacity_factors, terzaghi_bearing_capacity
from anvilate.units import Quantity

FRICTION_ANGLE = 30.0  # phi, degrees
COHESION = Quantity.parse("25 kPa")  # c
UNIT_WEIGHT = Quantity.parse("18 kN/m**3")  # gamma
WIDTH = Quantity.parse("2 m")  # B
SAFETY_FACTOR = 3.0
DEPTHS_M = (0.5, 1.5)  # founding depths D_f to compare


def footing_capacity() -> dict[str, float]:
    """Return the ultimate and allowable bearing pressures (kPa) at each founding depth."""
    factors = bearing_capacity_factors(friction_angle=FRICTION_ANGLE)
    gamma = UNIT_WEIGHT.to("kN/m**3").magnitude
    out: dict[str, float] = {}
    for depth in DEPTHS_M:
        surcharge = Quantity(magnitude=gamma * depth, unit="kPa")  # q = gamma * D_f
        q_ult = (
            terzaghi_bearing_capacity(
                cohesion=COHESION,
                surcharge=surcharge,
                unit_weight=UNIT_WEIGHT,
                width=WIDTH,
                bearing_factor_c=factors["N_c"],
                bearing_factor_q=factors["N_q"],
                bearing_factor_gamma=factors["N_gamma"],
            )
            .to("kPa")
            .magnitude
        )
        out[f"q_ult_D{depth}_kpa"] = q_ult
        out[f"q_allow_D{depth}_kpa"] = q_ult / SAFETY_FACTOR
    return out


def main() -> None:
    cap = footing_capacity()
    for depth in DEPTHS_M:
        q_ult = cap[f"q_ult_D{depth}_kpa"]
        q_allow = cap[f"q_allow_D{depth}_kpa"]
        print(f"D_f = {depth} m : q_ult = {q_ult:6.0f} kPa -> q_allow = {q_allow:5.0f} kPa")
    shallow = cap["q_allow_D0.5_kpa"]
    deep = cap["q_allow_D1.5_kpa"]
    print(
        f"burying 1.0 m deeper lifts the allowable bearing by {deep - shallow:.0f} kPa "
        f"({deep / shallow - 1:.0%})"
    )


if __name__ == "__main__":
    main()
