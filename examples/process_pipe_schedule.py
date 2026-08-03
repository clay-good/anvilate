"""Worked example: the pipe schedule a service pressure needs, allowances included.

A process line carries 5 MPa at temperature, and the question is which wall
schedule to buy. The ASME B31.3 pressure-design formula t = P·D/(2·(S·E + P·Y))
gives the wall the pressure alone requires — but the pipe you install is not the
wall you get to keep. Mill tolerance means the pipe can ship up to 12.5% thinner
than nominal, and a corrosion allowance is metal you set aside to be eaten over the
line's life. The pressure has to be carried by what is left: the *available* wall,
nominal minus the mill tolerance minus the corrosion allowance.

For NPS 4 pipe (114.3 mm OD) in an A106-B line (allowable 138 MPa, E = 1, Y = 0.4),
a Schedule 10 wall looks like plenty at 3.05 mm — but after the 12.5% mill tolerance
and a 1.5 mm corrosion allowance only about 1.2 mm is left to hold pressure, and its
rating falls below the 5 MPa service. Schedule 40 (6.02 mm nominal) keeps about
3.8 mm available and rates well past the service with margin to spare.

The lesson is to rate the wall you can rely on, not the wall stamped on the pipe.
Anvilate evaluates the B31.3 formula and its pressure inverse; the allowable stress,
quality factor, and coefficient come from the code and the caller, and the
allowances are the caller's to declare. Run it directly
(``python examples/process_pipe_schedule.py``); :func:`screen_schedule` is exercised
in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import asme_b313_pipe_pressure
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

SERVICE_PRESSURE = Quantity.parse("5 MPa")
OUTSIDE_DIAMETER = Quantity.parse("114.3 mm")  # NPS 4
ALLOWABLE_STRESS = Quantity.parse("138 MPa")  # A106-B at temperature (user-supplied)

MILL_TOLERANCE = 0.125  # 12.5% under-thickness the mill may ship
CORROSION_ALLOWANCE = Quantity.parse("1.5 mm")

SCHEDULE_10 = Quantity.parse("3.05 mm")  # nominal wall
SCHEDULE_40 = Quantity.parse("6.02 mm")


def _available_wall(nominal: Quantity) -> Quantity:
    """The wall left to hold pressure: nominal, less mill tolerance and corrosion."""
    left = (
        nominal.to("mm").magnitude * (1.0 - MILL_TOLERANCE) - CORROSION_ALLOWANCE.to("mm").magnitude
    )
    return Quantity(magnitude=max(left, 0.0), unit="mm")


def screen_schedule(nominal_wall: Quantity) -> Scorecard:
    """Screen a pipe schedule's available wall against the service pressure.

    The safety factor is the pressure rating of the available wall over the service
    pressure (the B31.3 allowable already embeds the code margin, so the target is
    1.0).
    """
    available = _available_wall(nominal_wall)
    rating = asme_b313_pipe_pressure(
        wall_thickness=available,
        outside_diameter=OUTSIDE_DIAMETER,
        allowable_stress=ALLOWABLE_STRESS,
    )
    safety = rating.to("MPa").magnitude / SERVICE_PRESSURE.to("MPa").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "B31.3 pressure design", computed=safety, required=1.0
            ).model_copy(update={"reference": "ASME B31.3 §304.1.2"}),
        )
    )


def screen_schedule_10() -> Scorecard:
    """Schedule 10: mill tolerance and corrosion drop it below the service pressure."""
    return screen_schedule(SCHEDULE_10)


def screen_schedule_40() -> Scorecard:
    """Schedule 40: it keeps enough available wall to clear the service pressure."""
    return screen_schedule(SCHEDULE_40)


def main() -> None:
    for label, wall in (("Schedule 10", SCHEDULE_10), ("Schedule 40", SCHEDULE_40)):
        available = _available_wall(wall).to("mm").magnitude
        rating = (
            asme_b313_pipe_pressure(
                wall_thickness=_available_wall(wall),
                outside_diameter=OUTSIDE_DIAMETER,
                allowable_stress=ALLOWABLE_STRESS,
            )
            .to("MPa")
            .magnitude
        )
        print(f"{label}: available wall {available:.2f} mm -> rating {rating:.2f} MPa")
        print(f"  {screen_schedule(wall).entries[0]}")


if __name__ == "__main__":
    main()
