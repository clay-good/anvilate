"""Worked example: the reflection loss and polarizing angle of a glass surface.

Every air-glass surface reflects some light — the glare on a window, the ghost images in an
uncoated lens. The Fresnel equations quantify it: how much reflects at each face, how much a slab
passes after losing at both faces, and the angle at which the reflection becomes fully polarized.
This example works them for ordinary crown glass.

Crown glass (refractive index 1.5) in air reflects about 4% of light at each surface at normal
incidence. A plain glass plate, losing 4% at both faces, transmits about 92% — the 8% loss that
stacks up through a multi-element uncoated lens and drove the invention of anti-reflection coatings.
Tilting the glass to the Brewster angle of about 56 degrees fully polarizes the reflected light,
which is how polarizing sunglasses cut glare and how laser Brewster windows work. The example
reports the single-surface reflectance, the slab transmittance, and the Brewster angle.

Run it directly (``python examples/glass_surface_reflection.py``);
:func:`glass_reflection` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import brewster_angle, fresnel_normal_reflectance, slab_transmittance

AIR_INDEX = 1.0
GLASS_INDEX = 1.5


def glass_reflection() -> dict[str, float]:
    """Return the single-surface reflectance, the slab transmittance, and the Brewster angle."""
    reflectance = fresnel_normal_reflectance(
        incident_index=AIR_INDEX, transmitted_index=GLASS_INDEX
    )
    transmittance = slab_transmittance(incident_index=AIR_INDEX, slab_index=GLASS_INDEX)
    brewster = brewster_angle(incident_index=AIR_INDEX, transmitted_index=GLASS_INDEX)
    return {
        "surface_reflectance_percent": reflectance * 100.0,
        "slab_transmittance_percent": transmittance * 100.0,
        "brewster_angle_deg": brewster,
    }


def main() -> None:
    d = glass_reflection()
    print(f"single-surface reflectance: {d['surface_reflectance_percent']:.0f}%")
    print(f"slab transmittance (two faces): {d['slab_transmittance_percent']:.0f}%")
    print(f"Brewster angle: {d['brewster_angle_deg']:.0f} deg")


if __name__ == "__main__":
    main()
