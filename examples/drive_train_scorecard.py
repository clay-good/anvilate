"""Worked example: the shaft passes, and the drive train does not.

A shaft's own card says nothing about the key that drives it or the bearings that hold it.
This example screens all three parts of one 40 mm drive: the shaft PASSES every one of
its three limits, its key is over on side bearing at 0.36, and its bearing reaches
8,084 hours against the 20,000 the application asks for. Each failing check names the
parameter that clears its own limit — a longer key, a bigger catalogue rating — and none of
them is the shaft diameter.

Run it directly (``python examples/drive_train_scorecard.py``);
:func:`drive_train` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.machinery import (
    RollingBearing,
    ShaftKey,
    TransmissionShaft,
    screen_rolling_bearing,
    screen_shaft,
    screen_shaft_key,
)
from anvilate.units import Quantity


def drive_train() -> dict[str, object]:
    """Screen the shaft, its key and its bearing, and return what each card found."""
    shaft = TransmissionShaft(
        diameter=Quantity.parse("40 mm"),
        bending_moment=Quantity.parse("250 N*m"),
        torque=Quantity.parse("400 N*m"),
        yield_strength=Quantity.parse("370 MPa"),
        length=Quantity.parse("200 mm"),
        shear_modulus=Quantity.parse("79.3 GPa"),
        allowable_twist=Quantity.parse("0.5 degree"),
        endurance_limit=Quantity.parse("200 MPa"),
        ultimate_strength=Quantity.parse("690 MPa"),
    )
    key = ShaftKey(
        shaft_diameter=Quantity.parse("40 mm"),
        key_width=Quantity.parse("12 mm"),
        key_height=Quantity.parse("8 mm"),
        key_length=Quantity.parse("10 mm"),
        torque=Quantity.parse("400 N*m"),
        allowable_shear=Quantity.parse("100 MPa"),
        allowable_bearing=Quantity.parse("180 MPa"),
    )
    unit = RollingBearing(
        dynamic_load_rating=Quantity.parse("35.1 kN"),
        static_load_rating=Quantity.parse("19.3 kN"),
        radial_load=Quantity.parse("4.2 kN"),
        axial_load=Quantity.parse("1.1 kN"),
        radial_factor=0.56,
        axial_factor=1.45,
        speed=Quantity.parse("1450 rpm"),
        required_life_hours=Quantity.parse("20000 hour"),
        required_static_factor=1.5,
    )
    cards = {
        "shaft": screen_shaft(shaft),
        "key": screen_shaft_key(key),
        "bearing": screen_rolling_bearing(unit),
    }
    return {
        "statuses": {part: card.status.value for part, card in cards.items()},
        "factors": {
            entry.name: round(entry.safety_factor, 2)
            for card in cards.values()
            for entry in card.entries
            if entry.safety_factor is not None
        },
        "levers": {
            entry.name: entry.repair_hint.parameter
            for card in cards.values()
            for entry in card.entries
            if entry.repair_hint is not None
        },
    }


def main() -> None:
    train = drive_train()
    for part, status in train["statuses"].items():  # type: ignore[union-attr]
        print(f"{part:<9} {str(status).upper()}")
    for name, factor in train["factors"].items():  # type: ignore[union-attr]
        print(f"  {name:<26} n = {factor}")
    print("what each failing check asks you to move:")
    for name, parameter in train["levers"].items():  # type: ignore[union-attr]
        print(f"  {name:<26} {parameter}")
    print("  -> not one of them is the shaft diameter")


if __name__ == "__main__":
    main()
