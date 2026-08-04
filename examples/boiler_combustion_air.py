"""Worked example: the combustion air a gas boiler needs, and reading its tune from the flue.

Tuning a burner is a balance: too little air leaves fuel unburned, too much air carries heat up the
stack. This example works both sides of that balance for a natural-gas (methane) boiler. First it
computes the stoichiometric air-fuel ratio from the fuel's ultimate analysis — for methane, about
17.2 kg of air per kg of fuel — the exact air for complete combustion with nothing to spare. Then it
turns to the field measurement a technician actually makes: the oxygen left in the flue gas. A
reading of 3% O₂ works back to about 17% excess air, a healthy target for a gas burner, and the
example scales the stoichiometric ratio up to the actual air the boiler is really pulling. The two
directions meet in the middle — the chemistry sets the floor, the flue reading confirms the tune.

Run it directly (``python examples/boiler_combustion_air.py``);
:func:`combustion_tune` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    actual_air_fuel_ratio,
    excess_air_from_flue_oxygen,
    stoichiometric_air_fuel_ratio,
)

# Methane (CH4) ultimate analysis by mass: C = 12/16, H = 4/16.
METHANE_CARBON = 0.7487
METHANE_HYDROGEN = 0.2513
FLUE_OXYGEN_PERCENT = 3.0


def combustion_tune() -> dict[str, float]:
    """Return the stoichiometric AFR, the excess air from the flue O2, and the actual AFR."""
    stoich = stoichiometric_air_fuel_ratio(carbon=METHANE_CARBON, hydrogen=METHANE_HYDROGEN)
    excess = excess_air_from_flue_oxygen(flue_oxygen_percent=FLUE_OXYGEN_PERCENT)
    actual = actual_air_fuel_ratio(stoichiometric_air_fuel_ratio=stoich, excess_air_fraction=excess)
    return {
        "stoichiometric_afr": stoich,
        "excess_air_percent": excess * 100.0,
        "actual_afr": actual,
    }


def main() -> None:
    t = combustion_tune()
    print(f"stoichiometric air-fuel ratio : {t['stoichiometric_afr']:.1f} kg air / kg fuel")
    print(f"excess air from 3% flue O2    : {t['excess_air_percent']:.0f}%")
    print(f"actual air-fuel ratio         : {t['actual_afr']:.1f} kg air / kg fuel")
    print("  -> chemistry sets the stoichiometric floor; the flue O2 reading confirms the tune")


if __name__ == "__main__":
    main()
