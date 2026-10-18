"""Worked example: a short Z stiffener whose elastic buckling stress is a fiction.

A formed aluminium Z stiffener, 1.6 mm thick with a 30 mm web and two 15 mm flanges
(96 mm²), is short enough not to buckle as a column. Its web, treated as a long plate
simply supported at the corners (k = 4), has an elastic local buckling stress of
760.3 MPa, above the material's 320 MPa F_0.7, where the material is far softer than
E says. The Astronautic Structures Manual's plasticity reduction, with the web's edges
rotationally restrained, brings it down to 335.2 MPa.

A section this stocky is past Gerard's crippling correlation: the screen refuses it and
names NACA TN 3784 eq. 73, under which the section cripples at its elements' local buckling
stress. That stress is the plasticity-reduced one, so the crippling stress is 335.2 MPa,
0.97 of the 345 MPa compressive yield. A thinner 1.0 mm stiffener of the same
proportions is inside the correlation, which gives 243.6 MPa directly.

Used unreduced, the elastic figure would have overstated the stocky stiffener's strength
2.27 times.

Material values are illustrative (E 72.4 GPa, F_0.7 320 MPa, F_0.85 300 MPa, compressive
yield 345 MPa), not allowables.

Run it directly (``python examples/short_stiffener_plasticity.py``);
:func:`short_stiffener_plasticity` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import (
    CripplingSection,
    PlateEdge,
    RambergOsgood,
    gerard_crippling_stress,
    plastic_plate_buckling_stress,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

E_MPA, POISSON = 72_400.0, 0.33
THICKNESS, WEB = 1.6, 30.0


def short_stiffener_plasticity() -> dict[str, float | str]:
    """Return the elastic, plasticity-reduced and crippling stresses, and the source."""
    curve = RambergOsgood.from_secant_points(
        elastic_modulus=Quantity(magnitude=E_MPA, unit="MPa"),
        f_07=Quantity(magnitude=320.0, unit="MPa"),
        f_085=Quantity(magnitude=300.0, unit="MPa"),
    )
    elastic = 4 * pi**2 * E_MPA / (12 * (1 - POISSON**2)) * (THICKNESS / WEB) ** 2
    plastic = plastic_plate_buckling_stress(
        curve=curve,
        elastic_stress=Quantity(magnitude=elastic, unit="MPa"),
        edge=PlateEdge.ROTATIONALLY_RESTRAINED,
        poisson=POISSON,
    ).stress
    try:
        crippling = _crippling(THICKNESS, 96.0)
        source = "Gerard's correlation"
    except RefusalError:
        # NACA TN 3784 eq. 73: above the cutoff the section cripples at local buckling
        crippling, source = plastic, "local buckling (NACA TN 3784 eq. 73)"
    return {
        "elastic_mpa": elastic,
        "plastic_mpa": plastic,
        "crippling_mpa": crippling,
        "crippling_source": source,
        "fraction_of_yield": crippling / 345.0,
        "overstatement": elastic / crippling,
        "crippling_thin_mpa": _crippling(1.0, 60.0),
    }


def _crippling(thickness: float, area: float) -> float:
    return gerard_crippling_stress(
        section=CripplingSection.FORMED_TWO_CORNER,
        thickness=Quantity(magnitude=thickness, unit="mm"),
        area=Quantity(magnitude=area, unit="mm**2"),
        compressive_yield=Quantity(magnitude=345.0, unit="MPa"),
        elastic_modulus=Quantity(magnitude=E_MPA, unit="MPa"),
        count=2,
        corner_yield_ratio=1.25,
        web_width=Quantity(magnitude=WEB, unit="mm"),
    ).stress


def main() -> None:
    d = short_stiffener_plasticity()
    print(f"elastic local buckling: {d['elastic_mpa']:.1f} MPa")
    print(f"plasticity-reduced: {d['plastic_mpa']:.1f} MPa")
    print(f"crippling: {d['crippling_mpa']:.1f} MPa, by {d['crippling_source']}")
    print(f"that is {d['fraction_of_yield']:.2f} of yield")
    print(f"the elastic figure overstates it {d['overstatement']:.2f} times")
    print(f"a 1.0 mm stiffener cripples at {d['crippling_thin_mpa']:.1f} MPa")


if __name__ == "__main__":
    main()
