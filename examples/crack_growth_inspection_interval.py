"""Worked example: how far a stress range moves a fatigue inspection interval.

A welded steel component carries a fluctuating load and is inspected in service
by a method that reliably finds cracks down to 2 mm. Damage tolerance asks: how
many cycles does a just-detectable 2 mm flaw take to grow to the 10 mm size that
would fail the section? That crack-propagation life, divided by a safety factor
on the planned inspection interval, is the margin the schedule rides on.

The Paris-Erdogan law makes the propagation life a steep function of the stress
range -- da/dN goes as (Delta-sigma)^m, so integrating from the initial to the
final crack inherits that same power. Here m = 3, so a duty cycle that raises the
stress range by half (150 -> 220 MPa) does not cost half the life; it costs more
than two thirds of it. The moderate-duty component grows its crack over ~190,000
cycles -- comfortably past twice the 50,000-cycle inspection interval, a passing
margin. The heavy-duty one, same crack, same steel, reaches failure in ~60,000
cycles: below the doubled interval, so a flaw missed at one inspection can run to
failure before the next. The schedule that was safe at moderate duty is unsafe at
heavy duty, and the cube law is why.

The crack-growth constants C and m are material data (a ferritic-pearlitic steel,
C for Delta-K in MPa*sqrt(m) and da in metres), declared inline like any
allowable.

Run it directly (``python examples/crack_growth_inspection_interval.py``);
:func:`screen_inspection_interval` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import paris_law_cycles_to_failure
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

INITIAL_CRACK = Quantity.parse("2 mm")  # smallest reliably detectable flaw
FINAL_CRACK = Quantity.parse("10 mm")  # crack size that fails the section
PARIS_COEFFICIENT = 6.9e-12  # m/cycle per (MPa*sqrt(m))^m, ferritic-pearlitic steel
PARIS_EXPONENT = 3.0

INSPECTION_INTERVAL = 50_000  # cycles between inspections
MARGIN = 2.0  # the propagation life must exceed the interval by this factor

DUTY_CYCLES = {
    "moderate duty (stress range 150 MPa)": Quantity.parse("150 MPa"),
    "heavy duty (stress range 220 MPa)": Quantity.parse("220 MPa"),
}


def screen_inspection_interval() -> Scorecard:
    """Screen each duty cycle: the crack-propagation life from the detectable flaw
    to the critical size must exceed the inspection interval by the margin
    (safety factor = N / (interval * margin))."""
    entries = []
    for name, stress_range in DUTY_CYCLES.items():
        cycles = paris_law_cycles_to_failure(
            stress_range=stress_range,
            initial_crack_length=INITIAL_CRACK,
            final_crack_length=FINAL_CRACK,
            paris_coefficient=PARIS_COEFFICIENT,
            paris_exponent=PARIS_EXPONENT,
        )
        entries.append(
            ScorecardEntry.from_safety_factor(
                name,
                computed=cycles / (INSPECTION_INTERVAL * MARGIN),
                required=1.0,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, stress_range in DUTY_CYCLES.items():
        cycles = paris_law_cycles_to_failure(
            stress_range=stress_range,
            initial_crack_length=INITIAL_CRACK,
            final_crack_length=FINAL_CRACK,
            paris_coefficient=PARIS_COEFFICIENT,
            paris_exponent=PARIS_EXPONENT,
        )
        print(f"{name}: propagation life {cycles:,.0f} cycles")
    print(screen_inspection_interval())


if __name__ == "__main__":
    main()
