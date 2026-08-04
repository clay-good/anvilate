"""Worked example: the soft story where gravity quietly worsens the earthquake.

A story that sways under an earthquake also carries the weight of everything above it, and that
weight, riding along the sway, adds an overturning demand the first-order forces never showed — the
P-delta effect. ASCE 7 measures it with the stability coefficient θ = Pₓ·Δ/(Vₓ·hsx·Cd) and sorts
stories into three bins: below 0.10 the effect is negligible and ignored; between 0.10 and the
ceiling θ_max the drift and forces must be amplified by 1/(1 − θ); above θ_max the story is unstable
and has to be stiffened.

This example compares two stories of the same braced frame (Cd = 4, so θ_max = 0.125). A stiff lower
story — light drift, high shear — comes out at θ = 0.02, comfortably in the ignore-it bin. A soft,
heavily-loaded upper story, drifting 80 mm while carrying 11,000 kN on only 500 kN of shear, reaches
θ = 0.11: still under the θ_max ceiling, so it is stable, but now over the 0.10 line, so its drift
and member forces must be scaled up about 12% before anything else is checked. The lesson is that
P-delta is not a fringe case for tall soft stories: the same sway that passes a first-order drift
check can carry a gravity load large enough to demand a second-order amplification, and the
stability coefficient is what tells you which bin a story falls in.

Run it directly (``python examples/seismic_p_delta_stability.py``);
:func:`stability_check` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    seismic_stability_coefficient,
    seismic_stability_coefficient_limit,
)
from anvilate.units import Quantity

DEFLECTION_AMPLIFICATION = 4.0  # Cd, braced frame
STORY_HEIGHT = Quantity.parse("4 m")


def stability_check() -> dict[str, float]:
    """Return the stability coefficients of a stiff and a soft story, and the ceiling."""
    stiff = seismic_stability_coefficient(
        story_gravity_load=Quantity.parse("6000 kN"),
        design_story_drift=Quantity.parse("40 mm"),
        story_shear=Quantity.parse("800 kN"),
        story_height=STORY_HEIGHT,
        deflection_amplification_factor=DEFLECTION_AMPLIFICATION,
    )
    soft = seismic_stability_coefficient(
        story_gravity_load=Quantity.parse("11000 kN"),
        design_story_drift=Quantity.parse("80 mm"),
        story_shear=Quantity.parse("500 kN"),
        story_height=STORY_HEIGHT,
        deflection_amplification_factor=DEFLECTION_AMPLIFICATION,
    )
    theta_max = seismic_stability_coefficient_limit(
        deflection_amplification_factor=DEFLECTION_AMPLIFICATION
    )
    return {"stiff_theta": stiff, "soft_theta": soft, "theta_max": theta_max}


def _verdict(theta: float, theta_max: float) -> str:
    if theta > theta_max:
        return "unstable, stiffen"
    if theta >= 0.10:
        return f"amplify by {1.0 / (1.0 - theta):.2f}"
    return "P-delta negligible"


def main() -> None:
    s = stability_check()
    tmax = s["theta_max"]
    print(f"stability ceiling theta_max : {tmax:.3f}")
    print(
        f"stiff lower story : theta = {s['stiff_theta']:.3f} ({_verdict(s['stiff_theta'], tmax)})"
    )
    print(f"soft upper story  : theta = {s['soft_theta']:.3f} ({_verdict(s['soft_theta'], tmax)})")
    print("  -> the soft story is stable but must carry a second-order amplification")


if __name__ == "__main__":
    main()
