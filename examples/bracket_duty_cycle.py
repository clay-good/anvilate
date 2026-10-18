"""Worked example: which road event uses up a suspension bracket?

A bracket's duty cycle over a 200,000 km life has three events, each a stress history at
its weld toe with how often it occurs: a pothole strike (0, 380, -160, 0 MPa, 4,000 times),
hard cornering (0, 220, -40, 0 MPa, 300,000 times) and braking (0, 140, 20, 0 MPa,
600,000 times). Counted by rainflow, corrected for mean stress by Goodman (ultimate
480 MPa), and read on an illustrative weld S-N curve (σ_a = 700·N^-0.1 MPa), Miner's rule
gives a damage of 4.054 per life: the bracket lasts 0.25 of it.

The pothole drives it, with 0.97 of the damage, though it is the rarest event by two orders
of magnitude. On an S-N curve this steep, life goes as the stress to the tenth power, so one
cycle twice as large does about a thousand times the damage. Cornering, 75 times as
frequent, is 0.03. Leaving the mean stress uncorrected would put the life at 3.27 lives, a
bracket that passes, because every one of these cycles has a tensile mean.

Run it directly (``python examples/bracket_duty_cycle.py``);
:func:`bracket_duty_cycle` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    BasquinCurve,
    DutyEvent,
    MeanStressCorrection,
    duty_cycle_damage,
)
from anvilate.units import Quantity

LIFE_KM = 200_000  # the life the occurrences are counted over

CURVE = BasquinCurve(
    coefficient=Quantity(magnitude=700.0, unit="MPa"), exponent=-0.1,
    source="illustrative weld-toe S-N curve",
)  # fmt: skip


def _event(name: str, history: tuple[float, ...], occurrences: float) -> DutyEvent:
    return DutyEvent(
        name=name, history=tuple(Quantity(magnitude=s, unit="MPa") for s in history),
        occurrences_per_life=occurrences, source=f"{name}, proving-ground strain survey",
        repeating=True,
    )  # fmt: skip


EVENTS = (
    _event("pothole", (0.0, 380.0, -160.0, 0.0), 4_000),
    _event("cornering", (0.0, 220.0, -40.0, 0.0), 300_000),
    _event("braking", (0.0, 140.0, 20.0, 0.0), 600_000),
)


def bracket_duty_cycle() -> dict[str, float | str]:
    """Return the damage per life, each event's share, and the uncorrected life."""
    goodman = duty_cycle_damage(
        EVENTS,
        curve=CURVE,
        correction=MeanStressCorrection.GOODMAN,
        ultimate_strength=Quantity(magnitude=480.0, unit="MPa"),
    )
    plain = duty_cycle_damage(EVENTS, curve=CURVE, correction=MeanStressCorrection.NONE)
    shares = {e.event: e.share for e in goodman.events}
    return {
        "damage": goodman.total_damage,
        "lives": goodman.lives,
        "governing": goodman.governing_event,
        "cornering_share": shares["cornering"],
        "pothole_share": shares["pothole"],
        "lives_uncorrected": plain.lives,
    }


def main() -> None:
    d = bracket_duty_cycle()
    print(f"damage per life {d['damage']:.3f}: {d['lives']:.2f} lives")
    print(f"{d['governing']} drives it: {d['pothole_share']:.2f} of the damage")
    print(f"cornering: {d['cornering_share']:.2f}")
    print(f"without the mean-stress correction: {d['lives_uncorrected']:.2f} lives")


if __name__ == "__main__":
    main()
