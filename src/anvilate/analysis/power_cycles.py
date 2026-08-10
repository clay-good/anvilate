"""T1 analytical air-standard power-cycle efficiencies (closed-form).

The ideal thermal efficiency of a heat engine or gas turbine follows from its compression alone —
the air-standard cycles give clean closed forms that set the ceiling a real engine works toward.

The Otto cycle (the spark-ignition engine) depends only on the compression ratio r and the specific-
heat ratio γ: η = 1 − 1/r^(γ−1). Squeezing the charge harder raises efficiency, which is why engines
run as high a compression ratio as knock allows.

The Diesel cycle adds a cutoff ratio r_c (how far combustion extends the volume at constant
pressure): η = 1 − (1/r^(γ−1))·(r_c^γ − 1)/(γ·(r_c − 1)). At the same compression ratio a diesel is
slightly less efficient than an Otto cycle, but it tolerates far higher compression, so real
diesels win.

The Brayton cycle (the gas turbine) depends on the pressure ratio r_p:
η = 1 − 1/r_p^((γ−1)/γ). All three assume air as an ideal gas with constant specific heats; the
specific-heat ratio γ (≈ 1.4 for air) is the caller's.

Above all three sits the Carnot efficiency η = 1 − T_c/T_h — the ceiling *no* heat engine can beat,
set by the reservoir temperatures alone. It is the power-generation mirror of the Carnot COP in
:mod:`anvilate.analysis.refrigeration`, and dividing a real engine's efficiency by it gives the
second-law efficiency that grades the machine against that ceiling.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "brake_specific_fuel_consumption",
    "brake_thermal_efficiency",
    "brayton_cycle_efficiency",
    "carnot_efficiency",
    "diesel_cycle_efficiency",
    "heat_engine_second_law_efficiency",
    "otto_cycle_efficiency",
]


def otto_cycle_efficiency(*, compression_ratio: float, specific_heat_ratio: float = 1.4) -> float:
    """The air-standard Otto-cycle efficiency, η = 1 − 1/r^(γ−1).

    The ideal thermal efficiency of a spark-ignition engine from its ``compression_ratio`` r (the
    cylinder volume at bottom dead centre over that at top) and the ``specific_heat_ratio`` γ (≈ 1.4
    for air): η = 1 − 1/r^(γ−1). It depends on nothing but the compression ratio — the reason
    raising compression (until knock intervenes) is the efficiency lever. Returns the efficiency as
    a fraction.
    """
    if compression_ratio <= 1:
        raise ValueError("compression_ratio must be greater than 1")
    if specific_heat_ratio <= 1:
        raise ValueError("specific_heat_ratio must be greater than 1")
    return 1.0 - 1.0 / compression_ratio ** (specific_heat_ratio - 1.0)


def diesel_cycle_efficiency(
    *,
    compression_ratio: float,
    cutoff_ratio: float,
    specific_heat_ratio: float = 1.4,
) -> float:
    """The air-standard Diesel-cycle efficiency, η = 1 − (1/r^(γ−1))·(r_c^γ − 1)/(γ·(r_c − 1)).

    The ideal efficiency of a compression-ignition engine, from its ``compression_ratio`` r, the
    ``cutoff_ratio`` r_c (the volume ratio over which combustion adds heat at constant pressure),
    and the ``specific_heat_ratio`` γ: η = 1 − (1/r^(γ−1))·(r_c^γ − 1)/(γ·(r_c − 1)). The cutoff
    term is always greater than 1, so at equal compression a diesel is a little less than an Otto
    cycle — but diesels run much higher compression, so they win in practice. As r_c → 1 (heat added
    at constant volume) it reduces to the Otto efficiency. Returns the efficiency as a fraction.
    """
    if compression_ratio <= 1:
        raise ValueError("compression_ratio must be greater than 1")
    if cutoff_ratio <= 1:
        raise ValueError("cutoff_ratio must be greater than 1")
    if specific_heat_ratio <= 1:
        raise ValueError("specific_heat_ratio must be greater than 1")
    g = specific_heat_ratio
    cutoff_term = (cutoff_ratio**g - 1.0) / (g * (cutoff_ratio - 1.0))
    return 1.0 - cutoff_term / compression_ratio ** (g - 1.0)


def brayton_cycle_efficiency(*, pressure_ratio: float, specific_heat_ratio: float = 1.4) -> float:
    """The air-standard Brayton-cycle efficiency, η = 1 − 1/r_p^((γ−1)/γ).

    The ideal efficiency of a gas turbine from its ``pressure_ratio`` r_p (compressor discharge over
    inlet pressure) and the ``specific_heat_ratio`` γ: η = 1 − 1/r_p^((γ−1)/γ). A higher pressure
    ratio raises efficiency, though the useful work peaks at a finite ratio the temperature limit
    sets — a trade this ideal form does not show. Returns the efficiency as a fraction.
    """
    if pressure_ratio <= 1:
        raise ValueError("pressure_ratio must be greater than 1")
    if specific_heat_ratio <= 1:
        raise ValueError("specific_heat_ratio must be greater than 1")
    g = specific_heat_ratio
    return 1.0 - 1.0 / pressure_ratio ** ((g - 1.0) / g)


def carnot_efficiency(*, cold_temperature: Quantity, hot_temperature: Quantity) -> float:
    """The Carnot (ideal) heat-engine efficiency, η = 1 − T_c/T_h.

    The most work any heat engine can wring from heat flowing between a ``hot_temperature`` T_h (the
    source) and a ``cold_temperature`` T_c (the sink), both absolute: η = 1 − T_c/T_h. No real
    engine — Otto, Diesel, Brayton, or steam — beats it, and it depends on the reservoir
    temperatures alone, not on the working fluid or the cycle. It is why a higher combustion
    temperature and a colder sink are the only fundamental levers on efficiency, and it is the
    ceiling :func:`heat_engine_second_law_efficiency` grades a real engine against. Returns the
    dimensionless Carnot efficiency (0 to 1).
    """
    _check(cold_temperature, "[temperature]", "cold_temperature")
    _check(hot_temperature, "[temperature]", "hot_temperature")
    t_c = cold_temperature.to("K").magnitude
    t_h = hot_temperature.to("K").magnitude
    if t_c <= 0 or t_h <= 0:
        raise ValueError("temperatures must be positive (absolute)")
    if t_h <= t_c:
        raise ValueError("hot_temperature must exceed cold_temperature")
    return 1.0 - t_c / t_h


def heat_engine_second_law_efficiency(
    *,
    thermal_efficiency: float,
    carnot_efficiency: float,
) -> float:
    """The second-law (exergetic) efficiency of a heat engine, η_II = η/η_Carnot.

    How close a real engine comes to the thermodynamic ceiling: the ``thermal_efficiency`` η it
    actually achieves over the ``carnot_efficiency`` η_Carnot for the same reservoirs (from
    :func:`carnot_efficiency`). Unlike the thermal efficiency itself — which is bounded low whenever
    the reservoirs are close even for a perfect engine — the second-law efficiency isolates how good
    the *engine* is, independent of how favorable the temperatures are: a good large steam or
    combined-cycle plant sits around 0.7–0.8 of its Carnot limit. It cannot exceed 1 (that would
    beat Carnot). Returns the dimensionless efficiency.
    """
    if not 0.0 < thermal_efficiency < 1.0:
        raise ValueError(f"thermal_efficiency must be in (0, 1); got {thermal_efficiency}")
    if not 0.0 < carnot_efficiency < 1.0:
        raise ValueError(f"carnot_efficiency must be in (0, 1); got {carnot_efficiency}")
    if thermal_efficiency > carnot_efficiency:
        raise ValueError(
            "thermal_efficiency cannot exceed the Carnot efficiency (that would beat Carnot)"
        )
    return thermal_efficiency / carnot_efficiency


def brake_specific_fuel_consumption(
    *,
    fuel_mass_flow: Quantity,
    brake_power: Quantity,
) -> Quantity:
    """The brake specific fuel consumption, BSFC = m_dot_fuel / P_brake.

    How much fuel a real engine burns per unit of useful work: the ``fuel_mass_flow`` m_dot_fuel
    divided by the ``brake_power`` P delivered at the shaft, BSFC = m_dot_fuel/P. It is the standard
    field measure of engine economy — a modern diesel runs ~200 g/kWh, a gasoline engine ~250-350,
    and lower is better. Because it folds the fuel's energy content and the engine's efficiency into
    one number, it is what a dyno reports and what :func:`brake_thermal_efficiency` converts into a
    true efficiency once the fuel's heating value is known. Returns the BSFC in kg/J (convert to the
    familiar g/kWh with ``.to("g/(kW*hour)")``).
    """
    _check(fuel_mass_flow, "[mass]/[time]", "fuel_mass_flow")
    _check(brake_power, "[power]", "brake_power")
    m_dot = fuel_mass_flow.to("kg/s").magnitude
    p = brake_power.to("W").magnitude
    if m_dot < 0:
        raise ValueError("fuel_mass_flow must be non-negative")
    if p <= 0:
        raise ValueError("brake_power must be positive")
    return Quantity(magnitude=m_dot / p, unit="kg/J")


def brake_thermal_efficiency(
    *,
    brake_power: Quantity,
    fuel_mass_flow: Quantity,
    fuel_heating_value: Quantity,
) -> float:
    """The brake thermal efficiency, η = P_brake / (m_dot_fuel · LHV).

    The fraction of the fuel's chemical energy a real engine turns into shaft work: the
    ``brake_power`` P over the fuel energy burned per unit time, m_dot_fuel·LHV, from the
    ``fuel_mass_flow`` m_dot_fuel and the fuel's ``fuel_heating_value`` LHV (lower heating value,
    ~44 MJ/kg for gasoline or diesel). It equals 1/(BSFC·LHV) with the BSFC of
    :func:`brake_specific_fuel_consumption`, and is the measured efficiency to feed
    :func:`heat_engine_second_law_efficiency` — distinct from the ideal air-standard cycle
    efficiencies (Otto/Diesel/Brayton), which are the ceiling this works toward. Real engines reach
    ~0.30-0.45. Returns the dimensionless efficiency (0 to 1).
    """
    _check(brake_power, "[power]", "brake_power")
    _check(fuel_mass_flow, "[mass]/[time]", "fuel_mass_flow")
    _check(fuel_heating_value, "[energy]/[mass]", "fuel_heating_value")
    p = brake_power.to("W").magnitude
    m_dot = fuel_mass_flow.to("kg/s").magnitude
    lhv = fuel_heating_value.to("J/kg").magnitude
    if p <= 0:
        raise ValueError("brake_power must be positive")
    if m_dot <= 0:
        raise ValueError("fuel_mass_flow must be positive")
    if lhv <= 0:
        raise ValueError("fuel_heating_value must be positive")
    eta = p / (m_dot * lhv)
    if eta > 1.0:
        raise ValueError(
            "brake_power exceeds the fuel energy rate (η > 1 is impossible); check inputs"
        )
    return eta


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
