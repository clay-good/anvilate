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
as unburned carbon; too much carries heat up the stack. The dimensionless way to say the same
thing is the equivalence ratio φ = AFR_stoich/AFR_actual = 1/(1 + EA): φ < 1 is a lean
(excess-air) mixture, φ = 1 stoichiometric, φ > 1 rich (fuel excess). The fuel composition is the
caller's from an ultimate analysis; the balances are here.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "actual_air_fuel_ratio",
    "excess_air_from_flue_oxygen",
    "equivalence_ratio",
    "equivalence_ratio_from_excess_air",
    "siegert_dry_flue_gas_loss",
    "combustion_efficiency",
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


def equivalence_ratio(
    *,
    stoichiometric_air_fuel_ratio: float,
    actual_air_fuel_ratio: float,
) -> float:
    """The equivalence ratio, φ = AFR_stoich/AFR_actual.

    The dimensionless measure of how rich or lean a mixture burns: φ =
    ``stoichiometric_air_fuel_ratio``/``actual_air_fuel_ratio``. φ < 1 is lean (excess air, the
    normal furnace condition), φ = 1 is stoichiometric, and φ > 1 is rich (fuel excess, incomplete
    combustion). It is the standard way to state the mixture strength independent of the particular
    fuel. Both ratios must be positive. Returns the dimensionless equivalence ratio.
    """
    if stoichiometric_air_fuel_ratio <= 0:
        raise ValueError("stoichiometric_air_fuel_ratio must be positive")
    if actual_air_fuel_ratio <= 0:
        raise ValueError("actual_air_fuel_ratio must be positive")
    return stoichiometric_air_fuel_ratio / actual_air_fuel_ratio


def equivalence_ratio_from_excess_air(*, excess_air_fraction: float) -> float:
    """The equivalence ratio from the excess air, φ = 1/(1 + EA).

    The equivalence ratio expressed directly from the ``excess_air_fraction`` EA: φ = 1/(1 + EA),
    the algebraic twin of :func:`equivalence_ratio` since AFR_actual = AFR_stoich·(1 + EA). Zero
    excess air is stoichiometric (φ = 1); 20% excess air gives φ ≈ 0.83 (lean). The excess-air
    fraction must be greater than −1. Returns the dimensionless equivalence ratio.
    """
    if excess_air_fraction <= -1.0:
        raise ValueError("excess_air_fraction must be greater than -1")
    return 1.0 / (1.0 + excess_air_fraction)


def siegert_dry_flue_gas_loss(
    *,
    flue_temperature: Quantity,
    combustion_air_temperature: Quantity,
    flue_oxygen_percent: float,
    siegert_factor: float,
) -> float:
    """The dry flue-gas heat loss by the Siegert formula, qA = f·(T_flue − T_air)/(21 − O₂%).

    The largest loss in a fuel-fired boiler is the heat that leaves up the stack in the hot, dry
    flue gas, and the Siegert formula estimates it from a flue-gas analysis:
    qA = ``siegert_factor``·(``flue_temperature`` − ``combustion_air_temperature``)/(21 −
    ``flue_oxygen_percent``), as a percentage of the fuel's heat input. The loss grows with a hotter
    stack (poor heat recovery) and with more excess air (higher flue O₂, which dilutes and carries
    away more heat). ``siegert_factor`` f is the fuel's constant (about 0.66 for natural gas, 0.68
    for oil, 0.74 for coal). Subtract the result from 100% with :func:`combustion_efficiency`.
    Returns the dry flue-gas loss as a percentage.
    """
    if not flue_temperature.has_dimension("[temperature]"):
        raise ValueError("flue_temperature must be a [temperature] quantity")
    if not combustion_air_temperature.has_dimension("[temperature]"):
        raise ValueError("combustion_air_temperature must be a [temperature] quantity")
    t_flue = flue_temperature.to("degC").magnitude
    t_air = combustion_air_temperature.to("degC").magnitude
    if t_flue <= t_air:
        raise ValueError("flue_temperature must exceed the combustion air temperature")
    if not 0 <= flue_oxygen_percent < 21:
        raise ValueError("flue_oxygen_percent must be in [0, 21)")
    if siegert_factor <= 0:
        raise ValueError("siegert_factor must be positive")
    return siegert_factor * (t_flue - t_air) / (21.0 - flue_oxygen_percent)


def combustion_efficiency(
    *,
    dry_flue_gas_loss_percent: float,
    other_losses_percent: float = 0.0,
) -> float:
    """The combustion (thermal) efficiency, η = 100 − qA − other losses.

    The fraction of the fuel's heat that stays in the boiler rather than escaping: 100% minus the
    ``dry_flue_gas_loss_percent`` qA (from :func:`siegert_dry_flue_gas_loss`, the dominant loss) and
    any ``other_losses_percent`` (radiation, blowdown, unburnt fuel — a couple of percent). A modern
    condensing gas boiler reaches the mid-90s; an old, poorly-tuned one runs in the 70s. Cutting the
    stack temperature or the excess air lifts it directly. Returns the efficiency as a percentage.
    """
    if dry_flue_gas_loss_percent < 0:
        raise ValueError("dry_flue_gas_loss_percent must be non-negative")
    if other_losses_percent < 0:
        raise ValueError("other_losses_percent must be non-negative")
    efficiency = 100.0 - dry_flue_gas_loss_percent - other_losses_percent
    if efficiency <= 0:
        raise ValueError("the losses given exceed 100% (check the inputs)")
    return efficiency
