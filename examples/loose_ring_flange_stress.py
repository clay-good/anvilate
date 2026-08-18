"""Worked example: the flange is sized by the bolt-up, not by the pressure.

A 200 mm bore loose ring flange — a flat plate ring behind a lap, no hub — sealing a
248 mm gasket reaction diameter at 2 MPa and 400 °C, bolted on a 290 mm circle with 16
M20 studs. The obvious way to pick its thickness is to check it under pressure. Do that
and 30 mm looks comfortable: the operating tangential stress is 115 MPa against a 138
MPa hot allowable, a safety factor of 1.20.

The flange fails anyway, at **0.73**, and the load that breaks it has no pressure in it
at all.

Appendix 2 charges the flange for the *seating* condition using W = (A_m + A_b)·S_a/2,
the mean of the required and the actual bolt area against the ambient allowable. The
joint needs 1,873 mm² of bolt; sixteen M20 studs supply 3,920 mm², because bolts come in
sizes and nobody fits a 2/3-size stud. That surplus is not free margin — it is bolt-up
load the fitter can actually apply, and the Code makes the flange carry it. The seating
moment comes out at 10.5 kN·m against the operating condition's 5.1 kN·m, and even
checked against the *higher* ambient allowable of 172 MPa the seating stress of 235 MPa
loses.

Take it to 40 mm and both conditions pass — seating at 1.30, operating at 2.13. Stress
goes as 1/t², so the 33% thicker ring is 1.78× stronger, and it is the condition nobody
computed that decided the thickness.

Two things worth keeping:

* **Over-bolting is a flange load.** Choosing bolts by rounding up the required area is
  correct for the bolts and pushes the flange the wrong way. The gap between A_m and
  A_b lands directly in the seating moment.
* **The governing condition is not decided by the moments.** They are checked against
  different allowables, so a bigger moment can still lose. Here it does not, but on a
  cold joint where S_a = S_b the ordering can flip either way.

Screening scope, not Code design: this is Appendix 2-7(b), the loose-type-without-hub
case where S_H and S_R are zero by definition and the tangential stress is the whole
check. A welding-neck or any hub-credited flange is **not** covered — its moment arms
come off the hub and its stresses need the F, V and f figures. The bolt-spacing
correction B_sc and the Appendix 2 rigidity index are also out of scope, and a flange
can fail either while its stresses pass.

Run it directly (``python examples/loose_ring_flange_stress.py``);
:func:`screen_flange` is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    asme_appendix_2_flange_moments,
    asme_appendix_2_flange_stress_scorecard,
    asme_appendix_2_gasket_geometry,
    asme_appendix_2_required_bolt_area,
    asme_appendix_2_ring_flange_stress,
    gasket_operating_load,
    gasket_seating_load,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

PRESSURE = Quantity.parse("2 MPa")
BORE = Quantity.parse("200 mm")  # B
BOLT_CIRCLE = Quantity.parse("290 mm")  # C
FLANGE_OD = Quantity.parse("330 mm")  # A, so K = 1.65

GASKET_OD = Quantity.parse("260 mm")
GASKET_CONTACT_WIDTH = Quantity.parse("12 mm")
GASKET_M = 3.0  # spiral wound, ASME Table 2-5.1, user-supplied
GASKET_Y = Quantity.parse("68.9 MPa")

BOLT_ALLOWABLE_AMBIENT = Quantity.parse("172 MPa")  # S_a, SA-193-B7 cold
BOLT_ALLOWABLE_HOT = Quantity.parse("138 MPa")  # S_b, at 400 degC
BOLT_COUNT = 16
BOLT_ROOT_AREA = Quantity.parse("245 mm**2")  # M20, user-supplied

FLANGE_ALLOWABLE_HOT = Quantity.parse("138 MPa")  # S_f at design temperature
FLANGE_ALLOWABLE_AMBIENT = Quantity.parse("172 MPa")  # S_f at ambient


def bolt_loads() -> dict[str, Quantity]:
    """The Appendix 2 bolt loads and the flange design bolt load W for seating."""
    gasket = asme_appendix_2_gasket_geometry(
        contact_width=GASKET_CONTACT_WIDTH, outside_diameter=GASKET_OD
    )
    operating = gasket_operating_load(
        gasket_mean_diameter=gasket.diameter,
        effective_seating_width=gasket.effective_width,
        gasket_factor=GASKET_M,
        pressure=PRESSURE,
    )
    seating = gasket_seating_load(
        gasket_mean_diameter=gasket.diameter,
        effective_seating_width=gasket.effective_width,
        seating_stress=GASKET_Y,
    )
    required_area = asme_appendix_2_required_bolt_area(
        operating_bolt_load=operating,
        seating_bolt_load=seating,
        operating_allowable=BOLT_ALLOWABLE_HOT,
        seating_allowable=BOLT_ALLOWABLE_AMBIENT,
    )
    actual_area = Quantity(
        magnitude=BOLT_COUNT * BOLT_ROOT_AREA.to("mm**2").magnitude, unit="mm**2"
    )
    # Appendix 2-5(e): the flange is charged for the over-bolting a fitter can apply,
    # so W uses the MEAN of the required and actual areas, not the required area alone.
    design_load = Quantity(
        magnitude=0.5
        * (required_area.to("mm**2").magnitude + actual_area.to("mm**2").magnitude)
        * BOLT_ALLOWABLE_AMBIENT.to("MPa").magnitude,
        unit="N",
    )
    return {
        "gasket_diameter": gasket.diameter,
        "operating_bolt_load": operating,
        "seating_bolt_load": seating,
        "required_bolt_area": required_area,
        "actual_bolt_area": actual_area,
        "flange_design_bolt_load": design_load,
    }


def screen_flange(thickness: Quantity) -> Scorecard:
    """Screen the ring flange at ``thickness`` in both Appendix 2 conditions."""
    loads = bolt_loads()
    moments = asme_appendix_2_flange_moments(
        inside_diameter=BORE,
        bolt_circle_diameter=BOLT_CIRCLE,
        gasket_diameter=loads["gasket_diameter"],
        pressure=PRESSURE,
        operating_bolt_load=loads["operating_bolt_load"],
        seating_bolt_load=loads["flange_design_bolt_load"],
    )
    stress = asme_appendix_2_ring_flange_stress(
        outside_diameter=FLANGE_OD,
        inside_diameter=BORE,
        thickness=thickness,
        moments=moments,
        operating_allowable=FLANGE_ALLOWABLE_HOT,
        seating_allowable=FLANGE_ALLOWABLE_AMBIENT,
    )
    return Scorecard(
        entries=(asme_appendix_2_flange_stress_scorecard("ring flange", stress=stress),)
    )


def main() -> None:
    loads = bolt_loads()
    required = loads["required_bolt_area"].to("mm**2").magnitude
    actual = loads["actual_bolt_area"].to("mm**2").magnitude
    print(
        f"bolts: {required:.0f} mm² required, {actual:.0f} mm² fitted "
        f"({BOLT_COUNT}x M20) — {actual / required:.2f}x"
    )
    print(
        f"flange design bolt load for seating W = (A_m + A_b)·S_a/2 = "
        f"{loads['flange_design_bolt_load'].to('kN').magnitude:.0f} kN"
    )
    for thickness in (Quantity.parse("30 mm"), Quantity.parse("40 mm")):
        card = screen_flange(thickness)
        entry = card.entries[0]
        print(f"\n  {thickness.to('mm').magnitude:.0f} mm ring -> {card.status.value}")
        print(f"    {entry.detail}")
        print(f"    safety factor {entry.safety_factor:.2f}")


if __name__ == "__main__":
    main()
