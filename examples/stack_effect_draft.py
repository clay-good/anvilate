"""Worked example: the invisible draft that pulls air up a tall building in winter.

Warm air is lighter than cold, so a tall column of heated indoor air floats on the denser outdoor
air and draws a pressure difference over the building's height — the stack effect. It is the same
buoyancy that lifts a boat, working on air, and it is what makes a chimney draw and what pulls
lobby doors shut and whistles air up stairwells in a winter high-rise. The driving pressure grows
with both the height and the indoor–outdoor temperature gap, so it is a winter phenomenon: on a
cold day a tall building has a real, sometimes troublesome, draft, while in summer it weakens and
reverses. This example computes the stack pressure across a 60 m building on a −5 °C winter day and
then on a mild spring day to show how sharply it depends on the temperature difference — the number
a smoke-control or door-hardware designer has to size for.

Run it directly (``python examples/stack_effect_draft.py``);
:func:`building_draft` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import stack_effect_pressure
from anvilate.units import Quantity

HEIGHT = Quantity.parse("60 m")
INDOOR = Quantity.parse("294.15 K")  # 21 deg C heated
ATMOSPHERIC = Quantity.parse("101325 Pa")
COLD_OUTDOOR = Quantity.parse("268.15 K")  # -5 deg C winter
MILD_OUTDOOR = Quantity.parse("288.15 K")  # 15 deg C spring


def building_draft() -> dict[str, float]:
    """Return the stack-effect pressure (Pa) on a cold winter day and a mild spring day."""
    winter = (
        stack_effect_pressure(
            height=HEIGHT,
            indoor_temperature=INDOOR,
            outdoor_temperature=COLD_OUTDOOR,
            atmospheric_pressure=ATMOSPHERIC,
        )
        .to("Pa")
        .magnitude
    )
    mild = (
        stack_effect_pressure(
            height=HEIGHT,
            indoor_temperature=INDOOR,
            outdoor_temperature=MILD_OUTDOOR,
            atmospheric_pressure=ATMOSPHERIC,
        )
        .to("Pa")
        .magnitude
    )
    return {
        "winter_pa": winter,
        "mild_pa": mild,
        "winter_over_mild": winter / mild,
    }


def main() -> None:
    d = building_draft()
    print(f"winter (-5 C) : {d['winter_pa']:.0f} Pa stack pressure over the 60 m height")
    print(f"mild (+15 C)  : {d['mild_pa']:.0f} Pa")
    print(f"  -> the cold day drives {d['winter_over_mild']:.1f}x the draft — a winter problem")


if __name__ == "__main__":
    main()
