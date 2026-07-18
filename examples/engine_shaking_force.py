"""Worked example: the connecting rod you can't see sets the shake you can feel.

A single-cylinder engine reciprocates a 0.50 kg piston-and-rod mass on a 40 mm
crank at 3000 rpm. Its inertia force -- mass times slider acceleration -- peaks at
top dead centre and shakes the whole engine on its mounts, which are rated to hold
2400 N before they pass the vibration on to the frame.

The peak is set by a part the spec sheet rarely mentions: the connecting rod
length. Slider acceleration at TDC is r·ω²·(1 + r/L), and that (1 + r/L) is the
finite-rod penalty -- the shorter the rod relative to the crank, the higher the
secondary shake. The stubby rod (L/r = 3.5) peaks at 2538 N and overloads the
mounts (0.95 margin); stretching to L/r = 5 drops it to 2369 N and just clears
them (1.01); a long L/r = 6.67 rod brings real headroom (2270 N, 1.06). Same
piston, same speed, same stroke -- the rod ratio alone decides whether the engine
buzzes.

The mount rating is manufacturer's data, declared inline like any allowable.

Run it directly (``python examples/engine_shaking_force.py``);
:func:`screen_shaking_force` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import slider_crank_acceleration
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

RECIPROCATING_MASS = Quantity.parse("0.50 kg")
CRANK_RADIUS = Quantity.parse("40 mm")
CRANK_SPEED = Quantity.parse("3000 rpm")
MOUNT_FORCE_LIMIT = Quantity.parse("2400 N")

ROD_LENGTHS = {
    "short rod (L/r = 3.5)": Quantity.parse("140 mm"),
    "medium rod (L/r = 5.0)": Quantity.parse("200 mm"),
    "long rod (L/r = 6.67)": Quantity.parse("266.8 mm"),
}


def peak_shaking_force(rod_length: Quantity) -> float:
    """The largest inertia force (N) over a revolution: m * max|slider accel|,
    sampled from the exact slider-crank acceleration at one-degree steps."""
    mass = RECIPROCATING_MASS.to("kg").magnitude
    peak_accel = 0.0
    angle = 0
    while angle < 360:
        a = abs(
            slider_crank_acceleration(
                crank_radius=CRANK_RADIUS,
                rod_length=rod_length,
                crank_angle=float(angle),
                crank_speed=CRANK_SPEED,
            )
            .to("m/s**2")
            .magnitude
        )
        peak_accel = max(peak_accel, a)
        angle += 1
    return mass * peak_accel


def screen_shaking_force() -> Scorecard:
    """Screen each rod length: the peak shaking force must stay under the mount
    rating (safety factor = mount limit / peak force)."""
    limit = MOUNT_FORCE_LIMIT.to("N").magnitude
    entries = [
        ScorecardEntry.from_safety_factor(
            name,
            computed=limit / peak_shaking_force(rod_length),
            required=1.0,
        )
        for name, rod_length in ROD_LENGTHS.items()
    ]
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, rod_length in ROD_LENGTHS.items():
        print(f"{name}: peak shaking force {peak_shaking_force(rod_length):.0f} N")
    print(screen_shaking_force())


if __name__ == "__main__":
    main()
