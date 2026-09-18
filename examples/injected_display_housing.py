"""Worked example: an injected-display housing whose display ribbon pulls the boresight off.

A 2 W display sits behind a combiner in a sealed housing, and the eye sees the display
reflected off the combiner and the world through it. Four screens answer for it:

- the display and backlight warm the inside by 8.0 K through a 4 K/W path, inside 10 K;
- the combiner's retainer bears on a 4 mm edge radius, putting 5.14 MPa of tension into
  the glass against a 7 MPa allowable;
- the display ribbon crosses from the housing to the display mount, and routed 3 mm off
  its free shape it pulls the mount 8.97 µm and the display's line of sight 358.9 µrad,
  against 100 µrad;
- and the boresight between the display and the world, where the housing's tilt moves both
  paths and cancels, the combiner's tilt turns only the reflected path by twice its angle,
  and the ribbon's pull acts on the display alone. By root-sum-square those reach
  462.0 µrad against a 400 µrad allowance.

The harness and the boresight fail together, for one cause. The repair is a service loop
that lets the ribbon sit 0.5 mm off its free shape: the pull falls to 59.8 µrad and the
boresight to 297.0 µrad, and the card passes. The beam-path keepout this workflow also
needs is not generated here, because the keepout envelopes are not built yet.

Run it directly (``python examples/injected_display_housing.py``); :func:`card` and
:func:`repaired_card` are also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis.optomechanics import (
    HarnessCrossing,
    boresight_scorecard,
    enclosure_rise_scorecard,
    glass_contact_stress_scorecard,
    harness_load_scorecard,
    mirror_tilt_line_of_sight,
)
from anvilate.budget import CombinationRule
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

q = Quantity.parse
FOCAL_LENGTH = q("25 mm")  # the display's collimating optic
COMBINER_TILT = q("0.5 arcmin")  # the combiner's mounting tolerance
HOUSING_TILT = q("50 µrad")  # moves both paths together


def _ribbon(routing_offset: str) -> HarnessCrossing:
    return HarnessCrossing(
        harness="display ribbon",
        stiffness=q("150 N/m"),
        routing_offset=q(routing_offset),
        lever_arm=q("12 mm"),
    )


def _card(routing_offset: str) -> Scorecard:
    ribbon = _ribbon(routing_offset)
    harness = harness_load_scorecard(
        "display mount harness load",
        crossings=(ribbon,),
        mount_stiffness=q("5e4 N/m"),
        focal_length=FOCAL_LENGTH,
        allowed_line_of_sight=q("100 µrad"),
    )
    assert harness.comparison is not None
    pulled = harness.comparison.measured
    combiner = mirror_tilt_line_of_sight(tilt=COMBINER_TILT)
    boresight = boresight_scorecard(
        "display-to-world boresight",
        # The display reaches the eye off the combiner; the world passes through it, and a
        # plate tilt displaces a collimated beam without turning it.
        first_path={
            "housing tilt": HOUSING_TILT,
            "combiner tilt": combiner,
            "display mount harness": pulled,
        },
        second_path={"housing tilt": HOUSING_TILT},
        allowance=q("400 µrad"),
        rule=CombinationRule.RSS,
    )
    return Scorecard(
        entries=(
            enclosure_rise_scorecard(
                "display self-heating",
                dissipations={"display": q("1.5 W"), "backlight": q("0.5 W")},
                thermal_resistance=q("4 K/W"),
                allowed_rise=q("10 K"),
            ),
            glass_contact_stress_scorecard(
                "combiner retainer contact",
                preload=q("20 N"),
                contact_diameter=q("30 mm"),
                glass_radius=q("1e6 mm"),
                mount_radius=q("4 mm"),
                glass_modulus=q("82 GPa"),
                glass_poisson=0.206,
                mount_modulus=q("69 GPa"),
                mount_poisson=0.33,
                allowable_tensile_stress=q("7 MPa"),
            ),
            harness,
            boresight,
        )
    )


def card() -> Scorecard:
    """The housing as drawn: the ribbon routed 3 mm off its free shape."""
    return _card("3 mm")


def repaired_card() -> Scorecard:
    """The repair: a service loop that lets the ribbon sit 0.5 mm off its free shape."""
    return _card("0.5 mm")


def main() -> None:
    for label, scorecard in (("as drawn", card()), ("ribbon rerouted", repaired_card())):
        print(f"{label}: {scorecard.status.value}")
        for entry in scorecard.entries:
            print(f"  {entry}")


if __name__ == "__main__":
    main()
