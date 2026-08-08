"""Worked example: comparing an LED and an incandescent bulb by luminous efficacy.

The efficiency of a light source is its luminous efficacy — lumens out per watt in. It decides how
much electrical power a lighting job costs to hit a lumen target, and it is the single number that
explains why LEDs displaced incandescent bulbs. This example compares the two at equal light output,
and measures each against the theoretical maximum.

Both sources emit 800 lumens (a typical 60 W incandescent's output). The LED draws 8 W, for an
efficacy of 100 lm/W; the incandescent draws the full 60 W, only about 13 lm/W — so the LED uses
about seven times less power for the same light. Against the 683 lm/W ceiling of ideal 555 nm light,
the LED runs about 15% efficient and the incandescent under 2%. The example reports both efficacies
and the LED's overall luminous efficiency.

Run it directly (``python examples/led_vs_incandescent_efficacy.py``);
:func:`efficacy_comparison` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import luminous_efficacy, luminous_efficiency
from anvilate.units import Quantity

LIGHT_OUTPUT = Quantity(magnitude=800.0, unit="lm")
LED_POWER = Quantity.parse("8 W")
INCANDESCENT_POWER = Quantity.parse("60 W")


def efficacy_comparison() -> dict[str, float]:
    """Return the LED and incandescent efficacies and the LED's overall luminous efficiency."""
    led_efficacy = luminous_efficacy(luminous_flux=LIGHT_OUTPUT, electrical_power=LED_POWER)
    incandescent_efficacy = luminous_efficacy(
        luminous_flux=LIGHT_OUTPUT, electrical_power=INCANDESCENT_POWER
    )
    led_efficiency = luminous_efficiency(luminous_efficacy=led_efficacy)
    return {
        "led_efficacy_lm_w": led_efficacy.to("lm/W").magnitude,
        "incandescent_efficacy_lm_w": incandescent_efficacy.to("lm/W").magnitude,
        "led_efficiency_percent": led_efficiency * 100.0,
    }


def main() -> None:
    d = efficacy_comparison()
    print(f"LED efficacy: {d['led_efficacy_lm_w']:.0f} lm/W")
    print(f"incandescent efficacy: {d['incandescent_efficacy_lm_w']:.0f} lm/W")
    print(f"LED luminous efficiency: {d['led_efficiency_percent']:.0f}%")


if __name__ == "__main__":
    main()
