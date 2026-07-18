"""Worked example: the guyed cable that sang at the wrong tension.

A 10 m guy cable weighing 1.5 kg/m is exposed to a steady 8 Hz forcing — vortices
shedding off the cable in a crosswind, or a nearby machine. A cable is a tuned
string: its lateral modes sit at f_n = (n/2L)*sqrt(T/mu), set by the tension, and
if a mode lands on the forcing the cable resonates and gallops, sawing at its end
fittings. Good practice keeps the fundamental well clear of the forcing — here, at
least 1.5x above it, so the cable is stiff enough that no low mode is excited.

The tension is the tuning knob. Strung at 40 kN the fundamental falls at 8.2 Hz —
right on the 8 Hz forcing (0.68 against the 12 Hz target): the worst possible
tension, a cable tuned to its own excitation. Tightening to 90 kN lifts the
fundamental to 12.2 Hz, just clear of the keep-out band (1.02), and 150 kN puts it
at 15.8 Hz with real margin (1.32).

A tensioned cable's resonances move with the square root of tension, so a span
that hums at one tension goes quiet at another. Tune the fundamental above the
forcing, not into it. The forcing frequency is site data, declared inline like any
allowable.

Run it directly (``python examples/cable_resonance_tuning.py``);
:func:`screen_cable_resonance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import string_natural_frequency
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

CABLE_LENGTH = Quantity.parse("10 m")
CABLE_MASS_PER_LENGTH = Quantity.parse("1.5 kg/m")
FORCING_FREQUENCY = Quantity.parse("8 Hz")
SEPARATION_FACTOR = 1.5  # the fundamental must clear the forcing by this factor

TENSIONS = {
    "40 kN": Quantity.parse("40 kN"),
    "90 kN": Quantity.parse("90 kN"),
    "150 kN": Quantity.parse("150 kN"),
}


def fundamental(tension: Quantity) -> Quantity:
    """The cable's fundamental transverse frequency at a given tension."""
    return string_natural_frequency(
        tension=tension, length=CABLE_LENGTH, mass_per_length=CABLE_MASS_PER_LENGTH
    )


def screen_cable_resonance() -> Scorecard:
    """Screen each tension: the fundamental must sit above the forcing by the
    separation factor (safety factor = f_1 / (forcing * factor))."""
    target = FORCING_FREQUENCY.to("Hz").magnitude * SEPARATION_FACTOR
    entries = [
        ScorecardEntry.from_safety_factor(
            name, computed=fundamental(tension).to("Hz").magnitude / target, required=1.0
        )
        for name, tension in TENSIONS.items()
    ]
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, tension in TENSIONS.items():
        print(f"{name}: fundamental {fundamental(tension).to('Hz').magnitude:.2f} Hz")
    print(screen_cable_resonance())


if __name__ == "__main__":
    main()
