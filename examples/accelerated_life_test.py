"""Worked example: an accelerated life test read through the Arrhenius law.

Aging is thermally activated, so running a part hot ages it faster in a predictable way — the basis
of accelerated life testing. Two Arrhenius questions size such a test: how much faster does the
failure mechanism run at the elevated stress temperature (the acceleration factor that converts oven
hours to field years), and, if the mechanism's activation energy is unknown, what value do two
measured rates imply.

This example uses a mechanism with an 80 kJ/mol activation energy. Between a 55 C (328 K) field
condition and an 85 C (358 K) oven, the acceleration factor is about 11.7 — every hour in the oven
stands in for roughly 11.7 field hours, so a 1000-hour oven run probes about 11,700 field hours.
Working the inverse, if a test instead measured rate constants that rose by 11.7x over that same
30 C span, the fitted activation energy comes back to about 80 kJ/mol, confirming the mechanism. The
example reports the acceleration factor and the activation energy recovered from the rate ratio.

Run it directly (``python examples/accelerated_life_test.py``);
:func:`accelerated_test` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import arrhenius_activation_energy, arrhenius_rate_ratio
from anvilate.units import Quantity

ACTIVATION_ENERGY = Quantity.parse("80 kJ/mol")
FIELD_TEMPERATURE = Quantity(magnitude=328.15, unit="K")  # 55 C
OVEN_TEMPERATURE = Quantity(magnitude=358.15, unit="K")  # 85 C


def accelerated_test() -> dict[str, float]:
    """Return the oven-to-field acceleration factor and the Ea recovered from that rate ratio."""
    factor = arrhenius_rate_ratio(
        activation_energy=ACTIVATION_ENERGY,
        temperature_low=FIELD_TEMPERATURE,
        temperature_high=OVEN_TEMPERATURE,
    )
    recovered_ea = arrhenius_activation_energy(
        rate_constant_low=Quantity(magnitude=1.0, unit="1/s"),
        rate_constant_high=Quantity(magnitude=factor, unit="1/s"),
        temperature_low=FIELD_TEMPERATURE,
        temperature_high=OVEN_TEMPERATURE,
    )
    return {
        "acceleration_factor": factor,
        "recovered_activation_energy_kj_mol": recovered_ea.to("kJ/mol").magnitude,
    }


def main() -> None:
    d = accelerated_test()
    print(f"acceleration factor (55 C -> 85 C): {d['acceleration_factor']:.1f}x")
    print(
        f"activation energy from rate ratio: {d['recovered_activation_energy_kj_mol']:.0f} kJ/mol"
    )


if __name__ == "__main__":
    main()
