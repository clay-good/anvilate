"""Worked example: the vibration mount that is stiff enough to be useless.

A 1500 rpm pump (25 Hz) is bolted to a floor that must not shake. The shop reaches for a
firm rubber mount -- it feels solid, deflecting only 1 mm under the pump's weight -- and
expects it to isolate. It barely does. A firm mount has a high natural frequency (15.8 Hz
here), and the forcing frequency is only 1.6 times that, so the mount transmits 66 % of the
vibration through to the floor: a mere 34 % isolation, a safety factor of 0.15 against a
90 %-isolation target.

Isolation is not stiffness -- it is *softness*. A mount only isolates above a frequency
ratio of √2, and the deeper into that region you go the better, so isolating well means a
*low* natural frequency, which means a mount that deflects a lot under load. Inverting the
transmissibility for 90 % isolation (TR = 0.1) at 25 Hz asks for a natural frequency of
7.5 Hz, which means a mount that settles 4.4 mm under the pump's weight -- four times as
soft as the firm one. Fit that mount and the transmitted fraction drops to 10 %, a safety
factor of 1.01 on the target.

The lesson runs against intuition: the mount that feels reassuringly solid is the one that
passes the vibration straight through, and the fix for a shaking floor is a *softer* mount
(more static deflection), not a firmer one. An isolator is selected by its static
deflection, and "stiffer" is the wrong direction.

Run it directly (``python examples/isolator_mount_selection.py``);
:func:`screen_mount` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    isolator_static_deflection_for_transmissibility as required_deflection,
)
from anvilate.analysis import natural_frequency_from_deflection, transmissibility
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

FORCING_FREQUENCY = Quantity.parse("25 Hz")  # 1500 rpm
TARGET_TRANSMISSIBILITY = 0.10  # 90% isolation
FIRM_MOUNT_DEFLECTION = Quantity.parse("1 mm")
SOFT_MOUNT_DEFLECTION = Quantity.parse("4.4 mm")


def _achieved_transmissibility(static_deflection: Quantity) -> float:
    natural = natural_frequency_from_deflection(static_deflection)
    ratio = FORCING_FREQUENCY.to("Hz").magnitude / natural.to("Hz").magnitude
    return transmissibility(frequency_ratio=ratio, damping_ratio=0.0)


def _screen(static_deflection: Quantity) -> Scorecard:
    achieved = _achieved_transmissibility(static_deflection)
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "transmissibility vs 90%-isolation target",
                computed=TARGET_TRANSMISSIBILITY / achieved,
                required=1.0,
            ),
        )
    )


def screen_mount() -> Scorecard:
    """Screen the firm 1 mm mount: it is too stiff to isolate."""
    return _screen(FIRM_MOUNT_DEFLECTION)


def screen_soft_mount() -> Scorecard:
    """Screen the soft 4.4 mm mount sized from the transmissibility inverse."""
    return _screen(SOFT_MOUNT_DEFLECTION)


def main() -> None:
    needed = required_deflection(
        forcing_frequency=FORCING_FREQUENCY, transmissibility=TARGET_TRANSMISSIBILITY
    )
    print(f"static deflection needed for 90% isolation: {needed.to('mm').magnitude:.2f} mm")
    print("firm mount (1 mm):")
    print(screen_mount())
    print("\nsoft mount (4.4 mm):")
    print(screen_soft_mount())


if __name__ == "__main__":
    main()
