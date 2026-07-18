"""Worked example: how far you can stretch a gear pair's centre distance.

A 20-tooth pinion and 40-tooth gear, 2 mm module, are cut for the standard 60 mm
centre distance, where they mesh at their 20-degree pressure angle. But the housing
they must fit is bored a little wider. Can the same gears run at the wider centre, and
if so, at what cost?

They can -- the base circles are fixed, so the teeth still touch -- but the mesh
tightens onto a higher *operating* pressure angle as the centres spread, and the gears
have to be profile-shifted (their teeth cut thicker) to take up the resulting backlash.
At a 62 mm centre the operating pressure angle rises to 24.6 degrees and the pair needs
1.11 of total profile shift: steep, but inside the ~25-degree ceiling above which the
radial tooth thrust balloons and the contact ratio thins toward rough, load-sharing-
starved running. Push the centre to 63 mm and the operating angle passes 26.5 degrees
and 1.74 of shift -- past the practical limit; that housing does not just want shifted
gears, it wants a redesign (a finer module or more teeth) sized for its actual centre.

The lesson is that a gear pair's centre distance is not a free fit-up dimension. A
small stretch is absorbed by profile shift, but the operating pressure angle climbs
with it and caps how far you can go before the mesh degrades -- so a housing bored off
the standard centre is checked against that cap, not just assembled and hoped for. The
gear geometry and candidate centres are declared inline.

Run it directly (``python examples/gear_nonstandard_center.py``);
:func:`screen_gear_centers` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    operating_pressure_angle,
    profile_shift_sum_for_center_distance,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

PAIR = {
    "module": Quantity.parse("2 mm"),
    "pinion_teeth": 20,
    "gear_teeth": 40,
    "pressure_angle": 20.0,
}
MAX_OPERATING_PRESSURE_ANGLE = 25.0  # practical ceiling in degrees
CANDIDATE_CENTERS = (Quantity.parse("62 mm"), Quantity.parse("63 mm"))


def screen_gear_centers() -> Scorecard:
    """Screen the operating pressure angle at each candidate centre distance against
    the 25-degree practical ceiling (safety factor = ceiling / operating angle)."""
    entries = []
    for center in CANDIDATE_CENTERS:
        phi_w = operating_pressure_angle(operating_center_distance=center, **PAIR)
        entries.append(
            ScorecardEntry.from_safety_factor(
                f"{center.to('mm').magnitude:.0f} mm centre",
                computed=MAX_OPERATING_PRESSURE_ANGLE / phi_w,
                required=1.0,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for center in CANDIDATE_CENTERS:
        phi_w = operating_pressure_angle(operating_center_distance=center, **PAIR)
        shift = profile_shift_sum_for_center_distance(operating_center_distance=center, **PAIR)
        print(
            f"{center.to('mm').magnitude:.0f} mm centre: operating pressure angle "
            f"{phi_w:.1f} deg, total profile shift {shift:.2f}"
        )
    print(screen_gear_centers())


if __name__ == "__main__":
    main()
