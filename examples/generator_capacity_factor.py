"""Worked example: why a 2 MW wind turbine is not a 2 MW power plant.

A generator's nameplate is the most it can ever produce, not what it typically does, and for
intermittent sources the gap is enormous. The honest way to compare them is the capacity factor —
the energy actually produced over a period divided by what the nameplate would make running flat out
the whole time, CF = E/(P·t). It folds the wind's lulls, the sun's nights, and every derating into
one fraction.

This example puts three 2 MW nameplate generators side by side over a year (8,760 hours). The wind
turbine produces 6,000 MWh — a capacity factor of 0.34, typical onshore. A 2 MW solar array in the
same slot makes 3,500 MWh, a capacity factor of 0.20, because it is dark half the day and derated by
heat the other half. A gas plant of the same nameplate, run as baseload, delivers 15,800 MWh — a
capacity factor of 0.90. All three are "2 MW," but the gas plant does nearly three times the work
of the wind turbine and four and a half times the solar. The lesson is that nameplate says what a
source *can* do; the capacity factor says what it *will* do, and comparing renewables to firm power
on nameplate alone quietly overstates them by a factor of three.

Run it directly (``python examples/generator_capacity_factor.py``);
:func:`capacity_factors` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import capacity_factor
from anvilate.units import Quantity

RATED_POWER = Quantity.parse("2 MW")
YEAR = Quantity.parse("8760 hour")


def capacity_factors() -> dict[str, float]:
    """Return the capacity factor of a wind, solar, and baseload gas generator (equal nameplate)."""

    def cf(annual_mwh: float) -> float:
        return capacity_factor(
            energy_produced=Quantity(magnitude=annual_mwh, unit="MWh"),
            rated_power=RATED_POWER,
            period=YEAR,
        )

    return {
        "wind_cf": cf(6000.0),
        "solar_cf": cf(3500.0),
        "gas_cf": cf(15800.0),
    }


def main() -> None:
    c = capacity_factors()
    print(f"wind (6000 MWh/yr)  : capacity factor {c['wind_cf']:.2f}")
    print(f"solar (3500 MWh/yr) : capacity factor {c['solar_cf']:.2f}")
    print(f"gas baseload (15800): capacity factor {c['gas_cf']:.2f}")
    print("  -> all three are '2 MW'; the capacity factor says how much each actually delivers")


if __name__ == "__main__":
    main()
