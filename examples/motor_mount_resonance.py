"""Worked example: a resonance screen of a cantilevered motor mount, end to end.

Runs the deterministic vertical for a dynamics check with no LLM: a 0.5 kg motor
runs at 3000 rpm (50 Hz) on the end of a 300 mm cantilevered steel mounting
bracket. The bracket's tip stiffness comes from a T1 beam deflection, the mount's
fundamental frequency from the mass-on-spring relation, and a scorecard screens it
against the motor's running speed to catch a resonance.

Run it directly (``python examples/motor_mount_resonance.py``);
:func:`screen_motor_mount` is also exercised in the test suite.

The instructive result: the long, flexible bracket's fundamental frequency (~43
Hz) sits *below* the 50 Hz running speed, so the mount would resonate — the
scorecard reports FAIL rather than a silent green.
"""

from __future__ import annotations

from anvilate.analysis import (
    cantilever_end_load,
    frequency_scorecard,
    natural_frequency,
    rectangular_second_moment,
)
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

MOTOR_MASS = Quantity.parse("0.5 kg")
RUNNING_SPEED = Quantity.parse("50 Hz")  # 3000 rpm


def screen_motor_mount() -> Scorecard:
    """Screen the example motor mount for resonance and return the scorecard."""
    steel = default_materials_db().get("ASTM-A36")

    # The bracket tip stiffness k = F/delta, from a T1 cantilever deflection.
    reference_force = Quantity.parse("100 N")
    inertia = rectangular_second_moment(Quantity.parse("20 mm"), Quantity.parse("10 mm"))
    beam = cantilever_end_load(
        force=reference_force,
        length=Quantity.parse("300 mm"),
        second_moment=inertia,
        extreme_fibre=Quantity.parse("5 mm"),
        elastic_modulus=steel.elastic_modulus.quantity,
    )
    k_n_per_mm = reference_force.to("N").magnitude / beam.max_deflection.to("mm").magnitude
    stiffness = Quantity(magnitude=k_n_per_mm, unit="N/mm")

    fundamental = natural_frequency(stiffness=stiffness, mass=MOTOR_MASS)
    resonance_check = frequency_scorecard(
        "mount resonance",
        frequency=fundamental,
        min_frequency=RUNNING_SPEED,
    )
    return Scorecard(entries=(resonance_check,))


def main() -> None:
    card = screen_motor_mount()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
