"""Worked example: the hoist that must hold its own load.

A worm-drive hoist lifts through a worm gearbox, and the wheel spends most of its
life trying to run *backward* — the suspended load is always pulling the wheel,
and through it the worm, toward unwinding. A hoist earns its keep by refusing:
a self-locking worm holds the load with the power off and no brake at all.

Self-locking is a lead-angle bargain. The worm's thread starts set its lead
angle, and friction only beats the lead below a limit: mu >= cos(phi_n)*tan(lambda).
On a fixed 40 mm worm at 8 mm axial pitch (mu = 0.08, phi_n = 14.5 deg), the
single-start worm (lambda = 3.6 deg) self-locks with a 1.30 margin, but it pays
for the hold in efficiency -- only 43% of the motor's work reaches the drum. Cut
a second or third start to recover efficiency (60%, 69%) and the lead angle opens
past the friction limit: the load now back-drives the moment power is lost, and
the hoist drops. Same worm blank, same friction, and the fast choice is the
unsafe one.

The honest hoist takes the single start and the efficiency hit, or it keeps a
multi-start worm and adds a real holding brake -- it does not pretend a
back-drivable worm holds load. The lining friction is manufacturer's data,
declared inline like any allowable.

Run it directly (``python examples/worm_hoist_selflock.py``);
:func:`screen_worm_hoist` is also exercised in the test suite.
"""

from __future__ import annotations

from math import cos, radians, tan

from anvilate.analysis import worm_gear_efficiency, worm_is_self_locking, worm_lead_angle
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

WORM_PITCH_DIAMETER = Quantity.parse("40 mm")
AXIAL_PITCH = Quantity.parse("8 mm")
FRICTION = 0.08
NORMAL_PRESSURE_ANGLE = 14.5

STARTS = {"single-start worm": 1, "double-start worm": 2, "triple-start worm": 3}


def self_locking_margin(starts: int) -> float:
    """The self-locking safety factor mu / (cos(phi_n)*tan(lambda)) >= 1."""
    lam = worm_lead_angle(
        worm_starts=starts, axial_pitch=AXIAL_PITCH, worm_pitch_diameter=WORM_PITCH_DIAMETER
    )
    threshold = cos(radians(NORMAL_PRESSURE_ANGLE)) * tan(radians(lam))
    return FRICTION / threshold


def efficiency(starts: int) -> float:
    """The worm-driving mesh efficiency for a given number of thread starts."""
    lam = worm_lead_angle(
        worm_starts=starts, axial_pitch=AXIAL_PITCH, worm_pitch_diameter=WORM_PITCH_DIAMETER
    )
    return worm_gear_efficiency(
        lead_angle=lam,
        friction_coefficient=FRICTION,
        normal_pressure_angle=NORMAL_PRESSURE_ANGLE,
    )


def screen_worm_hoist() -> Scorecard:
    """Screen each worm for the hoist's non-negotiable: it must self-lock. The
    detail reports the efficiency the self-locking hold costs."""
    entries = []
    for name, starts in STARTS.items():
        margin = self_locking_margin(starts)
        locks = worm_is_self_locking(
            lead_angle=worm_lead_angle(
                worm_starts=starts,
                axial_pitch=AXIAL_PITCH,
                worm_pitch_diameter=WORM_PITCH_DIAMETER,
            ),
            friction_coefficient=FRICTION,
            normal_pressure_angle=NORMAL_PRESSURE_ANGLE,
        )
        entry = ScorecardEntry.from_safety_factor(name, computed=margin, required=1.0)
        # Fold the efficiency into the detail so the trade-off is visible.
        assert entry.passed == locks  # the SF margin and the predicate agree
        entries.append(
            entry.model_copy(
                update={"detail": f"{entry.detail}; efficiency {efficiency(starts) * 100:.0f}%"}
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    print(screen_worm_hoist())


if __name__ == "__main__":
    main()
