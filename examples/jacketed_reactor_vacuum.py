"""Worked example: the pressure vessel that was really sized by vacuum.

A jacketed reactor shell, 1 m in diameter, runs at 4 bar internal pressure. As a
pressure vessel it is easy: even a thin 3 mm wall carries the 67 MPa hoop stress
against a 138 MPa allowable with a 2.07 margin, and thicker walls only add margin.
Judged on the pressure it is named for, the vessel is done.

It is not, because the shell sees a second load its nameplate ignores. When the
steam heating jacket is shut off and the sealed reactor cools, the vapour inside
condenses and pulls a partial vacuum — roughly one atmosphere of *external*
pressure. A thin shell does not yield under external pressure, it buckles, and the
collapse pressure goes as the cube of the wall-to-radius ratio. The 3 mm wall
buckles at 0.012 MPa, a twenty-fifth of the 0.1 MPa vacuum (a 0.04 margin against
the 3x the code wants); even 6 mm reaches only 0.095 MPa (0.32). It takes a 12 mm
wall — four times what the internal pressure alone would call for — before the
shell survives the vacuum with margin (2.53).

Every check clears the internal pressure; only the vacuum governs. A vessel that
can pull a vacuum must be designed for the vacuum, and it is routinely the buckling
case, not the pressure case, that sets the wall. The allowable and modulus are
material data, declared inline like any allowable.

Run it directly (``python examples/jacketed_reactor_vacuum.py``);
:func:`screen_reactor_shell` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import cylinder_external_pressure_buckling, thin_wall_cylinder
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

MEAN_RADIUS = Quantity.parse("500 mm")
INTERNAL_PRESSURE = Quantity.parse("0.4 MPa")  # 4 bar operating
HOOP_ALLOWABLE = Quantity.parse("138 MPa")
VACUUM = Quantity.parse("0.1 MPa")  # one atmosphere external on cooldown
VACUUM_SAFETY_FACTOR = 3.0
ELASTIC_MODULUS = Quantity.parse("200 GPa")

WALL_THICKNESSES = {
    "3 mm wall": Quantity.parse("3 mm"),
    "6 mm wall": Quantity.parse("6 mm"),
    "12 mm wall": Quantity.parse("12 mm"),
}


def screen_reactor_shell() -> Scorecard:
    """Screen each wall for BOTH the internal-pressure hoop stress and the
    external-vacuum buckling collapse."""
    allowable = HOOP_ALLOWABLE.to("MPa").magnitude
    vacuum = VACUUM.to("MPa").magnitude
    entries = []
    for name, thickness in WALL_THICKNESSES.items():
        hoop = thin_wall_cylinder(
            pressure=INTERNAL_PRESSURE, radius=MEAN_RADIUS, wall_thickness=thickness
        ).hoop_stress
        collapse = cylinder_external_pressure_buckling(
            elastic_modulus=ELASTIC_MODULUS, wall_thickness=thickness, mean_radius=MEAN_RADIUS
        )
        entries.append(
            ScorecardEntry.from_safety_factor(
                f"{name}: internal pressure (hoop)",
                computed=allowable / hoop.to("MPa").magnitude,
                required=1.0,
            )
        )
        entries.append(
            ScorecardEntry.from_safety_factor(
                f"{name}: external vacuum (buckling)",
                computed=collapse.to("MPa").magnitude / (vacuum * VACUUM_SAFETY_FACTOR),
                required=1.0,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, thickness in WALL_THICKNESSES.items():
        collapse = cylinder_external_pressure_buckling(
            elastic_modulus=ELASTIC_MODULUS, wall_thickness=thickness, mean_radius=MEAN_RADIUS
        )
        print(f"{name}: vacuum collapse pressure {collapse.to('MPa').magnitude:.4f} MPa")
    print(screen_reactor_shell())


if __name__ == "__main__":
    main()
