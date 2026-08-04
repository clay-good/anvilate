"""Worked example: the lopsided building that twists harder than it sways.

An earthquake pushes a building sideways, but if the building's stiffness is not centered — a stair
core on one side, a wall of glass on the other — it also *twists*, and the far corner rides through
a bigger arc than the near one. ASCE 7 handles this two ways at once. Even a perfectly symmetric
building is designed for an accidental torsion, the story shear acting at a 5% eccentricity,
Mta = Vx·(0.05·L). And when the building is genuinely torsionally irregular, that accidental torsion
is amplified by Ax = (δmax/(1.2·δavg))², bounded between 1 and 3.

This example takes a 30 m-wide building carrying 800 kN of story shear. Run it as symmetric — both
ends deflect the same — and Ax is 1.0, giving a baseline accidental torsion of 1,200 kN·m. Now make
it lopsided: the far corner deflects 18 mm while the two-end average is 12 mm. The amplification
climbs to Ax = 1.56, and the design torsional moment rises to about 1,875 kN·m — half again as much,
all of it landing on the flexible side that was already deflecting the most. The lesson is that
torsional irregularity is self-reinforcing: the soft edge draws the extra force, and Ax is
how the code makes the design chase it rather than ignore it.

Run it directly (``python examples/seismic_accidental_torsion.py``);
:func:`torsional_moments` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    seismic_accidental_torsional_moment,
    seismic_torsional_amplification_factor,
)
from anvilate.units import Quantity

STORY_SHEAR = Quantity.parse("800 kN")
BUILDING_WIDTH = Quantity.parse("30 m")


def torsional_moments() -> dict[str, float]:
    """Return the symmetric and irregular accidental torsional moments and the amplifier."""
    symmetric = seismic_accidental_torsional_moment(
        story_shear=STORY_SHEAR, building_dimension=BUILDING_WIDTH
    )
    ax = seismic_torsional_amplification_factor(
        maximum_displacement=Quantity.parse("18 mm"),
        average_displacement=Quantity.parse("12 mm"),
    )
    irregular = seismic_accidental_torsional_moment(
        story_shear=STORY_SHEAR, building_dimension=BUILDING_WIDTH, amplification_factor=ax
    )
    return {
        "amplification": ax,
        "symmetric_knm": symmetric.to("kN*m").magnitude,
        "irregular_knm": irregular.to("kN*m").magnitude,
    }


def main() -> None:
    t = torsional_moments()
    print(f"symmetric building (Ax=1.0) : {t['symmetric_knm']:.0f} kN.m accidental torsion")
    print(f"torsional amplification Ax : {t['amplification']:.2f}")
    print(f"irregular building : {t['irregular_knm']:.0f} kN.m (Ax applied)")
    print("  -> the soft edge draws the extra torsion; Ax makes the design chase it")


if __name__ == "__main__":
    main()
