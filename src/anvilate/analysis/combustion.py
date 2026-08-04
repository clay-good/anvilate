"""T1 analytical combustion checks (air-fuel ratio and excess air, closed-form).

Firing a boiler or furnace comes down to matching air to fuel, and a few mass balances carry it.

Burning a fuel completely needs a definite amount of air, fixed by the fuel's own chemistry: every
kilogram of carbon needs 2.667 kg of oxygen (to CO₂), every kilogram of hydrogen needs 8 kg (to
H₂O), and every kilogram of sulfur needs 1 kg (to SO₂), less whatever oxygen the fuel already
carries. Dividing that oxygen demand by air's oxygen mass fraction (0.232) gives the stoichiometric
air-fuel ratio from the fuel's ultimate analysis.

No real furnace runs at exactly stoichiometric — a little extra (excess) air ensures complete
burning. The amount is read straight from the flue gas: the leftover oxygen the burner did not use
is EA = O₂/(20.9 − O₂), the standard combustion-tuning relation. Too little excess air wastes fuel
as unburned carbon; too much carries heat up the stack. The fuel composition is the caller's from an
ultimate analysis; the balances are here.
"""

from __future__ import annotations

__all__ = [
    "actual_air_fuel_ratio",
    "excess_air_from_flue_oxygen",
    "stoichiometric_air_fuel_ratio",
]

_OXYGEN_MASS_FRACTION_AIR = 0.232  # kg O₂ per kg dry air
_O2_PER_CARBON = 2.6667  # kg O₂ per kg C (C → CO₂, 32/12)
_O2_PER_HYDROGEN = 8.0  # kg O₂ per kg H (2H₂ + O₂ → 2H₂O, 32/4)
_O2_PER_SULFUR = 1.0  # kg O₂ per kg S (S → SO₂, 32/32)


def stoichiometric_air_fuel_ratio(
    *,
    carbon: float,
    hydrogen: float,
    oxygen: float = 0.0,
    sulfur: float = 0.0,
) -> float:
    """The stoichiometric air-fuel ratio from a fuel's ultimate analysis (mass balance on oxygen).

    The mass of air to burn one mass of fuel completely, AFR = (2.667·C + 8·H + S − O)/0.232, from
    the fuel's ultimate-analysis mass
    fractions: ``carbon`` C, ``hydrogen`` H, ``oxygen`` O (already in the fuel, so it offsets the
    demand), and ``sulfur`` S. The oxygen demand is 2.667·C + 8·H + S − O kg per kg fuel, and
    dividing by air's 0.232 oxygen mass fraction gives the air. Fractions must be in [0, 1] and the
    net oxygen demand must be positive (a hydrocarbon fuel). Returns the dimensionless ratio by mass
    (~17.2 for methane, ~15.1 for octane).
    """
    for name, value in (
        ("carbon", carbon),
        ("hydrogen", hydrogen),
        ("oxygen", oxygen),
        ("sulfur", sulfur),
    ):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} mass fraction must be in [0, 1]; got {value}")
    oxygen_demand = (
        _O2_PER_CARBON * carbon + _O2_PER_HYDROGEN * hydrogen + _O2_PER_SULFUR * sulfur - oxygen
    )
    if oxygen_demand <= 0:
        raise ValueError("net oxygen demand must be positive (a combustible fuel)")
    return oxygen_demand / _OXYGEN_MASS_FRACTION_AIR


def excess_air_from_flue_oxygen(*, flue_oxygen_percent: float) -> float:
    """The excess-air fraction from the flue-gas oxygen, EA = O₂/(20.9 − O₂).

    Field combustion tuning reads the excess air from the oxygen left in the flue gas:
    EA = O₂/(20.9 − O₂), where ``flue_oxygen_percent`` is the measured dry-basis O₂ by volume (%).
    Zero flue oxygen is exactly stoichiometric; 3% O₂ is about 17% excess air, a typical gas-burner
    target. The value must be below 20.9 (ambient air). Returns the excess air as a fraction (0.17
    for 17%).
    """
    if not 0.0 <= flue_oxygen_percent < 20.9:
        raise ValueError(f"flue_oxygen_percent must be in [0, 20.9); got {flue_oxygen_percent}")
    return flue_oxygen_percent / (20.9 - flue_oxygen_percent)


def actual_air_fuel_ratio(
    *,
    stoichiometric_air_fuel_ratio: float,
    excess_air_fraction: float,
) -> float:
    """The actual air-fuel ratio a burner runs at, AFR_actual = AFR_stoich·(1 + EA).

    Running with excess air scales the stoichiometric ratio up: AFR_actual =
    ``stoichiometric_air_fuel_ratio``·(1 + ``excess_air_fraction``). At 20% excess air a methane
    burner's ratio rises from ~17.2 to ~20.6. The excess air fraction must be non-negative. Returns
    the dimensionless actual air-fuel ratio by mass.
    """
    if stoichiometric_air_fuel_ratio <= 0:
        raise ValueError("stoichiometric_air_fuel_ratio must be positive")
    if excess_air_fraction < 0:
        raise ValueError("excess_air_fraction must be non-negative")
    return stoichiometric_air_fuel_ratio * (1.0 + excess_air_fraction)
