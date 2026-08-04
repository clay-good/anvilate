"""Worked example: why a tall room needs more light fixtures than a low one of the same floor.

Designing a room's lighting by the lumen method needs the coefficient of utilization — the fraction
of a luminaire's output that reaches the desk — and that number is not free: it is read from
a photometric table against the room cavity ratio, RCR = 5·h·(L + W)/(L·W). The taller and narrower
the space between the fixtures and the work plane, the more light the walls swallow before it lands,
the lower the CU, and the more fixtures the same floor needs.

This example lights the same 12 m by 9 m office floor to the same 500 lux target with the same
troffers, at two ceiling heights. In a low-ceiling space the cavity is 1.8 m, the RCR is a modest
1.75, and a good CU of 0.72 meets the target with 12 fixtures. Raise the same room to a tall, open
3.6 m cavity and the RCR doubles to 3.5; the CU drops to 0.55, and the fixture count climbs to 15 to
hit the same 500 lux. Nothing about the desks or the target changed — only the geometry the light
must survive. The lesson is that the room cavity ratio is the hinge of a lumen-method design: it
turns the
room's shape into the CU, and the CU into the number of fixtures on the ceiling.

Run it directly (``python examples/office_lighting_cavity_ratio.py``);
:func:`fixture_counts` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import lumen_method_luminaire_count, room_cavity_ratio
from anvilate.units import Quantity

ROOM_LENGTH = Quantity.parse("12 m")
ROOM_WIDTH = Quantity.parse("9 m")
TARGET_ILLUMINANCE = Quantity.parse("500 lux")
LUMENS_PER_FIXTURE = Quantity.parse("8000 lm")
LIGHT_LOSS_FACTOR = 0.8

# A lower RCR (wide, low room) earns a higher coefficient of utilization.
LOW_CEILING_CAVITY = Quantity.parse("1.8 m")
LOW_CEILING_CU = 0.72
TALL_CEILING_CAVITY = Quantity.parse("3.6 m")
TALL_CEILING_CU = 0.55


def fixture_counts() -> dict[str, float]:
    """Return the cavity ratio and required fixture count for a low and a tall ceiling."""

    def design(cavity: Quantity, cu: float) -> dict[str, float]:
        rcr = room_cavity_ratio(
            cavity_height=cavity, room_length=ROOM_LENGTH, room_width=ROOM_WIDTH
        )
        count = lumen_method_luminaire_count(
            target_illuminance=TARGET_ILLUMINANCE,
            area=Quantity(
                magnitude=ROOM_LENGTH.to("m").magnitude * ROOM_WIDTH.to("m").magnitude,
                unit="m**2",
            ),
            lumens_per_luminaire=LUMENS_PER_FIXTURE,
            coefficient_of_utilization=cu,
            light_loss_factor=LIGHT_LOSS_FACTOR,
        )
        return {"rcr": rcr, "fixtures": count}

    low = design(LOW_CEILING_CAVITY, LOW_CEILING_CU)
    tall = design(TALL_CEILING_CAVITY, TALL_CEILING_CU)
    return {
        "low_rcr": low["rcr"],
        "low_fixtures": low["fixtures"],
        "tall_rcr": tall["rcr"],
        "tall_fixtures": tall["fixtures"],
    }


def main() -> None:
    f = fixture_counts()
    low_n = f["low_fixtures"]
    tall_n = f["tall_fixtures"]
    print(f"low ceiling  : RCR {f['low_rcr']:.2f}, CU {LOW_CEILING_CU} -> {low_n:.0f} fixtures")
    print(f"tall ceiling : RCR {f['tall_rcr']:.2f}, CU {TALL_CEILING_CU} -> {tall_n:.0f} fixtures")
    print("  -> the taller cavity lowers the CU and drives up the fixture count for the same lux")


if __name__ == "__main__":
    main()
