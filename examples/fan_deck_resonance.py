"""Worked example: end fixity rescues a fan-deck stringer from resonance.

A 4 m stringer under a duty fan running at 1450 rpm (24.2 Hz) — an
80 x 120 x 5 mm steel box carrying ~25 kg/m of its own steel, grating, and
duct. The screen wants the deck's fundamental at least 20% above the forcing
frequency (29.0 Hz floor). Sitting on clip angles (simply supported), the
distributed-mass first mode f₁ = (π²/2π)·√(EI/m̄L⁴) lands at 17.0 Hz — BELOW
the running speed, squarely in resonance, FAIL. Welding both ends into the
headers swaps the eigenvalue π² → 22.37 (`fixed_fixed_fundamental_frequency`),
raising the same beam to 38.6 Hz — a 2.27× jump for zero added steel, PASS.
No lumped mass or stiffness estimate needed: the distributed-mass closed forms
take m̄, E·I, and L directly.

Run it directly (``python examples/fan_deck_resonance.py``);
:func:`screen_fan_deck` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    CrossSection,
    fixed_fixed_fundamental_frequency,
    frequency_scorecard,
    simply_supported_fundamental_frequency,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

SPAN = Quantity.parse("4 m")
MASS_PER_LENGTH = Quantity.parse("25 kg/m")  # stringer + grating + duct, smeared
ELASTIC_MODULUS = Quantity.parse("200 GPa")
# 1450 rpm duty fan; the deck fundamental must clear it by 20%.
MIN_FREQUENCY = Quantity(magnitude=1450 / 60 * 1.2, unit="Hz")


def screen_fan_deck() -> Scorecard:
    """Screen the stringer's first mode at both end conditions, as one card."""
    section = CrossSection.hollow_rectangular(
        width=Quantity.parse("80 mm"),
        height=Quantity.parse("120 mm"),
        wall_thickness=Quantity.parse("5 mm"),
    )
    common = {
        "mass_per_length": MASS_PER_LENGTH,
        "length": SPAN,
        "second_moment": section.second_moment,
        "elastic_modulus": ELASTIC_MODULUS,
    }
    return Scorecard(
        entries=(
            frequency_scorecard(
                "on clip angles (simply supported)",
                frequency=simply_supported_fundamental_frequency(**common),
                min_frequency=MIN_FREQUENCY,
            ),
            frequency_scorecard(
                "ends welded to headers (fixed-fixed)",
                frequency=fixed_fixed_fundamental_frequency(**common),
                min_frequency=MIN_FREQUENCY,
            ),
        )
    )


def main() -> None:
    card = screen_fan_deck()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
