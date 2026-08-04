"""Worked example: the pump that runs fine on cold water and cavitates on hot.

A pump can have all the power it needs and still tear itself apart, if the pressure at its inlet
drops to the point where the liquid flashes to vapor — cavitation. The check is net positive
suction head: the head available at the suction (NPSH_a) has to stay above the head the pump
requires (NPSH_r). The subtle part is that NPSH_a depends on the liquid's *vapor pressure*, which
climbs steeply with temperature. This example runs one unchanged installation — same lift, same
suction piping, same pump requiring 4 m — on cold water and then on hot. Cold, the margin is a
healthy 1.6 m. Hot, the vapor pressure has risen more than twentyfold and eaten the suction head,
so the margin goes sharply negative and the pump cavitates. Nothing about the pump changed; the
temperature did.

Run it directly (``python examples/pump_npsh_cavitation.py``);
:func:`suction_margins` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import npsh_available, npsh_margin
from anvilate.units import Quantity

ATMOSPHERIC = Quantity.parse("101.325 kPa")
STATIC_SUCTION_HEAD = Quantity.parse("-3 m")  # pump lifts water 3 m from below
SUCTION_FRICTION_LOSS = Quantity.parse("1.5 m")
NPSH_REQUIRED = Quantity.parse("4 m")  # from the pump curve

# Water properties cold (20 C) and hot (80 C).
COLD_VAPOR_PRESSURE = Quantity.parse("2.34 kPa")
COLD_DENSITY = Quantity.parse("998 kg/m**3")
HOT_VAPOR_PRESSURE = Quantity.parse("47.4 kPa")
HOT_DENSITY = Quantity.parse("972 kg/m**3")


def suction_margins() -> dict[str, float]:
    """Return the available NPSH (m) and cavitation margin (m) for cold and hot water."""

    def margin(vapor: Quantity, density: Quantity) -> tuple[float, float]:
        available = npsh_available(
            atmospheric_pressure=ATMOSPHERIC,
            vapor_pressure=vapor,
            density=density,
            static_suction_head=STATIC_SUCTION_HEAD,
            suction_friction_loss=SUCTION_FRICTION_LOSS,
        )
        m = npsh_margin(npsh_available=available, npsh_required=NPSH_REQUIRED)
        return available.to("m").magnitude, m.to("m").magnitude

    cold_a, cold_m = margin(COLD_VAPOR_PRESSURE, COLD_DENSITY)
    hot_a, hot_m = margin(HOT_VAPOR_PRESSURE, HOT_DENSITY)
    return {
        "cold_npsh_available_m": cold_a,
        "cold_margin_m": cold_m,
        "hot_npsh_available_m": hot_a,
        "hot_margin_m": hot_m,
    }


def main() -> None:
    s = suction_margins()

    def verdict(m: float) -> str:
        return "cavitates" if m < 0 else "OK"

    cold_m = s["cold_margin_m"]
    hot_m = s["hot_margin_m"]
    cold_a = s["cold_npsh_available_m"]
    hot_a = s["hot_npsh_available_m"]
    print(f"cold water (20 C) : NPSH_a {cold_a:.1f} m, margin {cold_m:+.1f} m  ({verdict(cold_m)})")
    print(f"hot water (80 C)  : NPSH_a {hot_a:.1f} m, margin {hot_m:+.1f} m  ({verdict(hot_m)})")
    print("  -> vapor pressure rose 20x with temperature and ate the suction head")


if __name__ == "__main__":
    main()
