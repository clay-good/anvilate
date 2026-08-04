"""Worked example: why a roof is designed for more earthquake force than it receives.

The lateral force an earthquake puts on a floor and the force that floor's *diaphragm* must be
designed for are two different numbers, and at the roof the second is the larger — a result that
catches people out. The vertical-distribution force Fx is what the frame carries away from the
level; the diaphragm force Fpx is what the slab itself must gather and drag to the frame, and
ASCE 7 floors it at 0.2·SDS·Ie·wpx no matter how small the proportional value works out.

This example takes the roof of a four-story building. The seismic analysis gives the roof only a
modest share of the base shear — its proportional diaphragm force works out to 250 kN. But the
0.2·SDS·Ie·wpx floor, on a 2,000 kN roof at SDS = 1.0, is 400 kN, and that governs: the roof
diaphragm is designed for 400 kN, 60% more than the proportional value and more than the story force
it nominally receives. A lower floor, gathering a bigger fraction of the shear from the stories
above, lands between the 0.2 floor and the 0.4 ceiling and takes its proportional value. The lesson
is that diaphragm design is not the same check as the vertical force distribution: the collector and
drag elements at the roof are sized by a lower-bound the story force never sees.

Run it directly (``python examples/seismic_diaphragm_force.py``);
:func:`diaphragm_forces` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import seismic_diaphragm_force
from anvilate.units import Quantity

SDS = 1.0


def diaphragm_forces() -> dict[str, float]:
    """Return the roof and a mid-floor diaphragm forces, and the roof's proportional value."""
    roof = seismic_diaphragm_force(
        story_forces_above=Quantity.parse("1000 kN"),
        story_weights_above=Quantity.parse("8000 kN"),
        diaphragm_weight=Quantity.parse("2000 kN"),
        design_spectral_acceleration=SDS,
    )
    mid = seismic_diaphragm_force(
        story_forces_above=Quantity.parse("3600 kN"),
        story_weights_above=Quantity.parse("12000 kN"),
        diaphragm_weight=Quantity.parse("2000 kN"),
        design_spectral_acceleration=SDS,
    )
    return {
        "roof_proportional_kn": 1000.0 / 8000.0 * 2000.0,
        "roof_fpx_kn": roof.to("kN").magnitude,
        "mid_fpx_kn": mid.to("kN").magnitude,
    }


def main() -> None:
    d = diaphragm_forces()
    print(f"roof proportional (SigmaF/SigmaW * wpx) : {d['roof_proportional_kn']:.0f} kN")
    print(f"roof diaphragm force Fpx (0.2 floor)    : {d['roof_fpx_kn']:.0f} kN (governs)")
    print(f"mid-floor diaphragm force Fpx           : {d['mid_fpx_kn']:.0f} kN (proportional)")
    print("  -> the roof diaphragm is designed for the lower-bound force, above its story force")


if __name__ == "__main__":
    main()
