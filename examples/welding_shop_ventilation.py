"""Worked example: ventilating a welding bay, where dilution — not comfort — sets the airflow.

A welding shop has to breathe on two counts, and the tighter one wins. ASHRAE 62.1 sets a baseline
outdoor-air rate from the people and the floor; dilution ventilation sets a far larger rate from the
contaminant the process throws off. This example takes a 2000 ft² bay with four welders, computes
the ASHRAE breathing-zone outdoor air, then the airflow needed to dilute welding fume generated
at 90 g/h down below a 5 mg/m³ exposure limit with a mixing factor of 5 for imperfect capture. The
dilution rate dwarfs the comfort rate by two orders of magnitude — around 100 air changes an hour,
so impractical that it is exactly why welding fume is controlled at the source with local exhaust
rather than by diluting the whole room. The example expresses both airflows as air changes in the
bay's volume so they can be compared on one scale.

Run it directly (``python examples/welding_shop_ventilation.py``);
:func:`shop_ventilation` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    air_changes_per_hour,
    breathing_zone_outdoor_airflow,
    dilution_airflow,
)
from anvilate.units import Quantity

BAY_AREA = Quantity.parse("2000 ft**2")
BAY_VOLUME = Quantity.parse("32000 ft**3")  # 2000 ft^2 x 16 ft
WELDERS = 4.0
FUME_RATE = Quantity.parse("90 g/hour")
EXPOSURE_LIMIT = Quantity.parse("5 mg/m**3")
MIXING_FACTOR = 5.0


def shop_ventilation() -> dict[str, float]:
    """Return the comfort and dilution airflows (cfm) and their air-change rates."""
    comfort = breathing_zone_outdoor_airflow(
        people_outdoor_rate=Quantity.parse("10 ft**3/min"),
        occupancy=WELDERS,
        area_outdoor_rate=Quantity.parse("0.18 ft**3/min/ft**2"),
        floor_area=BAY_AREA,
    )
    dilution = dilution_airflow(
        contaminant_generation_rate=FUME_RATE,
        target_concentration=EXPOSURE_LIMIT,
        mixing_factor=MIXING_FACTOR,
    )
    return {
        "comfort_cfm": comfort.to("ft**3/min").magnitude,
        "dilution_cfm": dilution.to("ft**3/min").magnitude,
        "comfort_ach": air_changes_per_hour(airflow=comfort, room_volume=BAY_VOLUME),
        "dilution_ach": air_changes_per_hour(airflow=dilution, room_volume=BAY_VOLUME),
    }


def main() -> None:
    s = shop_ventilation()
    print(f"ASHRAE comfort air : {s['comfort_cfm']:.0f} cfm ({s['comfort_ach']:.1f} ACH)")
    print(f"fume dilution air  : {s['dilution_cfm']:.0f} cfm ({s['dilution_ach']:.1f} ACH)")
    print("  -> ~100 ACH by dilution is impractical; this is why welding uses local exhaust")


if __name__ == "__main__":
    main()
