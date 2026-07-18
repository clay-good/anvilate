"""Worked example: keeping a drivetrain's torsional mode off the firing frequency.

An engine drives a load through a flexible coupling. The two rotating inertias -- the
engine's 0.5 kg*m^2 and the load's 2.0 kg*m^2 -- twist against each other on the
coupling's stiffness in a single torsional mode, and the engine's firing pulses feed
it torque at 40 Hz. If that mode sits on the firing frequency the coupling winds and
unwinds resonantly and tears itself apart; the fix is to place the mode's frequency
clear of the excitation, and the coupling stiffness is the knob.

Unlike a mass on a spring, both inertias move, so the mode is the free-free two-rotor
frequency (1/2pi)*sqrt(k*(I1+I2)/(I1*I2)), set by the *reduced* inertia I1*I2/(I1+I2).
A soft 20 kN*m/rad coupling puts it at 35.6 Hz -- only 0.89 of the firing frequency,
squarely in the danger band, so a 1.4x separation requirement fails it. Stiffening the
coupling to 100 kN*m/rad lifts the mode to 79.6 Hz, twice the firing frequency (1.99),
comfortably clear. Here the stiffer coupling is the safe one, because it carries the
mode *up and over* the excitation rather than leaving it underneath.

The lesson is that a coupling is not chosen for stiffness alone but for where it puts
the drivetrain's torsional mode relative to the excitation it will actually see -- and
that mode depends on both inertias, not just the one you happen to think of as the
load. The inertias, stiffnesses, and firing frequency are declared inline.

Run it directly (``python examples/drivetrain_torsional_mode.py``);
:func:`screen_drivetrain_mode` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import two_rotor_torsional_natural_frequency
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

ENGINE_INERTIA = Quantity.parse("0.5 kg*m**2")
LOAD_INERTIA = Quantity.parse("2.0 kg*m**2")
FIRING_FREQUENCY = Quantity.parse("40 Hz")
REQUIRED_SEPARATION = 1.4  # the torsional mode must exceed the firing frequency by this
COUPLINGS = {
    "soft coupling (20 kN*m/rad)": Quantity.parse("20 kN*m"),
    "stiff coupling (100 kN*m/rad)": Quantity.parse("100 kN*m"),
}


def screen_drivetrain_mode() -> Scorecard:
    """Screen each coupling's two-rotor torsional mode against the firing frequency
    (safety factor = (mode / firing) / required separation)."""
    firing = FIRING_FREQUENCY.to("Hz").magnitude
    entries = []
    for name, stiffness in COUPLINGS.items():
        mode = (
            two_rotor_torsional_natural_frequency(
                torsional_stiffness=stiffness,
                polar_mass_moment_1=ENGINE_INERTIA,
                polar_mass_moment_2=LOAD_INERTIA,
            )
            .to("Hz")
            .magnitude
        )
        entries.append(
            ScorecardEntry.from_safety_factor(
                name, computed=(mode / firing) / REQUIRED_SEPARATION, required=1.0
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, stiffness in COUPLINGS.items():
        mode = two_rotor_torsional_natural_frequency(
            torsional_stiffness=stiffness,
            polar_mass_moment_1=ENGINE_INERTIA,
            polar_mass_moment_2=LOAD_INERTIA,
        )
        print(f"{name}: torsional mode {mode.to('Hz').magnitude:.1f} Hz")
    print(f"firing frequency: {FIRING_FREQUENCY.to('Hz').magnitude:.0f} Hz")
    print(screen_drivetrain_mode())


if __name__ == "__main__":
    main()
