"""Worked example: why rockets are mostly fuel — the Tsiolkovsky equation and its logarithm.

The rocket equation, Δv = I_sp·g₀·ln(m₀/m_f), is the tyranny at the heart of spaceflight. A stage's
velocity change depends not on its mass ratio directly but on the *logarithm* of it, so every extra
increment of Δv costs exponentially more propellant. Because the burnt-out mass m_f can never drop
below the structure and payload, there is a hard wall: no matter how much fuel you add, a single
stage struggles past a Δv much larger than its exhaust velocity, which is why launch vehicles stack
stages and shed them.

This example takes a stage with a 250 s specific impulse — a decent chemical engine — fuelled to
100 t and burning down to 30 t, a mass ratio of 3.33. The rocket equation gives a Δv of about
2950 m/s. Turn the question around: reaching low Earth orbit needs roughly 9400 m/s of Δv once
gravity and drag losses are counted, and to get that from a single 250 s stage would demand a
propellant mass fraction of about 98% — leaving just 2% for the tank, engine, and payload, which is
structurally impossible and is why orbital rockets are multi-stage. The example reports the
stage Δv, and the propellant fraction a single 250 s stage would need for a 9400 m/s orbital budget.

Run it directly (``python examples/rocket_delta_v_budget.py``);
:func:`delta_v_budget` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    rocket_delta_v,
    rocket_propellant_mass_fraction,
)
from anvilate.units import Quantity

SPECIFIC_IMPULSE = Quantity.parse("250 s")
INITIAL_MASS = Quantity.parse("100000 kg")
FINAL_MASS = Quantity.parse("30000 kg")
ORBITAL_DELTA_V = Quantity.parse("9400 m/s")  # LEO with gravity + drag losses


def delta_v_budget() -> dict[str, float]:
    """Return the stage Δv and the propellant fraction a 250 s stage needs for an orbital Δv."""
    stage_delta_v = rocket_delta_v(
        specific_impulse=SPECIFIC_IMPULSE,
        initial_mass=INITIAL_MASS,
        final_mass=FINAL_MASS,
    )
    orbital_fraction = rocket_propellant_mass_fraction(
        delta_v=ORBITAL_DELTA_V, specific_impulse=SPECIFIC_IMPULSE
    )
    return {
        "stage_delta_v_m_s": stage_delta_v.to("m/s").magnitude,
        "orbital_propellant_fraction": orbital_fraction,
    }


def main() -> None:
    d = delta_v_budget()
    print(f"stage Δv (mass ratio 3.33): {d['stage_delta_v_m_s']:.0f} m/s")
    print(
        f"propellant fraction for a 9400 m/s orbit on one 250 s stage: "
        f"{d['orbital_propellant_fraction']:.0%}"
    )
    print("  -> ~2% left for structure and payload -> single stage impossible, hence staging")


if __name__ == "__main__":
    main()
