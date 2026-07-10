"""Worked example: static margin says nothing about resonance.

One :class:`BeamMember` declaration — a 3 m simply-supported 80 x 120 x 5 mm
A36 box under a skid-mounted pump (1.5 N/mm smeared load, 40 kg/m of beam,
grating, and pump mass, 1450 rpm running speed) — and one screen returns all
three check dimensions. Statically the beam is bulletproof: bending SF 9.27
against yield and 2.1 mm of deflection inside L/360 = 8.3 mm. But the same
declaration's distributed-mass fundamental lands at 23.9 Hz, under the
29.0 Hz floor (1450 rpm x 1.2) — the beam idles at ~80% of the forcing
frequency, and the scorecard FAILs on the one dimension a static hand calc
never sees. Declaring ``mass_per_length`` and ``min_frequency`` is what puts
the modal check on the card.

Run it directly (``python examples/pump_mezzanine_beam.py``);
:func:`screen_pump_beam` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CrossSection
from anvilate.packs.structural import BeamMember, LoadType, Support, screen_beam_member
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

SPAN = Quantity.parse("3 m")
DECK_LOAD = Quantity.parse("1.5 N/mm")  # pump skid + deck, smeared over the span
MASS_PER_LENGTH = Quantity.parse("40 kg/m")  # beam + grating + pump mass, smeared
DEFLECTION_LIMIT = Quantity(magnitude=3000 / 360, unit="mm")  # L/360
MIN_FREQUENCY = Quantity(magnitude=1450 / 60 * 1.2, unit="Hz")  # 20% over 1450 rpm
REQUIRED_SF = 1.5


def screen_pump_beam() -> Scorecard:
    """One declaration, three check dimensions: strength, stiffness, modal."""
    member = BeamMember(
        name="pump beam",
        section=CrossSection.hollow_rectangular(
            width=Quantity.parse("80 mm"),
            height=Quantity.parse("120 mm"),
            wall_thickness=Quantity.parse("5 mm"),
        ),
        length=SPAN,
        support=Support.SIMPLY_SUPPORTED,
        load=DECK_LOAD,
        load_type=LoadType.DISTRIBUTED,
        material="ASTM-A36",
        deflection_limit=DEFLECTION_LIMIT,
        mass_per_length=MASS_PER_LENGTH,
        min_frequency=MIN_FREQUENCY,
    )
    return screen_beam_member(member, required_safety_factor=REQUIRED_SF)


def main() -> None:
    card = screen_pump_beam()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
