"""Worked example: a wind turbine's power at two wind speeds, and how far it is from the Betz limit.

Wind power is a cube-law business: the power in the wind goes as the cube of its speed, so a
turbine's output swings enormously with the weather and its siting matters more than almost anything
else. This example takes a 90 m rotor with a power coefficient of 0.42 (a good modern value,
comfortably under the Betz ceiling) and finds its output at a brisk 12 m/s and at a light 8 m/s. The
lighter wind is two-thirds the speed but yields only about a third of the power — the cube law at
work. The example also reports the theoretical Betz limit, the 16/27 ≈ 59% of the wind's power that
no turbine can exceed, to put the 42% coefficient in context: even a perfect rotor leaves 40% of the
wind's energy in the air behind it.

Run it directly (``python examples/wind_turbine_power_curve.py``);
:func:`turbine_output` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import BETZ_LIMIT, wind_turbine_power
from anvilate.units import Quantity

AIR_DENSITY = Quantity.parse("1.225 kg/m**3")
ROTOR_DIAMETER = Quantity.parse("90 m")
POWER_COEFFICIENT = 0.42


def _power(speed: str) -> float:
    return (
        wind_turbine_power(
            air_density=AIR_DENSITY,
            rotor_diameter=ROTOR_DIAMETER,
            wind_speed=Quantity.parse(speed),
            power_coefficient=POWER_COEFFICIENT,
        )
        .to("MW")
        .magnitude
    )


def turbine_output() -> dict[str, float]:
    """Return the turbine power (MW) at 12 and 8 m/s and the Betz limit."""
    brisk = _power("12 m/s")
    light = _power("8 m/s")
    return {
        "power_12ms_mw": brisk,
        "power_8ms_mw": light,
        "light_over_brisk": light / brisk,
        "betz_limit": BETZ_LIMIT,
    }


def main() -> None:
    t = turbine_output()
    print(f"power at 12 m/s : {t['power_12ms_mw']:.2f} MW")
    share = t["light_over_brisk"] * 100
    print(f"power at 8 m/s  : {t['power_8ms_mw']:.2f} MW ({share:.0f}% of the 12 m/s output)")
    print(f"Betz limit      : {t['betz_limit'] * 100:.0f}% (the 0.42 coefficient is well under it)")
    print("  -> two-thirds the wind speed gives about a third the power — the cube law dominates")


if __name__ == "__main__":
    main()
