"""Worked example: the stiff mount that made the vibration worse.

A machine runs at 1500 rpm — a 25 Hz forcing that must not shake through to the
floor. It sits on isolator mounts, and the temptation is to make them stiff and
solid, as if stiffness meant support. For vibration it means the opposite.

An isolator only isolates once the forcing frequency climbs past sqrt(2) times the
mount's own natural frequency; below that it *amplifies*. A stiff mount tuned to
20 Hz puts the forcing ratio at just 1.25 — inside the amplification band — and
passes 175% of the machine's shaking to the floor (a 0.11 margin against the 20%
transmission target: far worse than no mount at all). A medium 12 Hz mount reaches
the isolation region but only cuts transmission to 31%, still short (0.66). The
soft 6 Hz mount puts the ratio at 4.2, deep into isolation, and passes just 7% (a
3.0 margin).

Vibration isolation is won by going soft, not stiff: drop the mount's natural
frequency well below the forcing so the ratio clears sqrt(2) with room to spare. A
mount too stiff to sag is a mount too stiff to isolate. The damping and target
transmission are design data, declared inline like any allowable.

Run it directly (``python examples/machine_vibration_isolation.py``);
:func:`screen_isolation` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import transmissibility
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

FORCING = Quantity.parse("25 Hz")
DAMPING_RATIO = 0.05
MAX_TRANSMISSION = 0.20  # pass at most 20% of the shaking to the floor

MOUNTS = {
    "stiff mount (20 Hz)": Quantity.parse("20 Hz"),
    "medium mount (12 Hz)": Quantity.parse("12 Hz"),
    "soft mount (6 Hz)": Quantity.parse("6 Hz"),
}


def transmission(mount_frequency: Quantity) -> float:
    """The fraction of the forcing transmitted through a mount of this frequency."""
    ratio = FORCING.to("Hz").magnitude / mount_frequency.to("Hz").magnitude
    return transmissibility(frequency_ratio=ratio, damping_ratio=DAMPING_RATIO)


def screen_isolation() -> Scorecard:
    """Screen each mount: its transmissibility must stay under the target
    (safety factor = target transmission / actual)."""
    entries = [
        ScorecardEntry.from_safety_factor(
            name, computed=MAX_TRANSMISSION / transmission(freq), required=1.0
        )
        for name, freq in MOUNTS.items()
    ]
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, freq in MOUNTS.items():
        print(f"{name}: transmits {transmission(freq) * 100:.0f}% of the forcing")
    print(screen_isolation())


if __name__ == "__main__":
    main()
