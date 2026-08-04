"""Worked example: when air stops behaving like an incompressible fluid in a fast duct.

Most air-handling calculations quietly assume air is incompressible — a fair approximation, but
only up to a point. That point is a Mach number of about 0.3: below it the density change is under
a few percent and the simple relations hold; above it, compressibility and the temperature rise of
bringing the fast stream to rest start to matter. This example takes air at 15 °C and works out the
speed of sound, then checks two duct velocities against it — a normal 25 m/s duct and an aggressive
120 m/s high-velocity jet — reporting the Mach number and the stagnation temperature rise for each.
The ordinary duct is safely incompressible; the fast jet crosses M = 0.3 and warms measurably at
any stagnation point, the regime where an incompressible pressure-drop calculation quietly starts
to lie.

Run it directly (``python examples/blower_mach_limit.py``);
:func:`duct_mach_check` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import mach_number, speed_of_sound, stagnation_temperature_ratio
from anvilate.units import Quantity

AIR_TEMPERATURE = Quantity.parse("288.15 K")  # 15 deg C
HEAT_CAPACITY_RATIO = 1.4
GAS_CONSTANT = Quantity.parse("287 J/(kg*K)")
NORMAL_DUCT = Quantity.parse("25 m/s")
FAST_JET = Quantity.parse("120 m/s")
INCOMPRESSIBLE_LIMIT = 0.3


def duct_mach_check() -> dict[str, float]:
    """Return the speed of sound (m/s), the Mach numbers, and the fast-jet stagnation rise."""
    a = speed_of_sound(
        temperature=AIR_TEMPERATURE,
        heat_capacity_ratio=HEAT_CAPACITY_RATIO,
        specific_gas_constant=GAS_CONSTANT,
    )

    def state(velocity: Quantity) -> tuple[float, float]:
        m = mach_number(velocity=velocity, speed_of_sound=a)
        t_ratio = stagnation_temperature_ratio(
            mach_number=m, heat_capacity_ratio=HEAT_CAPACITY_RATIO
        )
        return m, t_ratio

    normal_m, normal_ratio = state(NORMAL_DUCT)
    fast_m, fast_ratio = state(FAST_JET)
    return {
        "speed_of_sound_ms": a.to("m/s").magnitude,
        "normal_mach": normal_m,
        "fast_mach": fast_m,
        "fast_stagnation_rise_c": (fast_ratio - 1) * AIR_TEMPERATURE.to("K").magnitude,
    }


def main() -> None:
    d = duct_mach_check()
    print(f"speed of sound : {d['speed_of_sound_ms']:.0f} m/s at 15 deg C")
    normal_ok = "incompressible OK" if d["normal_mach"] < INCOMPRESSIBLE_LIMIT else "compressible"
    fast_ok = "incompressible OK" if d["fast_mach"] < INCOMPRESSIBLE_LIMIT else "compressible"
    rise = d["fast_stagnation_rise_c"]
    print(f"25 m/s duct  : M = {d['normal_mach']:.2f}  ({normal_ok})")
    print(f"120 m/s jet  : M = {d['fast_mach']:.2f}  ({fast_ok}), stagnation warms {rise:.1f} C")
    print("  -> past M ~ 0.3 the incompressible pressure-drop calc quietly starts to lie")


if __name__ == "__main__":
    main()
