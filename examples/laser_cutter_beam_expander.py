"""Worked example: the beam expander that finally cuts a fine kerf.

A fiber laser cutter runs at 1064 nm and needs a focused spot no larger than 15 um in radius to hold
a clean, narrow kerf. The raw beam leaves the collimator at 2 mm radius and goes straight into the
100 mm focusing lens. A Gaussian beam focuses to w_f = lambda*f/(pi*w), so that 2 mm beam lands a
16.9 um spot -- bigger than the 15 um the job needs, a safety factor of 0.89. The kerf comes out
wide and ragged, and no amount of power fixes it: the spot size is set by diffraction and the beam
geometry, not the wattage.

The counterintuitive fix is to make the beam *bigger* before the lens. Because the focused spot
scales as 1/w, doubling the input radius halves the spot. Dropping in a 2x beam expander widens the
beam to 4 mm at the lens, and the same lens now forms an 8.5 um spot -- a safety factor of 1.77,
comfortably inside spec. The kerf tightens and the edge cleans up.

The lesson is that focus quality is won at the beam, not the lens or the power supply: a wide,
well-collimated beam filling the focusing optic makes the tightest spot, which is why every precision
laser tool expands its beam before the final lens.

Run it directly (``python examples/laser_cutter_beam_expander.py``);
:func:`screen_raw_beam` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import focused_spot_radius
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

WAVELENGTH = Quantity.parse("1064 nm")
FOCAL_LENGTH = Quantity.parse("100 mm")
RAW_BEAM_RADIUS = Quantity.parse("2 mm")
EXPANDED_BEAM_RADIUS = Quantity.parse("4 mm")  # after a 2x beam expander
REQUIRED_SPOT_RADIUS = Quantity.parse("15 um")


def _screen(input_beam_radius: Quantity) -> Scorecard:
    spot = focused_spot_radius(
        wavelength=WAVELENGTH,
        focal_length=FOCAL_LENGTH,
        input_beam_radius=input_beam_radius,
    )
    margin = REQUIRED_SPOT_RADIUS.to("um").magnitude / spot.to("um").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "focused spot vs required kerf",
                computed=margin,
                required=1.0,
            ),
        )
    )


def screen_raw_beam() -> Scorecard:
    """Screen the raw 2 mm beam: it focuses too large for the required kerf."""
    return _screen(RAW_BEAM_RADIUS)


def screen_expanded_beam() -> Scorecard:
    """Screen the 4 mm expanded beam: the wider beam focuses tight enough."""
    return _screen(EXPANDED_BEAM_RADIUS)


def main() -> None:
    print("raw 2 mm beam:")
    print(screen_raw_beam())
    print("\nexpanded 4 mm beam:")
    print(screen_expanded_beam())


if __name__ == "__main__":
    main()
