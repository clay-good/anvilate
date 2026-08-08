"""Worked example: the three faces of electromagnetic induction.

A changing magnetic flux makes a voltage, and it shows up three ways: a conductor moving through a
field, a coil linking a changing flux, and a coil fighting a change in its own current. This example
works one of each.

A 0.2 m rod sliding at 10 m/s across a 0.5 T field develops a motional EMF of 1.0 V — the output of
a simple generator. A 100-turn coil whose flux changes by 0.01 Wb in 0.1 s sees a Faraday EMF of
10 V. And a 0.5 H inductor whose current changes by 2 A in 10 ms produces a 100 V self-induced
back-EMF — the spike that appears when an inductive load is switched off. This example reports the
motional EMF, the Faraday EMF, and the self-induced EMF.

Run it directly (``python examples/generator_induction.py``);
:func:`induction_voltages` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    faraday_induced_emf,
    motional_emf,
    self_induced_emf,
)
from anvilate.units import Quantity


def induction_voltages() -> dict[str, float]:
    """Return the motional EMF, the Faraday EMF, and the self-induced EMF."""
    motional = motional_emf(
        magnetic_flux_density=Quantity(magnitude=0.5, unit="T"),
        conductor_length=Quantity(magnitude=0.2, unit="m"),
        velocity=Quantity(magnitude=10.0, unit="m/s"),
    )
    faraday = faraday_induced_emf(
        turns=100.0,
        flux_change=Quantity(magnitude=0.01, unit="Wb"),
        time_interval=Quantity(magnitude=0.1, unit="s"),
    )
    back_emf = self_induced_emf(
        inductance=Quantity(magnitude=0.5, unit="H"),
        current_change=Quantity(magnitude=2.0, unit="A"),
        time_interval=Quantity(magnitude=0.01, unit="s"),
    )
    return {
        "motional_emf_v": motional.to("V").magnitude,
        "faraday_emf_v": faraday.to("V").magnitude,
        "self_induced_emf_v": back_emf.to("V").magnitude,
    }


def main() -> None:
    d = induction_voltages()
    print(f"motional EMF (rod generator): {d['motional_emf_v']:.2f} V")
    print(f"Faraday EMF (changing flux): {d['faraday_emf_v']:.1f} V")
    print(f"self-induced back-EMF: {d['self_induced_emf_v']:.0f} V")


if __name__ == "__main__":
    main()
