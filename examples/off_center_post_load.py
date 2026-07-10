"""Worked example: the eccentric column feeds back on itself.

A 20 × 30 mm A36 support strut, 1.2 m between pinned ends, carries 37 kN
whose bearing pad sits 5 mm off the centroid. The naive combined-stress
check — P/A + P·e·c/I, superposition with no feedback — reads 123.4 MPa and
passes SF 2.03. But the eccentric load bows the strut, the bow adds moment
arm, and the extra moment bows it further: at 60% of the Euler load that
P-δ feedback amplifies the bending term by sec((L/2r)·√(P/EA)) = 2.88. The
exact secant formula (verified in the test suite against an independent
finite-difference beam-column solve) puts the true peak at 239.6 MPa —
SF 1.04, a strut one dent away from buckling that superposition called
comfortably safe. Slender + eccentric is a feedback problem, not an
addition problem.

Run it directly (``python examples/off_center_post_load.py``);
:func:`screen_off_center_post` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    combine_axial_bending,
    secant_column_max_stress,
    strength_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

LOAD = Quantity.parse("37 kN")
ECCENTRICITY = Quantity.parse("5 mm")
AREA = Quantity.parse("600 mm**2")  # 20 x 30 bar
SECOND_MOMENT = Quantity.parse("45000 mm**4")  # about the bending axis
EXTREME_FIBER = Quantity.parse("15 mm")
LENGTH = Quantity.parse("1.2 m")
STEEL = "ASTM-A36"
REQUIRED_SF = 2.0


def screen_off_center_post() -> Scorecard:
    """Screen the strut by naive superposition and by the exact secant formula."""
    record = default_materials_db().get(STEEL)
    yield_strength = record.yield_strength.quantity

    p = LOAD.to("N").magnitude
    axial = Quantity(magnitude=p / AREA.to("m**2").magnitude / 1e6, unit="MPa")
    moment_stress = (
        p
        * ECCENTRICITY.to("m").magnitude
        * EXTREME_FIBER.to("m").magnitude
        / SECOND_MOMENT.to("m**4").magnitude
        / 1e6
    )
    naive = combine_axial_bending(
        axial_stress=axial, bending_stress=Quantity(magnitude=moment_stress, unit="MPa")
    )
    secant = secant_column_max_stress(
        load=LOAD,
        eccentricity=ECCENTRICITY,
        area=AREA,
        second_moment=SECOND_MOMENT,
        extreme_fiber=EXTREME_FIBER,
        length=LENGTH,
        elastic_modulus=record.elastic_modulus.quantity,
    )

    entries = (
        strength_scorecard(
            "superposition (no P-delta)",
            stress=naive.tension_fibre,
            allowable=yield_strength,
            required=REQUIRED_SF,
        ),
        strength_scorecard(
            "secant formula (exact)",
            stress=secant,
            allowable=yield_strength,
            required=REQUIRED_SF,
        ),
    )
    return Scorecard(entries=entries)


def main() -> None:
    card = screen_off_center_post()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
