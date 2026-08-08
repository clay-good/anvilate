"""Worked example: how well an antenna is matched to its feedline.

An antenna only radiates the power that reaches it; whatever its impedance mismatches back into the
feedline is reflected and wasted. Three related numbers describe the match: the reflection
coefficient (how much bounces back), the voltage standing-wave ratio (the ripple it creates on the
line), and the return loss (the reflected power in decibels). This example evaluates them for a
common mismatch — a 75 ohm antenna on a 50 ohm line.

The reflection coefficient is (75-50)/(75+50) = 0.2, so 20% of the wave amplitude (4% of the power)
reflects. That gives a VSWR of 1.5 — right at the edge of what is usually accepted — and a return
loss of about 14 dB. For comparison, a well-matched 52 ohm antenna on the same line reflects almost
nothing: a VSWR near 1.04 and a return loss above 34 dB. The example reports the reflection
coefficient, VSWR, and return loss of the 75 ohm case.

Run it directly (``python examples/antenna_feedline_match.py``);
:func:`feedline_match` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    reflection_coefficient,
    return_loss,
    voltage_standing_wave_ratio,
)
from anvilate.units import Quantity

ANTENNA_IMPEDANCE = Quantity.parse("75 ohm")
LINE_IMPEDANCE = Quantity.parse("50 ohm")


def feedline_match() -> dict[str, float]:
    """Return the reflection coefficient, VSWR, and return loss of the antenna-feedline match."""
    gamma = reflection_coefficient(
        load_impedance=ANTENNA_IMPEDANCE, characteristic_impedance=LINE_IMPEDANCE
    )
    vswr = voltage_standing_wave_ratio(reflection_coefficient=gamma)
    rl = return_loss(reflection_coefficient=gamma)
    return {
        "reflection_coefficient": gamma,
        "vswr": vswr,
        "return_loss_db": rl,
    }


def main() -> None:
    d = feedline_match()
    print(f"reflection coefficient: {d['reflection_coefficient']:.2f}")
    print(f"VSWR: {d['vswr']:.2f}")
    print(f"return loss: {d['return_loss_db']:.0f} dB")


if __name__ == "__main__":
    main()
