"""Worked example: the crack a clay backfill opens behind a wall, and why it fills with water.

Cohesionless sand presses on a wall from the very top down, but a clay backfill is different:
cohesion holds the clay together, so near the surface the Rankine active pressure comes out
*negative* — the clay is in tension and simply pulls away from the wall, opening a crack. Only
below the tension-crack depth does the soil start to push. This example works a 5 m wall retaining
a c-φ clay and finds two things the sandy formula never shows: the depth of that tension crack
(here about 2.4 m, nearly half the wall), and the pressure profile below it. The catch is the
crack itself — in rain it fills with water, and the water pressure it then applies, undiminished
by any cohesion, is a worst case that has failed walls a dry analysis called safe. The cohesion
that helped is exactly what opens the crack that hurts.

Run it directly (``python examples/clay_backfill_tension_crack.py``);
:func:`backfill_pressures` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import rankine_active_pressure_cohesive, tension_crack_depth
from anvilate.units import Quantity

WALL_HEIGHT = Quantity.parse("5 m")
UNIT_WEIGHT = Quantity.parse("18 kN/m**3")
FRICTION_ANGLE = 20.0  # clay
COHESION = Quantity.parse("15 kPa")


def backfill_pressures() -> dict[str, float]:
    """Return the tension-crack depth (m), the surface pressure, and the base pressure (kPa)."""
    z_c = (
        tension_crack_depth(
            cohesion=COHESION, unit_weight=UNIT_WEIGHT, friction_angle=FRICTION_ANGLE
        )
        .to("m")
        .magnitude
    )
    surface = (
        rankine_active_pressure_cohesive(
            depth=Quantity.parse("0 m"),
            unit_weight=UNIT_WEIGHT,
            friction_angle=FRICTION_ANGLE,
            cohesion=COHESION,
        )
        .to("kPa")
        .magnitude
    )
    base = (
        rankine_active_pressure_cohesive(
            depth=WALL_HEIGHT,
            unit_weight=UNIT_WEIGHT,
            friction_angle=FRICTION_ANGLE,
            cohesion=COHESION,
        )
        .to("kPa")
        .magnitude
    )
    return {
        "tension_crack_m": z_c,
        "surface_pressure_kpa": surface,
        "base_pressure_kpa": base,
    }


def main() -> None:
    p = backfill_pressures()
    crack = p["tension_crack_m"]
    fraction = crack / WALL_HEIGHT.to("m").magnitude
    print(f"tension crack depth : {crack:.2f} m ({fraction:.0%} of the 5 m wall)")
    print(f"pressure at surface : {p['surface_pressure_kpa']:.1f} kPa (negative = tension, cracks)")
    print(f"pressure at base    : {p['base_pressure_kpa']:.1f} kPa (compressive, pushing)")
    print("  -> the crack fills with water in rain — a worst case a dry analysis misses")


if __name__ == "__main__":
    main()
