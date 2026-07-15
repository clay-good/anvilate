"""Worked example: the shaft sized for the average torque.

A 30 kW motor at 730 rpm drives a reciprocating compressor through a solid
shaft — a nominal torque of about 392 N·m. Sized straight off that torque
against the shaft steel's 145 MPa shear yield at a 2.0 margin, the shaft needs
only ~30 mm, so a 31 mm shaft looks fine. But a reciprocating load does not
deliver its average torque smoothly; a service factor of about 2.0 covers the
peaks. Against that 785 N·m design torque the 31 mm shaft works to 134 MPa —
a 1.08 margin, under the 2.0 requirement — and it is the peaks that fatigue a
shaft. Sizing on the design (service-factored) torque instead calls for ~38 mm,
and a 40 mm shaft carries the same peak at a comfortable 2.32. The torque a
shaft must be sized for is the peak, not the average.

Run it directly (``python examples/drive_shaft_sizing.py``);
:func:`screen_drive_shaft` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import shaft_diameter_for_torque, shaft_torsional_stress, strength_scorecard
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

NOMINAL_TORQUE = Quantity.parse("392.5 N*m")  # 30 kW at 730 rpm
SERVICE_FACTOR = 2.0  # reciprocating compressor: peaks ~ 2x the mean
DESIGN_TORQUE = Quantity.parse("785 N*m")  # SERVICE_FACTOR * NOMINAL
SHEAR_YIELD = Quantity.parse("145 MPa")  # shaft steel, ~0.577*Sy
REQUIRED_SF = 2.0
# The shaft each sizing basis calls for, rounded up to the next millimetre.
NOMINAL_DIAMETER = Quantity.parse("31 mm")  # sized on the mean torque
DESIGN_DIAMETER = Quantity.parse("40 mm")  # sized on the service-factored torque


def sizing_floors():
    """The un-rounded minimum diameter for each sizing basis."""
    on_mean = shaft_diameter_for_torque(
        torque=NOMINAL_TORQUE, allowable_shear=SHEAR_YIELD, required_safety_factor=REQUIRED_SF
    )
    on_design = shaft_diameter_for_torque(
        torque=DESIGN_TORQUE, allowable_shear=SHEAR_YIELD, required_safety_factor=REQUIRED_SF
    )
    return on_mean, on_design


def screen_drive_shaft() -> Scorecard:
    """Screen both candidate shafts against the real (service-factored) peak torque."""
    entries = []
    for name, diameter in (
        ("mean-sized 31 mm", NOMINAL_DIAMETER),
        ("design-sized 40 mm", DESIGN_DIAMETER),
    ):
        stress = shaft_torsional_stress(torque=DESIGN_TORQUE, diameter=diameter)
        entries.append(
            strength_scorecard(
                f"{name} shaft shear", stress=stress, allowable=SHEAR_YIELD, required=REQUIRED_SF
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    on_mean, on_design = sizing_floors()
    print(f"sizing floor on mean torque:   {on_mean.to('mm')}")
    print(f"sizing floor on design torque: {on_design.to('mm')}")
    card = screen_drive_shaft()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
