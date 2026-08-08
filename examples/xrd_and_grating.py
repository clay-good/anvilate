"""Worked example: identifying a crystal by X-ray diffraction, and dispersing light with a grating.

Diffraction turns a periodic spacing into a measurable angle, and two instruments exploit it. An
X-ray diffractometer shines a known wavelength at a crystal and reads the reflection angle to get
the atomic plane spacing — the fingerprint that names the material. A diffraction grating sends each
wavelength of light to a different angle, spreading a spectrum for a spectrometer. This example runs
both, including the inverse that XRD analysis actually uses.

The X-ray source is copper K-alpha (0.154 nm). Reflecting off crystal planes spaced 0.314 nm apart,
Bragg's law puts the first-order peak at about 14.2 degrees. Reading it the other way, a peak at
14.2 degrees recovers the 0.314 nm spacing — the step that identifies the phase. Separately, a 600
line/mm grating (1.67 micron groove spacing) sends first-order green light (550 nm) to about 19.3
degrees. The example reports the Bragg angle, the plane spacing recovered from it, and the grating
angle.

Run it directly (``python examples/xrd_and_grating.py``);
:func:`diffraction_angles` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import bragg_angle, bragg_plane_spacing, grating_diffraction_angle
from anvilate.units import Quantity

XRAY_WAVELENGTH = Quantity.parse("0.154 nm")  # Cu K-alpha
PLANE_SPACING = Quantity.parse("0.314 nm")
GRATING_GROOVE_SPACING = Quantity(magnitude=1.0 / 600e3, unit="m")  # 600 lines/mm
GREEN_WAVELENGTH = Quantity.parse("550 nm")


def diffraction_angles() -> dict[str, float]:
    """Return the Bragg angle, the plane spacing recovered from it, and the grating angle."""
    theta = bragg_angle(wavelength=XRAY_WAVELENGTH, plane_spacing=PLANE_SPACING)
    spacing = bragg_plane_spacing(wavelength=XRAY_WAVELENGTH, angle=theta)
    grating_theta = grating_diffraction_angle(
        wavelength=GREEN_WAVELENGTH, groove_spacing=GRATING_GROOVE_SPACING
    )
    return {
        "bragg_angle_deg": theta,
        "recovered_spacing_nm": spacing.to("nm").magnitude,
        "grating_angle_deg": grating_theta,
    }


def main() -> None:
    d = diffraction_angles()
    print(f"first-order Bragg angle: {d['bragg_angle_deg']:.1f} deg")
    print(f"plane spacing recovered: {d['recovered_spacing_nm']:.3f} nm")
    print(f"grating angle (550 nm, 600 lines/mm): {d['grating_angle_deg']:.1f} deg")


if __name__ == "__main__":
    main()
