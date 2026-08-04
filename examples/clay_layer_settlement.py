"""Worked example: a foundation the soil is strong enough for but settles too much, slowly.

Bearing capacity is only half of foundation design. A footing can sit on soil that never
shears yet still be unserviceable if the clay beneath it consolidates too far — and it does
so over years, not on the day of construction. This example loads a 3 m normally
consolidated clay layer with a 60 kPa stress increase and finds the Terzaghi 1D primary
settlement (≈ 100 mm, well past a typical 25 mm serviceability limit), then uses the time
factor to show that reaching 90% of it takes years, so most of the movement outlives the
contractor. It's the serviceability companion to ``strip_footing_bearing.py``: the same
foundation can pass on strength and fail on settlement.

Run it directly (``python examples/clay_layer_settlement.py``);
:func:`settlement_summary` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    consolidation_settlement,
    consolidation_time,
    consolidation_time_factor,
)
from anvilate.units import Quantity

COMPRESSION_INDEX = 0.30  # C_c, virgin curve slope
INITIAL_VOID_RATIO = 0.90  # e_0
LAYER_THICKNESS = Quantity.parse("3 m")  # H
INITIAL_STRESS = Quantity.parse("100 kPa")  # sigma_0', mid-layer overburden
STRESS_INCREMENT = Quantity.parse("60 kPa")  # delta-sigma from the footing

DRAINAGE_PATH = Quantity.parse("3 m")  # H_dr: 3 m layer draining through its top face only
COEFF_CONSOLIDATION = Quantity.parse("1 m**2/year")  # c_v
TARGET_CONSOLIDATION = 90.0  # percent
SERVICEABILITY_LIMIT_MM = 25.0


def settlement_summary() -> dict[str, float]:
    """Return the ultimate settlement (mm) and the years to reach the target consolidation."""
    settlement = (
        consolidation_settlement(
            compression_index=COMPRESSION_INDEX,
            initial_void_ratio=INITIAL_VOID_RATIO,
            layer_thickness=LAYER_THICKNESS,
            initial_effective_stress=INITIAL_STRESS,
            stress_increment=STRESS_INCREMENT,
        )
        .to("mm")
        .magnitude
    )
    t_v = consolidation_time_factor(degree_of_consolidation=TARGET_CONSOLIDATION)
    years = (
        consolidation_time(
            time_factor=t_v,
            drainage_path_length=DRAINAGE_PATH,
            coefficient_of_consolidation=COEFF_CONSOLIDATION,
        )
        .to("year")
        .magnitude
    )
    return {
        "ultimate_settlement_mm": settlement,
        "time_factor": t_v,
        "years_to_target": years,
    }


def main() -> None:
    s = settlement_summary()
    total = s["ultimate_settlement_mm"]
    verdict = "FAIL" if total > SERVICEABILITY_LIMIT_MM else "PASS"
    limit = SERVICEABILITY_LIMIT_MM
    print(f"ultimate primary settlement : {total:.0f} mm  ({verdict} vs {limit:.0f} mm limit)")
    at_target = total * TARGET_CONSOLIDATION / 100.0
    print(
        f"{TARGET_CONSOLIDATION:.0f}% of it ({at_target:.0f} mm) takes "
        f"{s['years_to_target']:.1f} years (T_v = {s['time_factor']:.3f})"
    )


if __name__ == "__main__":
    main()
