"""Worked example: one retaining wall, three ways it can fail before the stem ever bends.

A gravity retaining wall is checked for its concrete strength almost last. Long before
that, the backfill pushing on it can tip it over its toe, slide it across its base, or
crush the soil under its heel — three external-stability failures the stem's own strength
never sees. This example takes a 4 m wall retaining φ = 30° granular fill, pulls the
Rankine thrust once, and runs all three checks from it: overturning and sliding both pass
comfortably, but the resultant lands outside the middle third of the base, so the toe
pressure spikes and the heel lifts off — the governing check is bearing, not stability.
The point is that no single number describes whether the wall stands.

Run it directly (``python examples/retaining_wall_stability.py``);
:func:`wall_stability` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    eccentric_base_pressure,
    rankine_lateral_thrust,
    retaining_wall_overturning_factor,
    retaining_wall_sliding_factor,
)
from anvilate.units import Quantity

UNIT_WEIGHT = Quantity.parse("18 kN/m**3")  # backfill gamma
WALL_HEIGHT = Quantity.parse("4 m")  # H
FRICTION_ANGLE = 30.0  # phi, degrees

VERTICAL_LOAD = Quantity.parse("200 kN/m")  # wall + heel soil weight, per m run
LOAD_ARM = Quantity.parse("1.6 m")  # its lever arm to the toe
BASE_WIDTH = Quantity.parse("3 m")  # B
RESULTANT_ECCENTRICITY = Quantity.parse("0.6 m")  # e of the vertical resultant from base center
BASE_FRICTION = 0.5  # mu = tan(delta)

FS_OVERTURNING_MIN = 2.0
FS_SLIDING_MIN = 1.5


def wall_stability() -> dict[str, float]:
    """Return the overturning and sliding factors of safety and the base pressures (kPa)."""
    thrust = rankine_lateral_thrust(
        unit_weight=UNIT_WEIGHT, height=WALL_HEIGHT, friction_angle=FRICTION_ANGLE
    )
    thrust_height = Quantity(magnitude=WALL_HEIGHT.to("m").magnitude / 3.0, unit="m")  # H/3
    fs_ot = retaining_wall_overturning_factor(
        lateral_thrust=thrust,
        thrust_height=thrust_height,
        vertical_load=VERTICAL_LOAD,
        load_arm=LOAD_ARM,
    )
    fs_sl = retaining_wall_sliding_factor(
        lateral_thrust=thrust,
        vertical_load=VERTICAL_LOAD,
        base_friction_coefficient=BASE_FRICTION,
    )
    pressures = eccentric_base_pressure(
        vertical_load=VERTICAL_LOAD,
        base_width=BASE_WIDTH,
        eccentricity=RESULTANT_ECCENTRICITY,
    )
    return {
        "thrust_kn_per_m": thrust.to("kN/m").magnitude,
        "fs_overturning": fs_ot,
        "fs_sliding": fs_sl,
        "q_max_kpa": pressures["q_max"].to("kPa").magnitude,
        "q_min_kpa": pressures["q_min"].to("kPa").magnitude,
    }


def main() -> None:
    s = wall_stability()
    print(f"active thrust : {s['thrust_kn_per_m']:.0f} kN/m")
    ot_ok = "PASS" if s["fs_overturning"] >= FS_OVERTURNING_MIN else "FAIL"
    sl_ok = "PASS" if s["fs_sliding"] >= FS_SLIDING_MIN else "FAIL"
    print(f"overturning   : FS = {s['fs_overturning']:.2f}  ({ot_ok} vs {FS_OVERTURNING_MIN})")
    print(f"sliding       : FS = {s['fs_sliding']:.2f}  ({sl_ok} vs {FS_SLIDING_MIN})")
    heel = "heel lifts off (e outside middle third)" if s["q_min_kpa"] == 0.0 else "full contact"
    q_max = s["q_max_kpa"]
    q_min = s["q_min_kpa"]
    print(f"base pressure : q_max = {q_max:.0f} kPa, q_min = {q_min:.0f} kPa  ({heel})")


if __name__ == "__main__":
    main()
