"""Worked example: the gearbox ratio that could not be cut.

A trailer winch drum needs 200 N*m to haul its load; the motor delivers
55 N*m at 1440 rpm. Direct drive musters barely a quarter of the demand, so a
single-stage planetary reducer goes between them — ring bolted to the case,
sun on the motor, carrier on the drum — giving a (1 + N_r/N_s):1 reduction.

On paper the ratio is a free choice. In steel it is not. The tidy 4.5:1
(sun 30, ring 105) dies at the first hard constraint: the planet must span the
sun-to-ring gap, N_p = (105 - 30)/2 = 37.5 teeth — there is no half-tooth
gear, so that set cannot exist. The next pick, 4.7:1 (sun 30, ring 110), cuts
fine (40-tooth planets) but will not go together: three equally spaced planets
need (N_s + N_r) divisible by 3, and 140 is not — the second planet arrives at
its slot out of phase and never drops in. The set that works is 4.6:1
(sun 30, ring 108): 39-tooth planets, 138/3 assembles, and the Willis
equation puts the drum at 313 rpm — enough mechanical advantage to clear the
200 N*m demand with margin. A planetary ratio is a *tooth-count* choice, and
whole teeth and assembly phasing get a vote before torque does.

Torque here is the ideal (loss-free) power balance T_out = T_in * (w_in/w_out);
a real screen would knock it down by gear-mesh efficiency.

Run it directly (``python examples/winch_planetary_reducer.py``);
:func:`screen_winch_reducer` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    planetary_can_assemble,
    planetary_planet_teeth,
    planetary_speed,
)
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.units import Quantity

REQUIRED_DRUM_TORQUE = Quantity.parse("200 N*m")
MOTOR_TORQUE = Quantity.parse("55 N*m")
MOTOR_SPEED = Quantity.parse("1440 rpm")
MIN_SAFETY_FACTOR = 1.2
PLANET_COUNT = 3

CANDIDATES = {
    "4.5:1 (sun 30, ring 105)": (30, 105),
    "4.7:1 (sun 30, ring 110)": (30, 110),
    "4.6:1 (sun 30, ring 108)": (30, 108),
}


def drum_speed(sun_teeth: int, ring_teeth: int) -> Quantity:
    """Carrier (drum) speed with the ring held and the motor on the sun."""
    return planetary_speed(
        sun_teeth=sun_teeth,
        ring_teeth=ring_teeth,
        sun_speed=MOTOR_SPEED,
        ring_speed=Quantity.parse("0 rpm"),
    )


def drum_torque(sun_teeth: int, ring_teeth: int) -> Quantity:
    """Ideal drum torque from the power balance T_out = T_in * (w_in/w_out)."""
    ratio = MOTOR_SPEED.to("rpm").magnitude / drum_speed(sun_teeth, ring_teeth).to("rpm").magnitude
    return Quantity(magnitude=MOTOR_TORQUE.to("N*m").magnitude * ratio, unit="N*m")


def buildability_entry(name: str, sun_teeth: int, ring_teeth: int) -> ScorecardEntry:
    """PASS only when the set can be cut (whole-tooth planets) and assembled."""
    try:
        planets = planetary_planet_teeth(sun_teeth=sun_teeth, ring_teeth=ring_teeth)
    except ValueError as exc:
        return ScorecardEntry(name=f"{name}, buildable", status=CheckStatus.FAIL, detail=str(exc))
    if not planetary_can_assemble(
        sun_teeth=sun_teeth, ring_teeth=ring_teeth, planet_count=PLANET_COUNT
    ):
        return ScorecardEntry(
            name=f"{name}, buildable",
            status=CheckStatus.FAIL,
            detail=(
                f"{planets}-tooth planets cut, but {PLANET_COUNT} equally spaced planets "
                f"cannot assemble: {sun_teeth} + {ring_teeth} = {sun_teeth + ring_teeth} "
                f"is not divisible by {PLANET_COUNT}"
            ),
        )
    return ScorecardEntry(
        name=f"{name}, buildable",
        status=CheckStatus.PASS,
        detail=(
            f"{planets}-tooth planets, {PLANET_COUNT} planets space equally "
            f"(({sun_teeth} + {ring_teeth}) / {PLANET_COUNT} = "
            f"{(sun_teeth + ring_teeth) // PLANET_COUNT})"
        ),
    )


def screen_winch_reducer() -> Scorecard:
    """Screen direct drive, then each candidate set: buildability before torque."""
    required = REQUIRED_DRUM_TORQUE.to("N*m").magnitude
    entries = [
        ScorecardEntry.from_safety_factor(
            "direct drive, drum torque",
            computed=MOTOR_TORQUE.to("N*m").magnitude / required,
            required=MIN_SAFETY_FACTOR,
        )
    ]
    for name, (sun_teeth, ring_teeth) in CANDIDATES.items():
        buildable = buildability_entry(name, sun_teeth, ring_teeth)
        entries.append(buildable)
        if buildable.passed:
            entries.append(
                ScorecardEntry.from_safety_factor(
                    f"{name}, drum torque",
                    computed=drum_torque(sun_teeth, ring_teeth).to("N*m").magnitude / required,
                    required=MIN_SAFETY_FACTOR,
                )
            )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    sun_teeth, ring_teeth = CANDIDATES["4.6:1 (sun 30, ring 108)"]
    speed = drum_speed(sun_teeth, ring_teeth).to("rpm").magnitude
    torque = drum_torque(sun_teeth, ring_teeth).to("N*m").magnitude
    print(
        f"chosen set: sun {sun_teeth} / ring {ring_teeth} -> drum {speed:.1f} rpm, {torque:.0f} N*m"
    )
    print(screen_winch_reducer())


if __name__ == "__main__":
    main()
