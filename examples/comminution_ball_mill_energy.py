"""Worked example: grinding energy for a ball mill by Bond's law, cross-checked against Rittinger.

A ball mill grinds ore from a feed that is 80% finer than 10 mm (F80 = 10,000 µm) down to a product
80% passing 100 µm. For an ore with a Bond work index of 12 kWh/tonne, how much grinding energy does
that take, and how does the fine-grinding Rittinger picture compare?

Bond's law gives W = 12·(10/√100 − 10/√10000) = 10.8 kWh/tonne — the number used to size the mill
motor. Rittinger's law, weighting the new surface created, is shown alongside for the same size
reduction (with an illustrative constant) to show that the fine end dominates its estimate.

Run it directly (``python examples/comminution_ball_mill_energy.py``);
:func:`ball_mill_grinding_energy` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    bond_comminution_work,
    rittinger_comminution_energy,
)
from anvilate.units import Quantity

BOND_WORK_INDEX = Quantity.parse("12 kW*hour/tonne")
FEED_80 = Quantity.parse("10000 um")
PRODUCT_80 = Quantity.parse("100 um")
RITTINGER_CONSTANT = Quantity.parse("1.0 J*m/kg")


def ball_mill_grinding_energy() -> dict[str, float]:
    """Return the Bond grinding work (kWh/tonne) and a Rittinger specific energy (kJ/kg)."""
    bond = bond_comminution_work(
        bond_work_index=BOND_WORK_INDEX,
        feed_size_80=FEED_80,
        product_size_80=PRODUCT_80,
    )
    rittinger = rittinger_comminution_energy(
        rittinger_constant=RITTINGER_CONSTANT,
        feed_size=FEED_80,
        product_size=PRODUCT_80,
    )
    return {
        "bond_work_kwh_per_tonne": bond.to("kW*hour/tonne").magnitude,
        "rittinger_energy_kj_per_kg": rittinger.to("kJ/kg").magnitude,
    }


def main() -> None:
    d = ball_mill_grinding_energy()
    print("Ball mill, F80 = 10 mm -> P80 = 100 um, Wi = 12 kWh/t:")
    print(f"  Bond grinding work    : {d['bond_work_kwh_per_tonne']:.2f} kWh/tonne")
    print(f"  Rittinger (illustr.)  : {d['rittinger_energy_kj_per_kg']:.2f} kJ/kg")


if __name__ == "__main__":
    main()
