"""Worked example: the rod-side hose that bursts below the pump pressure.

A press cylinder runs off a 210 bar pump through a meter-out circuit -- the return (rod-side)
flow is throttled to control the speed. Every hose and fitting on the machine is rated for
350 bar, comfortably above the 210 bar the pump can make, so the plumbing looks safe. The
rod-side hose bursts anyway, and the pressure gauge on the pump never rises above 210.

The trap is pressure intensification. When the rod-side flow is throttled while the bore side
is driven, the rod-side oil is trapped, and a force balance across the piston raises its
pressure by the *area ratio*: the bore force has to be reacted over the smaller annular area,
so p_rod = p_supply·D²/(D² − d²). This cylinder has a fat 45 mm rod in a 63 mm bore, an area
ratio of 2.04, so the 210 bar supply intensifies to 429 bar on the rod side -- past the 350 bar
hose rating, a safety factor of 0.82. The hose sees a pressure the pump cannot generate and
that no gauge upstream of the cylinder ever shows.

The fix is not a stronger pump-side circuit -- that pressure was never the problem. It is to
cut the *intensification*, which means a thinner rod: dropping to a 36 mm rod lowers the area
ratio to 1.48 and the rod-side pressure to 312 bar, back inside the 350 bar rating (1.12).
Alternatively the rod-side hose is uprated for the intensified pressure. The lesson is that a
cylinder with a throttled or blocked rod side is a pressure amplifier set by its rod-to-bore
area ratio, and the rod-side components must be rated for the *intensified* pressure, not the
supply. A fat rod that helps the cylinder push harder quietly raises the pressure its own
return line must survive.

Run it directly (``python examples/hydraulic_meter_out_intensification.py``);
:func:`screen_rodside` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import cylinder_rodside_intensified_pressure
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

SUPPLY_PRESSURE = Quantity.parse("21 MPa")  # 210 bar
BORE_DIAMETER = Quantity.parse("63 mm")
HOSE_RATING = Quantity.parse("35 MPa")  # 350 bar

FAT_ROD_DIAMETER = Quantity.parse("45 mm")  # heavy intensification
THIN_ROD_DIAMETER = Quantity.parse("36 mm")  # the fix


def _screen(rod_diameter: Quantity) -> Scorecard:
    rodside = cylinder_rodside_intensified_pressure(
        supply_pressure=SUPPLY_PRESSURE, bore_diameter=BORE_DIAMETER, rod_diameter=rod_diameter
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "rod-side hose vs intensified pressure",
                computed=HOSE_RATING.to("MPa").magnitude / rodside.to("MPa").magnitude,
                required=1.0,
            ),
        )
    )


def screen_rodside() -> Scorecard:
    """Screen the fat-rod cylinder: the rod side intensifies past the hose rating."""
    return _screen(FAT_ROD_DIAMETER)


def screen_thinner_rod() -> Scorecard:
    """Screen the thinner rod: less area ratio, so the rod side stays inside the rating."""
    return _screen(THIN_ROD_DIAMETER)


def main() -> None:
    print("fat rod (45 mm):")
    print(screen_rodside())
    print("\nthinner rod (36 mm):")
    print(screen_thinner_rod())


if __name__ == "__main__":
    main()
