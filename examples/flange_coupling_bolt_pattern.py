"""Worked example: the coupling that needs two more bolts, not bigger ones.

A rigid flange coupling joins a 30 kW gearmotor to a crusher shaft: 955 N·m of steady
torque, doubled to 1,910 N·m by the shock service factor the crusher demands. The
bolts sit on an 80 mm bolt circle and the chosen M12 fitted bolts are good for 5 kN of
shear each -- an allowable the designer supplies from the bolt grade, as with any
material allowable.

The four-bolt pattern the flange was sketched with does not survive the arithmetic:
each bolt must carry T/(n*R) = 5,969 N, an 0.84 safety factor against its 5 kN
allowable. The bolt-count inverse says the torque needs five bolts at minimum -- and a
five-bolt pattern is a machinist's and balancer's nuisance, so the practical answer is
the next even count. Six bolts drop the per-bolt shear to 3,979 N, a comfortable 1.26
safety factor, with the drilling still on the same bolt circle.

The lesson is that a flange coupling's capacity is bought by bolt count and bolt-circle
radius (T = n*F*R -- the classic bolt-circle torque share, Shigley), and count is the
cheaper lever: two more holes cost nothing, while thicker bolts mean re-boring and
re-fitting every hole. Size the pattern from the inverse, then round up to symmetry.

Run it directly (``python examples/flange_coupling_bolt_pattern.py``);
:func:`screen_four_bolt_coupling` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import flange_coupling_bolt_count, flange_coupling_bolt_force
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

DESIGN_TORQUE = Quantity.parse("1910 N*m")  # 955 N*m steady x 2.0 shock service factor
BOLT_CIRCLE_RADIUS = Quantity.parse("80 mm")
ALLOWABLE_BOLT_SHEAR = Quantity.parse("5 kN")  # user-supplied, from the bolt grade


def _screen(num_bolts: int) -> Scorecard:
    per_bolt = flange_coupling_bolt_force(
        torque=DESIGN_TORQUE,
        bolt_circle_radius=BOLT_CIRCLE_RADIUS,
        num_bolts=num_bolts,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                f"bolt shear ({num_bolts}-bolt pattern)",
                computed=ALLOWABLE_BOLT_SHEAR.to("N").magnitude / per_bolt.to("N").magnitude,
                required=1.0,
            ),
        )
    )


def screen_four_bolt_coupling() -> Scorecard:
    """Screen the sketched four-bolt pattern: each bolt is overloaded."""
    return _screen(4)


def screen_six_bolt_coupling() -> Scorecard:
    """Screen the six-bolt pattern: the even count above the five-bolt minimum."""
    return _screen(6)


def minimum_bolt_count() -> int:
    """The fewest bolts the design torque needs at the allowable per-bolt shear."""
    return flange_coupling_bolt_count(
        torque=DESIGN_TORQUE,
        bolt_circle_radius=BOLT_CIRCLE_RADIUS,
        allowable_bolt_force=ALLOWABLE_BOLT_SHEAR,
    )


def main() -> None:
    print("four-bolt pattern:")
    print(screen_four_bolt_coupling().report())
    print(f"\nminimum bolts for the torque: {minimum_bolt_count()}")
    print("\nsix-bolt pattern (next even count):")
    print(screen_six_bolt_coupling().report())


if __name__ == "__main__":
    main()
