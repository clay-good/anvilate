"""Worked example: the wall passes and the hole in it does not.

An 800 mm ID shell at 2 MPa in SA-516-70 (S = 138 MPa, E = 1.0 seamless) needs
5.85 mm of wall for pressure. UG-37 asks a different question from UG-27 — not "is
the wall thick enough" but "has the metal the hole removed been put back nearby" —
and the two answers come apart as soon as the wall is trimmed toward its minimum.

The same vessel at two shell thicknesses:

* **Built at 14 mm.** Shell SF 2.14, 2:1 ellipsoidal head SF 2.15, and the 6-inch
  nozzle opening SF 1.66. Everything passes. The opening is carried by the shell's
  own surplus wall, which is what UG-37 credits as A_1.
* **Built at 8 mm.** The shell still passes at SF 1.11 and the head at 1.12 — the
  wall is genuinely adequate for pressure. The opening fails at **0.49**, less than
  half the area it needs, because the surplus that was reinforcing it is gone. The
  shell got 1.9x thinner and the opening got 3.4x worse: reinforcement depends on
  the wall's *excess*, not its thickness, and excess falls away much faster.

That is the whole lesson. A vessel trimmed to its pressure minimum has no
reinforcement left over, and the component that fails first is the one nobody
re-checked.

The flange is screened separately, and makes a second point. 12 mm of spiral-wound
gasket contact on a 320 mm OD gives b_0 = 6 mm, inside Appendix 2's ¼-inch limit, so
b = b_0 and G is the mean diameter. The seating load is 400.0 kN and the operating
load only 218.7 kN: this joint is **seating**-governed, not pressure-governed. A
designer who sized the bolts on pressure alone would undersize them by nearly half,
and nothing about the pressure says so.

Screening scope, not Code design: this is UG-27/UG-32/UG-37 and the Appendix 2 bolt
loads. It is not a U-stamp calculation. There is no flange stress analysis, no MDMT
or impact-test assessment, no external-pressure or nozzle-load check, and no
fabrication or NDE requirements. A green scorecard here means the pressure
arithmetic screens clean; it does not mean the vessel is Code-compliant.

Run it directly (``python examples/pressure_vessel_nozzle_and_flange.py``);
:func:`screen_vessel` is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    asme_appendix_2_gasket_geometry,
    asme_appendix_2_required_bolt_area,
    asme_cylinder_thickness,
    asme_ellipsoidal_head_thickness,
    asme_ug37_nozzle_reinforcement,
    asme_ug37_reinforcement_scorecard,
    gasket_operating_load,
    gasket_seating_load,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

PRESSURE = Quantity.parse("2 MPa")
INSIDE_RADIUS = Quantity.parse("400 mm")
ALLOWABLE = Quantity.parse("138 MPa")  # SA-516-70 at design temperature, user-supplied
JOINT_EFFICIENCY = 1.0
CORROSION = Quantity.parse("1.5 mm")
SHELL_THICKNESS = Quantity.parse("14 mm")

NOZZLE_OD = Quantity.parse("168.3 mm")  # 6 in NPS
NOZZLE_WALL = Quantity.parse("10.97 mm")  # Schedule 80
NOZZLE_REQUIRED_WALL = Quantity.parse("1.22 mm")  # its own UG-27 wall at this pressure
WELD_LEG = Quantity.parse("8 mm")

GASKET_OD = Quantity.parse("320 mm")
GASKET_CONTACT_WIDTH = Quantity.parse("12 mm")
GASKET_M = 3.0  # spiral wound, ASME Table 2-5.1, user-supplied
GASKET_Y = Quantity.parse("68.9 MPa")
BOLT_ALLOWABLE_HOT = Quantity.parse("138 MPa")
BOLT_ALLOWABLE_AMBIENT = Quantity.parse("138 MPa")


def shell_required_thickness() -> Quantity:
    """The UG-27 pressure-design wall of the shell, before corrosion allowance."""
    return asme_cylinder_thickness(
        pressure=PRESSURE,
        radius=INSIDE_RADIUS,
        allowable_stress=ALLOWABLE,
        joint_efficiency=JOINT_EFFICIENCY,
    )


def nozzle_reinforcement(shell_thickness: Quantity):
    """The UG-37 area accounting for the 6-inch opening at a given shell thickness."""
    return asme_ug37_nozzle_reinforcement(
        shell_thickness=shell_thickness,
        shell_required_thickness=shell_required_thickness(),
        nozzle_outside_diameter=NOZZLE_OD,
        nozzle_thickness=NOZZLE_WALL,
        nozzle_required_thickness=NOZZLE_REQUIRED_WALL,
        corrosion_allowance=CORROSION,
        weld_leg=WELD_LEG,
    )


def flange_bolt_area() -> tuple[Quantity, Quantity, Quantity]:
    """The Appendix 2 seating load, operating load, and required bolt area."""
    geometry = asme_appendix_2_gasket_geometry(
        contact_width=GASKET_CONTACT_WIDTH, outside_diameter=GASKET_OD
    )
    seating = gasket_seating_load(
        gasket_mean_diameter=geometry.diameter,
        effective_seating_width=geometry.effective_width,
        seating_stress=GASKET_Y,
    )
    operating = gasket_operating_load(
        gasket_mean_diameter=geometry.diameter,
        effective_seating_width=geometry.effective_width,
        gasket_factor=GASKET_M,
        pressure=PRESSURE,
    )
    area = asme_appendix_2_required_bolt_area(
        operating_bolt_load=operating,
        seating_bolt_load=seating,
        operating_allowable=BOLT_ALLOWABLE_HOT,
        seating_allowable=BOLT_ALLOWABLE_AMBIENT,
    )
    return seating, operating, area


def screen_vessel(shell_thickness: Quantity = SHELL_THICKNESS) -> Scorecard:
    """Screen the shell, the head and the nozzle opening at one shell thickness."""
    required = shell_required_thickness()
    available = Quantity(
        magnitude=shell_thickness.to("mm").magnitude - CORROSION.to("mm").magnitude, unit="mm"
    )
    head_required = asme_ellipsoidal_head_thickness(
        pressure=PRESSURE,
        diameter=Quantity(magnitude=2 * INSIDE_RADIUS.to("mm").magnitude, unit="mm"),
        allowable_stress=ALLOWABLE,
        joint_efficiency=JOINT_EFFICIENCY,
    )

    def wall(label: str, need: Quantity, clause: str) -> ScorecardEntry:
        have = available.to("mm").magnitude
        return ScorecardEntry.from_safety_factor(
            label, computed=have / need.to("mm").magnitude, required=1.0
        ).model_copy(
            update={
                "detail": (
                    f"{have:.2f} mm of corroded wall against a required "
                    f"{need.to('mm').magnitude:.2f} mm"
                ),
                "reference": clause,
            }
        )

    entries: list[ScorecardEntry] = [
        wall("shell wall (UG-27)", required, "ASME VIII Div 1 UG-27"),
        wall("2:1 ellipsoidal head (UG-32)", head_required, "ASME VIII Div 1 UG-32"),
        asme_ug37_reinforcement_scorecard(
            "6 in nozzle opening", reinforcement=nozzle_reinforcement(shell_thickness)
        ),
    ]
    return Scorecard(entries=entries)


def main() -> None:
    required = shell_required_thickness()
    print(f"shell required wall (UG-27): {required.to('mm').magnitude:.2f} mm")
    for thickness in (SHELL_THICKNESS, Quantity.parse("8 mm")):
        card = screen_vessel(thickness)
        print(f"\n  built at {thickness.to('mm').magnitude:.0f} mm -> {card.status.value}")
        for entry in card.entries:
            factor = "  —  " if entry.safety_factor is None else f"{entry.safety_factor:.2f}"
            print(f"    {entry.name:<30} {entry.status.value:<6} SF {factor}")

    seating, operating, area = flange_bolt_area()
    governs = "seating" if seating.magnitude >= operating.magnitude else "operating"
    print(
        f"\n  flange: seating {seating.to('kN').magnitude:.1f} kN, operating "
        f"{operating.to('kN').magnitude:.1f} kN — {governs} governs"
    )
    print(f"  required bolt area: {area.to('mm**2').magnitude:.0f} mm²")


if __name__ == "__main__":
    main()
