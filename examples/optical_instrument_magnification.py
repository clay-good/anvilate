"""Worked example: the magnifying power of a telescope, a magnifier, and a microscope.

Three familiar instruments enlarge the world in three different ways, and each one's magnifying
power follows from its focal lengths. This example computes the angular magnification of a small
telescope, a hand magnifier, and a compound microscope — the number that tells you how much bigger
each makes its subject appear to the eye.

A telescope with a 1000 mm objective and a 25 mm eyepiece magnifies 40 times (f_o/f_e). A hand
magnifier of 50 mm focal length gives 5 times, from the 250 mm near point over the focal length. A
compound microscope with a 160 mm tube, a 4 mm objective, and a 25 mm eyepiece reaches 400 times —
the objective's 40x linear magnification times the eyepiece's 10x angular magnification. The example
reports all three magnifications.

Run it directly (``python examples/optical_instrument_magnification.py``);
:func:`instrument_powers` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    magnifier_angular_magnification,
    microscope_magnification,
    telescope_angular_magnification,
)
from anvilate.units import Quantity


def instrument_powers() -> dict[str, float]:
    """Return the telescope, magnifier, and microscope angular magnifications."""
    telescope = telescope_angular_magnification(
        objective_focal_length=Quantity.parse("1000 mm"),
        eyepiece_focal_length=Quantity.parse("25 mm"),
    )
    magnifier = magnifier_angular_magnification(focal_length=Quantity.parse("50 mm"))
    microscope = microscope_magnification(
        tube_length=Quantity.parse("160 mm"),
        objective_focal_length=Quantity.parse("4 mm"),
        eyepiece_focal_length=Quantity.parse("25 mm"),
    )
    return {
        "telescope_magnification": telescope,
        "magnifier_magnification": magnifier,
        "microscope_magnification": microscope,
    }


def main() -> None:
    d = instrument_powers()
    print(f"telescope magnification: {d['telescope_magnification']:.0f}x")
    print(f"magnifier magnification: {d['magnifier_magnification']:.0f}x")
    print(f"microscope magnification: {d['microscope_magnification']:.0f}x")


if __name__ == "__main__":
    main()
