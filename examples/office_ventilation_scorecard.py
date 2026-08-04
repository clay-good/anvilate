"""Worked example: an office zone's outdoor air, screened against ASHRAE 62.1 and air changes.

The ventilation pack reports the two things an occupied zone must satisfy at once, and a big room
can pass one while failing the other. This example takes a 5000 ft² office holding 50 people, sets
the ASHRAE 62.1 demand (5 cfm/person and 0.06 cfm/ft², delivered at 0.8 zone air distribution
effectiveness), and screens the outdoor airflow the system delivers. At 800 cfm the zone clears both
the ~688 cfm outdoor-air requirement and a 0.5 ACH minimum. The example then re-screens the same
800 cfm against a laboratory-grade 6 ACH minimum, where the outdoor-air rate is still fine but the
air-change rate falls far short — the case where a high-turnover space must be sized on air changes,
not the ventilation-rate procedure.

Run it directly (``python examples/office_ventilation_scorecard.py``);
:func:`zone_scorecards` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.ventilation import VentilationZone, screen_ventilation
from anvilate.units import Quantity

_ZONE = {
    "people_outdoor_rate": Quantity.parse("5 ft**3/min"),
    "occupancy": 50.0,
    "area_outdoor_rate": Quantity.parse("0.06 ft**3/min/ft**2"),
    "floor_area": Quantity.parse("5000 ft**2"),
    "zone_air_distribution_effectiveness": 0.8,
    "provided_outdoor_airflow": Quantity.parse("800 ft**3/min"),
    "room_volume": Quantity.parse("50000 ft**3"),
}


def zone_scorecards() -> dict[str, str]:
    """Return the scorecard status for a normal-office and a lab-grade air-change minimum."""
    office = screen_ventilation(VentilationZone(required_air_changes=0.5, **_ZONE))
    lab = screen_ventilation(VentilationZone(required_air_changes=6.0, **_ZONE))
    return {
        "office_status": office.status.value,
        "office_fails": ", ".join(e.name for e in office.failures()),
        "lab_status": lab.status.value,
        "lab_fails": ", ".join(e.name for e in lab.failures()),
    }


def main() -> None:
    r = zone_scorecards()
    print(f"office (0.5 ACH min): {r['office_status'].upper()}")
    lab_tail = f" (fails: {r['lab_fails']})" if r["lab_fails"] else ""
    print(f"lab    (6 ACH min)  : {r['lab_status'].upper()}{lab_tail}")
    print("  -> same 800 cfm meets the outdoor-air rate but cannot make 6 air changes here")


if __name__ == "__main__":
    main()
