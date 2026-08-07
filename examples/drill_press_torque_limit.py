"""Worked example: why a big drill stalls a press a small one spins through — torque grows with d².

A drill press is sized on torque, not surface speed. The twist the spindle must supply to a twist
drill rises with the square of the diameter: double the drill and the torque quadruples at the same
feed. That is why a bench press that whips a 5 mm drill through steel bogs down and stalls on a
20 mm drill in the same bar — the cut needs sixteen times the torque, and the motor cannot deliver
it. The practical lever the operator has is the feed per revolution: torque is linear in feed, so a
drill too big for the machine can still be run by feeding it more gently.

This example drills steel of 2000 MPa specific cutting energy with a 12 mm drill at 0.2 mm/rev and
600 rpm. The removal rate is about 13.6 cm³/min, and the torque works out to around 7.2 N·m. Suppose
the press is rated to 10 N·m at the spindle: the example inverts the torque relation to find the
largest feed that rating allows — about 0.28 mm/rev — so the chosen 0.2 mm/rev sits safely inside
the machine's limit. Push the feed past f_max and the required torque exceeds what the press can
hold and the drill stalls in the hole. The example reports the removal rate, the torque, and that
feed ceiling so the margin against stalling is explicit.

Run it directly (``python examples/drill_press_torque_limit.py``);
:func:`drill_duty` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    drilling_feed_for_torque_limit,
    drilling_material_removal_rate,
    drilling_torque,
)
from anvilate.units import Quantity

DRILL_DIAMETER = Quantity.parse("12 mm")
FEED_PER_REVOLUTION = Quantity.parse("0.2 mm")
SPINDLE_SPEED = Quantity.parse("600 revolution/minute")
SPECIFIC_CUTTING_ENERGY = Quantity.parse("2000 MPa")  # steel, ~2 J/mm^3
SPINDLE_TORQUE_LIMIT = Quantity.parse("10 N*m")


def drill_duty() -> dict[str, float]:
    """Return the removal rate, torque, and torque-limited feed ceiling of a drilling cut."""
    mrr = drilling_material_removal_rate(
        drill_diameter=DRILL_DIAMETER,
        feed_per_revolution=FEED_PER_REVOLUTION,
        spindle_speed=SPINDLE_SPEED,
    )
    torque = drilling_torque(
        specific_cutting_energy=SPECIFIC_CUTTING_ENERGY,
        feed_per_revolution=FEED_PER_REVOLUTION,
        drill_diameter=DRILL_DIAMETER,
    )
    f_max = drilling_feed_for_torque_limit(
        torque_limit=SPINDLE_TORQUE_LIMIT,
        specific_cutting_energy=SPECIFIC_CUTTING_ENERGY,
        drill_diameter=DRILL_DIAMETER,
    )
    return {
        "removal_rate_cm3_min": mrr.to("cm**3/min").magnitude,
        "torque_nm": torque.to("N*m").magnitude,
        "feed_ceiling_mm": f_max.to("mm").magnitude,
        "feed_used_mm": FEED_PER_REVOLUTION.to("mm").magnitude,
    }


def main() -> None:
    d = drill_duty()
    print(f"removal rate: {d['removal_rate_cm3_min']:.1f} cm^3/min")
    print(f"spindle torque: {d['torque_nm']:.1f} N*m (press rated 10 N*m)")
    print(
        f"feed ceiling at that rating: {d['feed_ceiling_mm']:.2f} mm/rev "
        f"(using {d['feed_used_mm']:.2f} mm/rev -> inside the limit)"
    )


if __name__ == "__main__":
    main()
