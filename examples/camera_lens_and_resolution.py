"""Worked example: where a camera lens focuses, how big the image is, and the limit of sharpness.

Sizing an imaging system comes down to three questions, and geometric optics answers all of them in
closed form. Where does the image land, so the sensor can be placed there? How large is it, so the
scene fits the sensor? And how fine a detail can the lens ever resolve, no matter how well it is
built? The first two are pure geometry — the thin-lens equation and the magnification — but the
third is set by physics the geometry cannot beat: light diffracts at the aperture, and that puts a
hard floor under the finest angle two points can be told apart.

This example points a 50 mm lens at an object 2 m away. The thin-lens equation places the image
51.3 mm behind the lens — just past the focal length, as expected for a distant subject — and the
magnification is about −0.026, so the image is upright-inverted and about a fortieth of the object's
size (which is how a person metres away fits on a sensor centimetres across). Its aperture, 25 mm
across at f/2, sets a Rayleigh diffraction limit of about 5.5 arcseconds at green light — the finest
detail it could ever resolve. The example reports the image distance, the magnification, and the
diffraction-limited resolution, so the geometry and the physical sharpness ceiling are explicit.

Run it directly (``python examples/camera_lens_and_resolution.py``);
:func:`lens_system` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    diffraction_limited_angular_resolution,
    lens_transverse_magnification,
    thin_lens_image_distance,
)
from anvilate.units import Quantity

FOCAL_LENGTH = Quantity.parse("50 mm")
OBJECT_DISTANCE = Quantity.parse("2 m")
APERTURE_DIAMETER = Quantity.parse("25 mm")  # 50 mm f/2
WAVELENGTH = Quantity.parse("550 nm")  # green light


def lens_system() -> dict[str, float]:
    """Return the image distance, the magnification, and the diffraction-limited resolution."""
    image_distance = thin_lens_image_distance(
        focal_length=FOCAL_LENGTH, object_distance=OBJECT_DISTANCE
    )
    magnification = lens_transverse_magnification(
        object_distance=OBJECT_DISTANCE, image_distance=image_distance
    )
    resolution = diffraction_limited_angular_resolution(
        wavelength=WAVELENGTH, aperture_diameter=APERTURE_DIAMETER
    )
    return {
        "image_distance_mm": image_distance.to("mm").magnitude,
        "magnification": magnification,
        "resolution_arcsec": resolution.to("arcsecond").magnitude,
    }


def main() -> None:
    d = lens_system()
    print(f"image distance: {d['image_distance_mm']:.1f} mm behind the lens")
    inv = abs(1 / d["magnification"])
    print(f"magnification: {d['magnification']:.3f} (inverted, ~1/{inv:.0f} size)")
    print(f"diffraction limit at 550 nm, f/2: {d['resolution_arcsec']:.1f} arcsec")


if __name__ == "__main__":
    main()
