"""Worked example: the drivetrain twist mode a lateral screen never sees.

A 5 kg, 200 mm flywheel rides a 500 mm steel stub shaft driven at 3000 rpm —
torque pulsation excites the drivetrain at the 50 Hz running speed, and the
screen wants the torsional mode 20% above it (60 Hz floor). On the Ø20 mm
shaft as drawn, k_t = G·J/L = 2513 N·m/rad against the disc's I = m·d²/8 =
0.025 kg·m² puts the twist mode at 50.5 Hz — dead on the forcing frequency,
FAIL. Upsizing the shaft to Ø25 mm multiplies J (∝ d⁴) by 2.44, and the
frequency (∝ √k_t ∝ d²) by 1.56: 78.8 Hz, PASS. A 25% shaft upsize moves the
torsional mode 56% — stiffness is the cheap lever, the flywheel inertia is
usually fixed by function.

Run it directly (``python examples/flywheel_torsional_mode.py``);
:func:`screen_flywheel_drive` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    frequency_scorecard,
    polar_second_moment_solid,
    shaft_torsional_stiffness,
    solid_disc_polar_mass_moment,
    torsional_natural_frequency,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

SHAFT_LENGTH = Quantity.parse("500 mm")
SHEAR_MODULUS = Quantity.parse("80 GPa")  # steel G
FLYWHEEL = solid_disc_polar_mass_moment(
    mass=Quantity.parse("5 kg"), diameter=Quantity.parse("200 mm")
)
# 3000 rpm drive; the twist mode must clear the torque-ripple frequency by 20%.
MIN_FREQUENCY = Quantity(magnitude=3000 / 60 * 1.2, unit="Hz")

_SHAFTS = (
    ("Ø20 shaft as drawn", "20 mm"),
    ("Ø25 shaft upsized", "25 mm"),
)


def screen_flywheel_drive() -> Scorecard:
    """Screen the flywheel's torsional mode on both shaft sizes, as one card."""
    entries = []
    for name, diameter in _SHAFTS:
        stiffness = shaft_torsional_stiffness(
            polar_second_moment=polar_second_moment_solid(Quantity.parse(diameter)),
            length=SHAFT_LENGTH,
            shear_modulus=SHEAR_MODULUS,
        )
        mode = torsional_natural_frequency(
            torsional_stiffness=stiffness, polar_mass_moment=FLYWHEEL
        )
        entries.append(frequency_scorecard(name, frequency=mode, min_frequency=MIN_FREQUENCY))
    return Scorecard(entries=tuple(entries))


def main() -> None:
    card = screen_flywheel_drive()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
