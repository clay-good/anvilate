"""Worked example: sizing a lab's supply air to the air-change rate the code demands.

Ventilation minimums for spaces like labs, isolation rooms, and kitchens are almost never a flow
rate — they are written as air changes per hour, a count of how many times the room's whole volume
of air is replaced each hour. Turning that requirement into a fan and duct size is the inverse of
the air-change definition: the required airflow is Q = ACH·V.

This example sizes the supply air for a 60 m² wet lab with a 3 m ceiling, so a 180 m³ room, which
its code requires to run at 8 air changes per hour. The airflow needed is 8 × 180 = 1,440 m³/h,
which is 0.40 m³/s — the number the fan is selected for and the duct sized to carry. Feeding that
flow back through the air-change definition recovers the 8 ACH, confirming the round trip. The
example also shows what a lighter, office-grade 2 ACH would need on the same room — only 0.10 m³/s —
a quarter of the flow, which is the whole reason a lab's ventilation costs so much more to run than
an office of the same size. The lesson is that the air-change rate, not the floor area, is what sets
a space's ventilation load, and Q = ACH·V is the bridge from the code line to the equipment.

Run it directly (``python examples/lab_ventilation_air_changes.py``);
:func:`lab_airflow` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import air_changes_per_hour, airflow_for_air_changes
from anvilate.units import Quantity

ROOM_VOLUME = Quantity.parse("180 m**3")  # 60 m2 x 3 m
LAB_AIR_CHANGES = 8.0
OFFICE_AIR_CHANGES = 2.0


def lab_airflow() -> dict[str, float]:
    """Return the airflow the lab and an office rate need, and the back-checked lab ACH."""
    lab = airflow_for_air_changes(air_changes_per_hour=LAB_AIR_CHANGES, room_volume=ROOM_VOLUME)
    office = airflow_for_air_changes(
        air_changes_per_hour=OFFICE_AIR_CHANGES, room_volume=ROOM_VOLUME
    )
    recovered = air_changes_per_hour(airflow=lab, room_volume=ROOM_VOLUME)
    return {
        "lab_flow_m3s": lab.to("m**3/s").magnitude,
        "office_flow_m3s": office.to("m**3/s").magnitude,
        "recovered_ach": recovered,
    }


def main() -> None:
    f = lab_airflow()
    print(f"lab at 8 ACH    : {f['lab_flow_m3s']:.2f} m3/s ({f['lab_flow_m3s'] * 3600:.0f} m3/h)")
    print(f"office at 2 ACH : {f['office_flow_m3s']:.2f} m3/s (a quarter of the flow)")
    print(f"back-check      : {f['recovered_ach']:.1f} ACH (round-trip)")
    print("  -> the air-change rate, not the floor area, sets the ventilation load")


if __name__ == "__main__":
    main()
