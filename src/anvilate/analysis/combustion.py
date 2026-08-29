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

Sources: Turns, *An Introduction to Combustion*, and Cengel & Boles,
*Thermodynamics*, for the stoichiometry, heating-value and flue-gas relations.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "actual_air_fuel_ratio",
    "excess_air_from_flue_oxygen",
    "equivalence_ratio",
    "equivalence_ratio_from_excess_air",
    "siegert_dry_flue_gas_loss",
    "combustion_efficiency",
    "stoichiometric_air_fuel_ratio",
    "wobbe_index",
    "adiabatic_flame_temperature",
    "lower_heating_value",
]

_WATER_LATENT_HEAT_MJ_PER_KG = 2.442  # h_fg of water at 25 °C, MJ/kg

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
    if not isinstance(flue_temperature, Quantity):
        raise ValueError(
            f"flue_temperature must be a [temperature] quantity; got {flue_temperature!r}"
        )
    if not flue_temperature.has_dimension("[temperature]"):
        raise ValueError("flue_temperature must be a [temperature] quantity")
    if not isinstance(combustion_air_temperature, Quantity):
        raise ValueError(
            f"combustion_air_temperature must be a [temperature] quantity; "
            f"got {combustion_air_temperature!r}"
        )
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


def wobbe_index(*, higher_heating_value: Quantity, gas_specific_gravity: float) -> Quantity:
    """The Wobbe index, W = HHV/√(SG), the gas-interchangeability number.

    Two fuel gases fire a given burner interchangeably — same heat output at the same nozzle
    pressure — when they share a Wobbe index, not merely a heating value: the flow through a fixed
    orifice scales as 1/√(density), so the delivered energy tracks HHV/√(SG). From the *volumetric*
    ``higher_heating_value`` HHV (energy per unit volume) and the ``gas_specific_gravity`` SG (gas
    density relative to air), W = HHV/√(SG). It is the number gas utilities hold within a band so
    appliances run safely on gas from any source (pipeline, LNG, biogas). Returns the Wobbe index in
    the same volumetric-energy units as the heating value.
    """
    if not isinstance(higher_heating_value, Quantity):
        raise ValueError(
            f"higher_heating_value must be a [energy]/[volume] quantity; "
            f"got {higher_heating_value!r}"
        )
    if not higher_heating_value.has_dimension("[energy]/[volume]"):
        raise ValueError(
            "higher_heating_value must be a volumetric energy density (energy per volume); got "
            f"{higher_heating_value.dimensionality} ({higher_heating_value})"
        )
    if gas_specific_gravity <= 0:
        raise ValueError("gas_specific_gravity must be positive")
    hhv = higher_heating_value.to("MJ/m**3").magnitude
    return Quantity(magnitude=hhv / sqrt(gas_specific_gravity), unit="MJ/m**3")


def lower_heating_value(
    *,
    higher_heating_value: Quantity,
    water_mass_per_fuel_mass: float,
    latent_heat: Quantity | None = None,
) -> Quantity:
    """The lower (net) heating value, LHV = HHV − w·h_fg.

    The higher heating value counts the latent heat recovered by condensing the combustion water;
    the lower (net) value — the practical one for a non-condensing appliance whose flue leaves the
    water as vapour — subtracts it: LHV = HHV − w·h_fg, from the ``higher_heating_value`` HHV, the
    ``water_mass_per_fuel_mass`` w (kg of water vapour produced per kg of fuel, from the fuel's
    hydrogen content), and the water latent heat ``latent_heat`` h_fg (default 2.442 MJ/kg at
    25 °C).
    Hydrogen-rich fuels (natural gas) lose the most: methane's LHV is about 10% below its HHV.
    ``higher_heating_value`` and ``latent_heat`` are per-unit-mass energies. Returns the LHV in the
    same mass-specific units.
    """
    if not isinstance(higher_heating_value, Quantity):
        raise ValueError(
            f"higher_heating_value must be a [energy]/[mass] quantity; got {higher_heating_value!r}"
        )
    if not higher_heating_value.has_dimension("[energy]/[mass]"):
        raise ValueError(
            "higher_heating_value must be a mass-specific energy (energy per mass); got "
            f"{higher_heating_value.dimensionality} ({higher_heating_value})"
        )
    if water_mass_per_fuel_mass < 0:
        raise ValueError("water_mass_per_fuel_mass must be non-negative")
    if latent_heat is None:
        h_fg = _WATER_LATENT_HEAT_MJ_PER_KG
    else:
        if not isinstance(latent_heat, Quantity):
            raise ValueError(f"latent_heat must be a [energy]/[mass] quantity; got {latent_heat!r}")
        if not latent_heat.has_dimension("[energy]/[mass]"):
            raise ValueError(
                "latent_heat must be a mass-specific energy (energy per mass); got "
                f"{latent_heat.dimensionality} ({latent_heat})"
            )
        h_fg = latent_heat.to("MJ/kg").magnitude
    hhv = higher_heating_value.to("MJ/kg").magnitude
    lhv = hhv - water_mass_per_fuel_mass * h_fg
    if lhv <= 0:
        raise ValueError(
            "the water latent-heat term exceeds the higher heating value (LHV ≤ 0); check inputs"
        )
    return Quantity(magnitude=lhv, unit="MJ/kg")


