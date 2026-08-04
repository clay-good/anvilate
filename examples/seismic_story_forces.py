"""Worked example: where an earthquake's force actually lands on a building.

The equivalent lateral force method finds a single base shear for a building, but a designer needs
to know how that total is shared over the height — because the floors do not feel it equally. ASCE 7
distributes it by Fx = V·wx·hx^k/Σ(wi·hi^k): each level's share rises with its weight and, more
sharply, with its height above the base. The upper floors, swinging through the largest arc, take
the most.

This example runs the whole seismic load path on a 4-story building of 2,500 kN per floor: the
response coefficient (SDS = 1.0 g on a moderately ductile R = 6 frame), the base shear it draws from
the 10,000 kN total, and the vertical distribution of that shear to each floor. With short-period
exponent k = 1 the roof force is already several times the first-floor force; bump the building to a
long-period k = 2 and the distribution tips even more sharply toward the top. The lesson is that
seismic force is a height game — the roof and the upper stories carry the brunt, which is why the
top of a building, not its base, is often where the lateral system is worked hardest.

Run it directly (``python examples/seismic_story_forces.py``);
:func:`story_forces` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    seismic_base_shear,
    seismic_response_coefficient,
    seismic_vertical_force_distribution,
)
from anvilate.units import Quantity

STORY_WEIGHT = Quantity.parse("2500 kN")
STORY_HEIGHTS = [Quantity.parse(f"{4 * n} m") for n in (1, 2, 3, 4)]
TOTAL_WEIGHT = Quantity.parse("10000 kN")
DESIGN_SPECTRAL_ACCELERATION = 1.0  # SDS, g
RESPONSE_MODIFICATION = 6.0


def story_forces() -> dict[str, float]:
    """Return the base shear and the per-floor seismic forces (kN) at k = 1 and k = 2."""
    cs = seismic_response_coefficient(
        design_spectral_acceleration=DESIGN_SPECTRAL_ACCELERATION,
        response_modification_factor=RESPONSE_MODIFICATION,
    )
    base = seismic_base_shear(seismic_weight=TOTAL_WEIGHT, response_coefficient=cs)
    weights = [STORY_WEIGHT] * len(STORY_HEIGHTS)

    def forces(k: float) -> list[float]:
        dist = seismic_vertical_force_distribution(
            base_shear=base,
            story_weights=weights,
            story_heights=STORY_HEIGHTS,
            distribution_exponent=k,
        )
        return [f.to("kN").magnitude for f in dist]

    return {
        "base_shear_kn": base.to("kN").magnitude,
        "k1_forces": forces(1.0),
        "k2_forces": forces(2.0),
    }


def main() -> None:
    s = story_forces()
    print(f"base shear : {s['base_shear_kn']:.0f} kN")
    print("floor forces (kN), base -> roof:")
    print(f"  k=1 (short period): {[round(f) for f in s['k1_forces']]}")
    print(f"  k=2 (long period) : {[round(f) for f in s['k2_forces']]}")
    print("  -> seismic force is a height game; the upper stories take the brunt")


if __name__ == "__main__":
    main()
