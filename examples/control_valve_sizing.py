"""Worked example: the control valve that cannot pass its own duty.

A cooling-water loop needs a control valve to pass 200 gpm of water with 10 psi of pressure drop
allotted to the valve. The turbulent-liquid valve equation Q = Cv*sqrt(dP/SG) inverts to a required
flow coefficient Cv = Q/sqrt(dP/SG) = 200/sqrt(10) = 63.2. A 2-inch valve on the shelf is rated
Cv 50 -- below the duty. Selected anyway, it runs pinned near wide open and still cannot pass
200 gpm
at only 10 psi; the loop starves. The safety factor of rated-to-required Cv is 0.79, under one,
which
is the tell that the valve is undersized before it is ever installed.

Stepping up to a 3-inch valve rated Cv 80 clears it: 80 vs the 63.2 required is a safety factor of
1.26, so the valve passes the flow with travel to spare and room to throttle. It is not oversized to
waste -- a valve that must sit near wide open has no control authority left, and one with a little
margin can modulate.

The lesson is that a control valve is sized against the Cv its duty demands, not its pipe size:
match the rated Cv to Q/sqrt(dP/SG) with margin, and confirm the valve still owns enough of the loop
pressure drop to actually control the flow.

Run it directly (``python examples/control_valve_sizing.py``);
:func:`screen_undersized_valve` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import required_flow_coefficient
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

DESIGN_FLOW = Quantity.parse("200 gallon/minute")
ALLOTTED_PRESSURE_DROP = Quantity.parse("10 psi")
WATER_SPECIFIC_GRAVITY = 1.0
UNDERSIZED_VALVE_CV = 50.0  # 2-inch valve
SELECTED_VALVE_CV = 80.0  # 3-inch valve


def _screen(rated_cv: float) -> Scorecard:
    required_cv = required_flow_coefficient(
        flow_rate=DESIGN_FLOW,
        pressure_drop=ALLOTTED_PRESSURE_DROP,
        specific_gravity=WATER_SPECIFIC_GRAVITY,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "rated Cv vs required Cv",
                computed=rated_cv / required_cv,
                required=1.0,
            ),
        )
    )


def screen_undersized_valve() -> Scorecard:
    """Screen the Cv 50 valve: it falls short of the duty's required coefficient."""
    return _screen(UNDERSIZED_VALVE_CV)


def screen_selected_valve() -> Scorecard:
    """Screen the Cv 80 valve: it passes the flow with throttling margin."""
    return _screen(SELECTED_VALVE_CV)


def main() -> None:
    print("undersized valve (Cv 50):")
    print(screen_undersized_valve())
    print("\nselected valve (Cv 80):")
    print(screen_selected_valve())


if __name__ == "__main__":
    main()
