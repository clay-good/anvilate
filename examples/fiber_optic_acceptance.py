"""Worked example: why light stays trapped in an optical fibre — refraction and total reflection.

Light crossing between two transparent media bends by Snell's law, and how much it bends depends on
the index contrast. Push the angle far enough, going from a denser medium to a rarer one, and the
light stops crossing altogether: past the critical angle it is totally internally reflected, trapped
inside. That trapping is what makes an optical fibre work — a slightly denser core inside a lower-
index cladding — and the range of input angles the fibre will accept and guide is captured in a
single number, its numerical aperture.

This example first bends a ray from air (index 1.0) into glass (index 1.5) at 30° incidence: Snell's
law refracts it to about 19.5° from the normal, toward the surface normal as expected for a denser
medium. Going the other way, a ray inside that glass meets its surface at a critical angle of about
41.8°; steeper than that and it cannot escape. Finally, a step-index fibre with a 1.48 core and 1.46
cladding has a numerical aperture of about 0.24 — an acceptance half-angle of roughly 14° — so light
arriving within that cone couples in and is guided. The example reports the refracted angle, the
critical angle, and the fibre NA, so the chain from refraction to trapped, guided light is explicit.

Run it directly (``python examples/fiber_optic_acceptance.py``);
:func:`fiber_optics` is also exercised in the test suite.
"""

from __future__ import annotations

from math import asin, degrees

from anvilate.analysis import (
    critical_angle,
    fiber_numerical_aperture,
    snell_refraction_angle,
)

AIR_INDEX = 1.0
GLASS_INDEX = 1.5
INCIDENCE_ANGLE = 30.0
FIBER_CORE_INDEX = 1.48
FIBER_CLADDING_INDEX = 1.46


def fiber_optics() -> dict[str, float]:
    """Return the Snell refracted angle, the critical angle, and the fibre NA and cone angle."""
    refracted = snell_refraction_angle(
        incident_angle=INCIDENCE_ANGLE,
        incident_index=AIR_INDEX,
        refracted_index=GLASS_INDEX,
    )
    crit = critical_angle(incident_index=GLASS_INDEX, transmitted_index=AIR_INDEX)
    na = fiber_numerical_aperture(core_index=FIBER_CORE_INDEX, cladding_index=FIBER_CLADDING_INDEX)
    return {
        "refracted_angle_deg": refracted,
        "critical_angle_deg": crit,
        "fiber_numerical_aperture": na,
        "acceptance_half_angle_deg": degrees(asin(na)),
    }


def main() -> None:
    d = fiber_optics()
    print(f"air->glass at 30 deg refracts to: {d['refracted_angle_deg']:.1f} deg")
    print(f"glass->air critical angle: {d['critical_angle_deg']:.1f} deg (steeper = trapped)")
    print(
        f"fibre NA: {d['fiber_numerical_aperture']:.2f} "
        f"(acceptance half-angle {d['acceptance_half_angle_deg']:.0f} deg)"
    )


if __name__ == "__main__":
    main()
