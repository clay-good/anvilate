"""Worked example: a ruggedized lens assembly under a declared shock and vibration environment.

A 25 g lens rides a 30 g, 11 ms half-sine shock, and its focus screw is set once and left
in a vibrating vehicle. Three screens follow from that environment:

- the retainer must hold the lens against the shock, so its preload is the lens's weight
  at 30 g, m·a·g₀, and on a sharp 1 mm edge that puts 7.72 MPa of tension into the glass
  against a 7 MPa allowable;
- the lens cell, at 600 Hz, swings 22.0 µm under the shock across a 15 µm radial gap;
- and the focus screw reaches its 120 µm correction, but nothing holds it in vibration,
  where a threaded adjustment backs off whatever its static friction.

All three fail as drawn. The repairs are the ordinary ones: a 3 mm edge radius on the
retainer brings the tension to 4.57 MPa, a 30 µm gap clears the swing, and a jam nut
holds the screw. The repaired card passes.

Run it directly (``python examples/ruggedized_shock_assembly.py``); :func:`card` and
:func:`repaired_card` are also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis.optomechanics import (
    AdjustmentMechanism,
    adjustment_scorecard,
    dynamic_clearance_scorecard,
    glass_contact_stress_scorecard,
    retention_preload,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

q = Quantity.parse
SHOCK_G = 30.0
LENS_MASS = q("25 g")


def _card(*, gap: str, locked: bool, edge_radius: str) -> Scorecard:
    # The retainer must hold the lens against the shock, so the preload is the shock's.
    preload = retention_preload(mass=LENS_MASS, acceleration=SHOCK_G)
    focus = AdjustmentMechanism(
        mechanism="focus screw",
        resolution=q("2 µm"),
        hysteresis=q("5 µm"),
        travel=q("200 µm"),
        locked=locked,
        screw_mean_diameter=q("3 mm"),
        screw_lead=q("0.35 mm"),
        friction_coefficient=0.15,
    )
    return Scorecard(
        entries=(
            glass_contact_stress_scorecard(
                "lens retainer contact",
                preload=preload,
                contact_diameter=q("20 mm"),
                glass_radius=q("40 mm"),
                mount_radius=q(edge_radius),
                glass_modulus=q("82 GPa"),
                glass_poisson=0.206,
                mount_modulus=q("69 GPa"),
                mount_poisson=0.33,
                allowable_tensile_stress=q("7 MPa"),
            ),
            dynamic_clearance_scorecard(
                "lens cell radial gap",
                natural_frequency=q("600 Hz"),
                peak_acceleration=SHOCK_G,
                pulse_duration=q("11 ms"),
                gap=q(gap),
            ),
            adjustment_scorecard(
                "focus adjustment",
                mechanism=focus,
                required_correction=q("120 µm"),
                vibration=True,
            ),
        )
    )


def card() -> Scorecard:
    """The assembly as drawn: a sharp retainer edge, a 15 µm gap, a friction-held screw."""
    return _card(gap="15 µm", locked=False, edge_radius="1 mm")


def repaired_card() -> Scorecard:
    """The repair: a 3 mm retainer edge radius, a 30 µm gap, and a jam nut on the screw."""
    return _card(gap="30 µm", locked=True, edge_radius="3 mm")


def main() -> None:
    for label, scorecard in (("as drawn", card()), ("repaired", repaired_card())):
        print(f"{label}: {scorecard.status.value}")
        for entry in scorecard.entries:
            print(f"  {entry}")


if __name__ == "__main__":
    main()
