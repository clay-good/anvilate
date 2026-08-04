"""Worked example: will the wind resonate a steel stack? The vortex-shedding lock-in check.

A slender steel stack in the wind sheds vortices off alternate sides, and if the shedding frequency
drifts up to the stack's natural frequency, the vibration locks in and can grow until it fatigues
the base. This example screens a 1 m diameter stack with a 0.9 Hz first natural frequency. It finds
the wind speed at which shedding would resonate it — the lock-in velocity — from the Strouhal
relation with St = 0.2 for a cylinder, and checks whether that speed falls in the normal wind range.
It then reads the shedding frequency at a typical 10 m/s wind and the reduced velocity that scores
the risk: a reduced velocity near 1/St (about 5) means the wind is parking the shedding right on the
natural frequency. Here the lock-in wind lands at a modest, common speed, so the stack needs a
helical strake or a damper — the classic outcome the reduced-velocity screen is meant to flag.

Run it directly (``python examples/stack_vortex_lock_in.py``);
:func:`stack_viv_screen` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    lock_in_velocity,
    reduced_velocity,
    vortex_shedding_frequency,
)
from anvilate.units import Quantity

STROUHAL = 0.2  # circular cylinder
DIAMETER = Quantity.parse("1 m")
NATURAL_FREQUENCY = Quantity.parse("0.9 Hz")
OPERATING_WIND = Quantity.parse("10 m/s")


def stack_viv_screen() -> dict[str, float]:
    """Return the lock-in wind speed, the shedding frequency at wind, and the reduced velocity."""
    lock_in = lock_in_velocity(
        strouhal_number=STROUHAL,
        natural_frequency=NATURAL_FREQUENCY,
        characteristic_length=DIAMETER,
    )
    shedding = vortex_shedding_frequency(
        strouhal_number=STROUHAL, velocity=OPERATING_WIND, characteristic_length=DIAMETER
    )
    v_r = reduced_velocity(
        velocity=lock_in,
        natural_frequency=NATURAL_FREQUENCY,
        characteristic_length=DIAMETER,
    )
    return {
        "lock_in_wind_m_s": lock_in.to("m/s").magnitude,
        "shedding_hz_at_10ms": shedding.to("Hz").magnitude,
        "reduced_velocity_at_lock_in": v_r,
    }


def main() -> None:
    s = stack_viv_screen()
    print(f"lock-in wind speed        : {s['lock_in_wind_m_s']:.1f} m/s (resonance risk here)")
    print(f"shedding freq at 10 m/s   : {s['shedding_hz_at_10ms']:.1f} Hz")
    print(f"reduced velocity at lock-in: {s['reduced_velocity_at_lock_in']:.1f} (≈ 1/St)")
    print("  -> the lock-in wind is a common speed; fit a strake or damper to detune the stack")


if __name__ == "__main__":
    main()