def adiabatic_flame_temperature(
    *,
    lower_heating_value: Quantity,
    air_fuel_ratio: float,
    product_specific_heat: Quantity,
    inlet_temperature: Quantity,
) -> Quantity:
    """The constant-c_p adiabatic flame temperature, T_ad = T₀ + LHV/[(1 + AFR)·c_p].

    The temperature the products would reach if every joule released stayed in them. The module
    already computes both inputs it needs — the ``lower_heating_value`` LHV from
    :func:`lower_heating_value` and the ``air_fuel_ratio`` AFR from
    :func:`stoichiometric_air_fuel_ratio` or :func:`actual_air_fuel_ratio` — but stopped short of
    the number those two exist to produce. Burning 1 kg of fuel with AFR kg of air makes (1 + AFR)
    kg of products, so the release LHV is spread over that mass at the mean
    ``product_specific_heat`` c_p, lifting them from the ``inlet_temperature`` T₀:
    T_ad = T₀ + LHV/[(1 + AFR)·c_p].

    This is what sizes refractory, picks burner and liner alloys, and sets the NOx expectation,
    and it is the lever excess air pulls: the heat is fixed but the mass to heat is not, so going
    from stoichiometric AFR = 15 to 20% excess air at AFR = 18 drops a 2486 K flame to 2140 K.
    Treat it as an upper bound — it is adiabatic (no wall or radiation loss) and takes c_p as
    constant, where a real flame both loses heat and dissociates CO₂ and H₂O endothermically above
    roughly 2000 K, so measured temperatures run several hundred kelvin below this. Temperatures
    must be absolute. Returns the adiabatic flame temperature in K.
    """
    if not isinstance(lower_heating_value, Quantity):
        raise ValueError(
            f"lower_heating_value must be a [energy]/[mass] quantity; got {lower_heating_value!r}"
        )
    if not lower_heating_value.has_dimension("[energy]/[mass]"):
        raise ValueError(
            "lower_heating_value must be a mass-specific energy (energy per mass); got "
            f"{lower_heating_value.dimensionality} ({lower_heating_value})"
        )
    if not isinstance(product_specific_heat, Quantity):
        raise ValueError(
            f"product_specific_heat must be a [energy]/([mass]*[temperature]) quantity; "
            f"got {product_specific_heat!r}"
        )
    if not product_specific_heat.has_dimension("[energy]/([mass]*[temperature])"):
        raise ValueError(
            "product_specific_heat must be a specific heat (energy per mass per temperature); got "
            f"{product_specific_heat.dimensionality} ({product_specific_heat})"
        )
    if not isinstance(inlet_temperature, Quantity):
        raise ValueError(
            f"inlet_temperature must be a [temperature] quantity; got {inlet_temperature!r}"
        )
    if not inlet_temperature.has_dimension("[temperature]"):
        raise ValueError(
            "inlet_temperature must be a temperature; got "
            f"{inlet_temperature.dimensionality} ({inlet_temperature})"
        )
    lhv = lower_heating_value.to("J/kg").magnitude
    c_p = product_specific_heat.to("J/(kg*K)").magnitude
    t_0 = inlet_temperature.to("K").magnitude
    if lhv <= 0:
        raise ValueError("lower_heating_value must be positive")
    if air_fuel_ratio <= 0:
        raise ValueError("air_fuel_ratio must be positive")
    if c_p <= 0:
        raise ValueError("product_specific_heat must be positive")
    if t_0 <= 0:
        raise ValueError("inlet_temperature must be a positive absolute temperature")
    return Quantity(magnitude=t_0 + lhv / ((1.0 + air_fuel_ratio) * c_p), unit="K")
