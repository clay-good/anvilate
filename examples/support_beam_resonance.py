"""Worked example: the support's own mass moves a resonance check onto the peak.

A 50 kg machine running at 1320 rpm (22 Hz) sits at the middle of a simply-supported
steel support beam. A resonance screen asks whether the beam-plus-machine fundamental
frequency clears the running speed with margin -- a bounce mode that lands on the
excitation shakes the machine apart.

The trap is what mass you count. Treat the beam as a massless spring and only the
machine's 50 kg bounces on k = 48EI/L^3: the fundamental comes out at 24.7 Hz,
comfortably above the 22 Hz running speed (a 1.12 margin, passing a 1.1 criterion).
But the beam here weighs 30 kg, and a simply-supported beam contributes 17/35 of its
own mass to the mode (the Rayleigh share from its deflection shape). Adding that
14.6 kg drops the effective mass to 64.6 kg and the frequency to 21.7 Hz -- *below*
the running speed. The mode the massless estimate placed safely above the excitation
actually sits right on it.

The lesson is that a support's own mass is not negligible when it is comparable to
the mounted mass; a resonance screen that ignores it is optimistic exactly where it
must not be. The beam section and masses are declared inline.

Run it directly (``python examples/support_beam_resonance.py``);
:func:`screen_support_resonance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import simply_supported_center_mass_frequency
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

ELASTIC_MODULUS = Quantity.parse("200 GPa")
SECOND_MOMENT = Quantity.parse("1e6 mm**4")
SPAN = Quantity.parse("2000 mm")
MACHINE_MASS = Quantity.parse("50 kg")
BEAM_MASS = Quantity.parse("30 kg")
RUNNING_SPEED = Quantity.parse("22 Hz")
REQUIRED_SEPARATION = 1.1  # the fundamental must exceed the running speed by this factor


def screen_support_resonance() -> Scorecard:
    """Screen the beam-plus-machine fundamental frequency against the running speed,
    once ignoring the beam's mass and once including it (safety factor =
    fundamental / running speed, required >= 1.1)."""
    running = RUNNING_SPEED.to("Hz").magnitude
    common = {
        "elastic_modulus": ELASTIC_MODULUS,
        "second_moment": SECOND_MOMENT,
        "length": SPAN,
        "center_mass": MACHINE_MASS,
    }
    ignored = simply_supported_center_mass_frequency(**common)
    included = simply_supported_center_mass_frequency(**common, beam_mass=BEAM_MASS)
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "resonance margin (beam mass ignored)",
                computed=ignored.to("Hz").magnitude / running,
                required=REQUIRED_SEPARATION,
            ),
            ScorecardEntry.from_safety_factor(
                "resonance margin (beam mass included)",
                computed=included.to("Hz").magnitude / running,
                required=REQUIRED_SEPARATION,
            ),
        )
    )


def main() -> None:
    common = {
        "elastic_modulus": ELASTIC_MODULUS,
        "second_moment": SECOND_MOMENT,
        "length": SPAN,
        "center_mass": MACHINE_MASS,
    }
    ignored = simply_supported_center_mass_frequency(**common)
    included = simply_supported_center_mass_frequency(**common, beam_mass=BEAM_MASS)
    print(f"fundamental, beam mass ignored:   {ignored.to('Hz').magnitude:.1f} Hz")
    print(f"fundamental, beam mass included:  {included.to('Hz').magnitude:.1f} Hz")
    print(f"running speed:                    {RUNNING_SPEED.to('Hz').magnitude:.1f} Hz")
    print(screen_support_resonance())


if __name__ == "__main__":
    main()
