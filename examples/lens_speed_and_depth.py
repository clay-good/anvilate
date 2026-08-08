"""Worked example: what an f-number buys — light and depth of field against a sharper focus.

The f-number of a lens, its focal length over its aperture diameter, is the single knob that sets a
lens's character. Open up (a low f-number) and the lens is fast: it gathers a lot of light and
throws the background out of focus, but its focused spot is tightest only up to a point. Stop down
(a high f-number) and it grows slow but the depth of field deepens, until diffraction — which widens
the focused spot in proportion to the f-number — starts to soften the whole image. Every lens lives
in that trade, and three closed-form numbers pin it down.

This example works with a 50 mm lens. Wide open at a 25 mm aperture it is an f/2 lens. At that
setting its diffraction-limited focused spot, at green light, is about 2.7 µm across — the tightest
point it can render, worth matching to the sensor's pixel pitch. Stopped down to f/8 for depth of
field, and accepting a 0.03 mm circle of confusion (the 35 mm-format standard), its hyperfocal
distance is about 10.4 m: focus there and everything from ~5.2 m to infinity is sharp. The example
reports the f/2 f-number, its Airy spot, and the f/8 hyperfocal distance, so the light-versus-depth-
versus-sharpness trade is explicit.

Run it directly (``python examples/lens_speed_and_depth.py``);
:func:`lens_speed` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    diffraction_limited_spot_diameter,
    hyperfocal_distance,
    lens_f_number,
)
from anvilate.units import Quantity

FOCAL_LENGTH = Quantity.parse("50 mm")
WIDE_APERTURE = Quantity.parse("25 mm")  # f/2
WAVELENGTH = Quantity.parse("550 nm")
STOPPED_DOWN_F_NUMBER = 8.0
CIRCLE_OF_CONFUSION = Quantity.parse("0.03 mm")  # 35 mm-format standard


def lens_speed() -> dict[str, float]:
    """Return the wide-open f-number, its Airy spot, and the f/8 hyperfocal distance."""
    f_number = lens_f_number(focal_length=FOCAL_LENGTH, aperture_diameter=WIDE_APERTURE)
    spot = diffraction_limited_spot_diameter(wavelength=WAVELENGTH, f_number=f_number)
    hyperfocal = hyperfocal_distance(
        focal_length=FOCAL_LENGTH,
        f_number=STOPPED_DOWN_F_NUMBER,
        circle_of_confusion=CIRCLE_OF_CONFUSION,
    )
    return {
        "f_number": f_number,
        "airy_spot_um": spot.to("micrometer").magnitude,
        "hyperfocal_m": hyperfocal.to("m").magnitude,
    }


def main() -> None:
    d = lens_speed()
    print(f"wide-open f-number: f/{d['f_number']:.0f}")
    print(f"diffraction-limited focused spot at f/2: {d['airy_spot_um']:.1f} um")
    print(
        f"hyperfocal distance at f/8: {d['hyperfocal_m']:.1f} m "
        f"(sharp from ~{d['hyperfocal_m'] / 2:.1f} m to infinity)"
    )


if __name__ == "__main__":
    main()
