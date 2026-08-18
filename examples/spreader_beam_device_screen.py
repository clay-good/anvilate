"""Worked example: the eight kilonewtons that were never in the load case.

A 4 m spreader beam rated for 100 kN, fabricated from A36 (S_y 250, S_u 400 MPa), with
a 17 mm upper bail plate — 180 mm wide, 60 mm pin hole. Category B, because it leaves
the bay it was designed for. Service Class 2, because it will see a few hundred thousand
picks.

Screen the bail against the **rated** load and it passes: pin bearing at 98.0 MPa
against BTH-1's F_p = 1.25·S_y/N_d = 104.2 MPa, a safety factor of 1.06. Thin, but a
pass.

The beam weighs 8 kN, and the crane hook carries that too. BTH-1 §3-1.2 has the design
consider the device's own weight alongside the rated load, so the bail — which is the
*upper* attachment, the one the hook pulls on — sees 108 kN, not 100. At 108 kN the same
plate is at 105.9 MPa and the check **fails at 0.98**.

Eight percent more load turned a pass into a fail because the margin was 6% to begin
with. That is the whole point of the example: the omission is small, and the margin it
has to survive is smaller.

Two more things the screen makes visible:

* **`self_weight` has no default.** A designer who has established it as negligible
  passes zero deliberately and that shows on the card. There is no way to *forget* it,
  which is the single most common omission in lifter design.
* **The self weight stops at the upper attachment.** A lower lug, below the pickup
  point, carries the rated load alone. `design_load` is documented for the top of the
  device and this example applies it only there.

And the category is not a detail: the same bail at the same 108 kN passes comfortably at
**1.48** as Category A, where N_d = 2.00. Nothing in the geometry says which category
applies — it is a judgement about supervision, environment and load predictability, and
it moves every allowable by 50%. That is why it is a typed input that travels into every
entry's detail rather than a bare safety factor.

The card as a whole comes back FAIL here, on the bail — but note the fatigue entry:
a Class 2 device with no cycle data has not been fatigue-screened, so with the bail
fixed the card would still not read PASS. Only Class 0 is exempt, and NOT_EVALUATED is
not a pass.

Screening scope, not stamped design: BTH-1 §3-2/§3-3 allowable stresses on stresses the
caller computed, plus the §3-1.4 fatigue obligation. There is no lateral-torsional
buckling check, no weld or bolt design, no impact or dynamic load factor, and no
fabrication, marking or proof-test requirement. A green card here is a screen, not a
lifter you may hang a load from.

Run it directly (``python examples/spreader_beam_device_screen.py``);
:func:`screen_bail` is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    BTH1LimitState,
    DesignCategory,
    LifterDevice,
    LifterMemberStress,
    LifterPinPlate,
    ServiceClass,
    bth1_allowable_stresses,
    bth1_pin_plate_scorecard,
    screen_lifter_device,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

YIELD = Quantity.parse("250 MPa")  # A36, user-supplied
ULTIMATE = Quantity.parse("400 MPa")

RATED_LOAD = Quantity.parse("100 kN")
SELF_WEIGHT = Quantity.parse("8 kN")

BAIL_WIDTH = Quantity.parse("180 mm")
BAIL_HOLE = Quantity.parse("60 mm")
BAIL_THICKNESS = Quantity.parse("17 mm")

BEAM_BENDING_STRESS = Quantity.parse("70 MPa")  # from the beam analysis, user-supplied


def device(category: DesignCategory = DesignCategory.B) -> LifterDevice:
    """The spreader beam as a typed BTH-1 device."""
    return LifterDevice(
        name="4 m spreader beam",
        rated_load=RATED_LOAD,
        self_weight=SELF_WEIGHT,
        category=category,
        service_class=ServiceClass.CLASS_2,
    )


def screen_bail(load: Quantity, *, category: DesignCategory = DesignCategory.B):
    """Screen the upper bail plate at ``load`` — the two BTH-1 pin-plate limit states."""
    allowables = bth1_allowable_stresses(
        yield_strength=YIELD, ultimate_strength=ULTIMATE, category=category
    )
    plate = LifterPinPlate(
        name="upper bail",
        width=BAIL_WIDTH,
        hole_diameter=BAIL_HOLE,
        thickness=BAIL_THICKNESS,
        load=load,
    )
    return Scorecard(entries=bth1_pin_plate_scorecard(plate, allowables=allowables))


def screen_device() -> Scorecard:
    """The whole device: the beam in bending, the bail on the design load, and fatigue."""
    lifter = device()
    allowables = bth1_allowable_stresses(
        yield_strength=YIELD, ultimate_strength=ULTIMATE, category=lifter.category
    )
    return Scorecard(
        entries=screen_lifter_device(
            lifter,
            allowables=allowables,
            members=(
                LifterMemberStress(
                    name="beam bending",
                    stress=BEAM_BENDING_STRESS,
                    limit_state=BTH1LimitState.BENDING,
                ),
            ),
            # The bail is the UPPER attachment, so it carries the device's weight too.
            pin_plates=(
                LifterPinPlate(
                    name="upper bail",
                    width=BAIL_WIDTH,
                    hole_diameter=BAIL_HOLE,
                    thickness=BAIL_THICKNESS,
                    load=lifter.design_load,
                ),
            ),
        )
    )


def main() -> None:
    lifter = device()
    print(f"{lifter}")
    print(
        f"design load at the upper attachment: "
        f"{lifter.design_load.to('kN').magnitude:.0f} kN "
        f"({RATED_LOAD.to('kN').magnitude:.0f} rated + "
        f"{SELF_WEIGHT.to('kN').magnitude:.0f} self weight)"
    )
    for label, load in (
        ("rated load only", RATED_LOAD),
        ("rated + self weight", lifter.design_load),
    ):
        card = screen_bail(load)
        bearing = card.entries[1]
        print(
            f"\n  bail on {label:<20} ({load.to('kN').magnitude:.0f} kN) -> "
            f"{bearing.status.value.upper()} at SF {bearing.safety_factor:.2f}"
        )
    as_a = screen_bail(lifter.design_load, category=DesignCategory.A).entries[1]
    print(
        f"\n  the same 108 kN bail as Category A -> {as_a.status.value.upper()} at SF "
        f"{as_a.safety_factor:.2f} (N_d = 2.00 instead of 3.00)"
    )

    card = screen_device()
    print(f"\n  whole device -> {card.status.value}")
    for entry in card.entries:
        factor = "  —  " if entry.safety_factor is None else f"{entry.safety_factor:.2f}"
        print(f"    {entry.name:<28} {entry.status.value:<14} SF {factor}")


if __name__ == "__main__":
    main()
