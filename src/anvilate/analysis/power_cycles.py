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

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_ENGINE_SOURCE = "the engine's specification sheet (compression, cutoff, and pressure ratios)"
_GAS_PROPERTY_SOURCE = "the working gas's specific-heat ratio from a property table"
_RESERVOIR_SOURCE = "the operating case's source and sink temperatures"
_TEST_SOURCE = "the engine dynamometer test record (brake power and fuel flow)"
_FUEL_SOURCE = "the fuel's certificate of analysis (lower heating value)"


class _PowerCyclesInputError(RefusalError, ValueError):
    """A power-cycle input that cannot be used without correction."""


def _power_cycles_refusal(message: str, *, subject: str, source: str) -> _PowerCyclesInputError:
    return _PowerCyclesInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _power_cycles_input_source(name: str) -> str:
    if name == "specific_heat_ratio":
        return _GAS_PROPERTY_SOURCE
    if name in {"carnot_efficiency", "cold_temperature", "hot_temperature"}:
        return _RESERVOIR_SOURCE
    if name in {"brake_power", "fuel_mass_flow", "net_work_per_cycle", "thermal_efficiency"}:
        return _TEST_SOURCE
    if name == "fuel_heating_value":
        return _FUEL_SOURCE
    return _ENGINE_SOURCE


__all__ = [
    "brake_specific_fuel_consumption",
    "brake_thermal_efficiency",
    "brayton_cycle_efficiency",
    "carnot_efficiency",
    "diesel_cycle_efficiency",
    "heat_engine_second_law_efficiency",
    "mean_effective_pressure",
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
    require_finite(compression_ratio, name="compression_ratio")
    require_finite(specific_heat_ratio, name="specific_heat_ratio")
    if compression_ratio <= 1:
        raise _power_cycles_refusal(
            "compression_ratio must be greater than 1",
            subject="compression_ratio",
            source=_ENGINE_SOURCE,
        )
    if specific_heat_ratio <= 1:
        raise _power_cycles_refusal(
            "specific_heat_ratio must be greater than 1",
            subject="specific_heat_ratio",
            source=_GAS_PROPERTY_SOURCE,
        )
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
    require_finite(compression_ratio, name="compression_ratio")
    require_finite(cutoff_ratio, name="cutoff_ratio")
    require_finite(specific_heat_ratio, name="specific_heat_ratio")
    if compression_ratio <= 1:
        raise _power_cycles_refusal(
            "compression_ratio must be greater than 1",
            subject="compression_ratio",
            source=_ENGINE_SOURCE,
        )
    if cutoff_ratio <= 1:
        raise _power_cycles_refusal(
            "cutoff_ratio must be greater than 1", subject="cutoff_ratio", source=_ENGINE_SOURCE
        )
    if specific_heat_ratio <= 1:
        raise _power_cycles_refusal(
            "specific_heat_ratio must be greater than 1",
            subject="specific_heat_ratio",
            source=_GAS_PROPERTY_SOURCE,
        )
    # The geometry the cycle is drawn on: V3 = r_c*V2 is where combustion ends, and it
    # cannot be past V1 = r*V2, which is bottom dead centre. Nothing enforced it, so a
    # cutoff ratio above the compression ratio returned a plausible-looking 0.161 at
    # (18, 25) and a *negative* efficiency at (18, 40) — a heat engine consuming work,
    # from a formula whose every individual guard had passed.
    if cutoff_ratio > compression_ratio:
        raise _power_cycles_refusal(
            f"cutoff_ratio ({cutoff_ratio}) cannot exceed compression_ratio "
            f"({compression_ratio}): combustion would end past bottom dead centre, which "
            "is not a cycle the air-standard analysis describes",
            subject="cutoff_ratio and compression_ratio",
            source=_ENGINE_SOURCE,
        )
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
    require_finite(pressure_ratio, name="pressure_ratio")
    require_finite(specific_heat_ratio, name="specific_heat_ratio")
    if pressure_ratio <= 1:
        raise _power_cycles_refusal(
            "pressure_ratio must be greater than 1", subject="pressure_ratio", source=_ENGINE_SOURCE
        )
    if specific_heat_ratio <= 1:
        raise _power_cycles_refusal(
            "specific_heat_ratio must be greater than 1",
            subject="specific_heat_ratio",
            source=_GAS_PROPERTY_SOURCE,
        )
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
        raise _power_cycles_refusal(
            "temperatures must be positive (absolute)",
            subject="cold_temperature and hot_temperature",
            source=_RESERVOIR_SOURCE,
        )
    if t_h <= t_c:
        raise _power_cycles_refusal(
            "hot_temperature must exceed cold_temperature",
            subject="cold_temperature and hot_temperature",
            source=_RESERVOIR_SOURCE,
        )
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
    require_finite(thermal_efficiency, name="thermal_efficiency")
    require_finite(carnot_efficiency, name="carnot_efficiency")
    if not 0.0 < thermal_efficiency < 1.0:
        raise _power_cycles_refusal(
            f"thermal_efficiency must be in (0, 1); got {thermal_efficiency}",
            subject="thermal_efficiency",
            source=_TEST_SOURCE,
        )
    if not 0.0 < carnot_efficiency < 1.0:
        raise _power_cycles_refusal(
            f"carnot_efficiency must be in (0, 1); got {carnot_efficiency}",
            subject="carnot_efficiency",
            source=_RESERVOIR_SOURCE,
        )
    if thermal_efficiency > carnot_efficiency:
        raise _power_cycles_refusal(
            "thermal_efficiency cannot exceed the Carnot efficiency (that would beat Carnot)",
            subject="thermal_efficiency and carnot_efficiency",
            source=_TEST_SOURCE,
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
        raise _power_cycles_refusal(
            "fuel_mass_flow must be non-negative", subject="fuel_mass_flow", source=_TEST_SOURCE
        )
    if p <= 0:
        raise _power_cycles_refusal(
            "brake_power must be positive", subject="brake_power", source=_TEST_SOURCE
        )
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
        raise _power_cycles_refusal(
            "brake_power must be positive", subject="brake_power", source=_TEST_SOURCE
        )
    if m_dot <= 0:
        raise _power_cycles_refusal(
            "fuel_mass_flow must be positive", subject="fuel_mass_flow", source=_TEST_SOURCE
        )
    if lhv <= 0:
        raise _power_cycles_refusal(
            "fuel_heating_value must be positive", subject="fuel_heating_value", source=_FUEL_SOURCE
        )
    eta = p / (m_dot * lhv)
    if eta > 1.0:
        raise _power_cycles_refusal(
            "brake_power exceeds the fuel energy rate (η > 1 is impossible); check inputs",
            subject="brake_power, fuel_mass_flow, and fuel_heating_value",
            source=_TEST_SOURCE,
        )
    return eta


def mean_effective_pressure(
    *,
    net_work_per_cycle: Quantity,
    displacement_volume: Quantity,
) -> Quantity:
    """The mean effective pressure, MEP = W_net / V_d.

    The constant pressure that, acting on the piston through one stroke, would produce the same net
    work a cycle actually delivers: the ``net_work_per_cycle`` W_net over the
    ``displacement_volume`` V_d, MEP = W_net/V_d. Because it divides out engine size, it is the
    fairest way to compare how hard engines of different displacement are worked — a
    naturally-aspirated gasoline engine peaks near 10 bar, a boosted one higher. Formed from brake
    work it is the BMEP a dyno reports; from the ideal cycle work it is the indicated MEP. Returns
    the MEP in kPa.
    """
    _check(net_work_per_cycle, "[energy]", "net_work_per_cycle")
    _check(displacement_volume, "[volume]", "displacement_volume")
    w = net_work_per_cycle.to("J").magnitude
    v_d = displacement_volume.to("m**3").magnitude
    if w <= 0:
        raise _power_cycles_refusal(
            "net_work_per_cycle must be positive", subject="net_work_per_cycle", source=_TEST_SOURCE
        )
    if v_d <= 0:
        raise _power_cycles_refusal(
            "displacement_volume must be positive",
            subject="displacement_volume",
            source=_ENGINE_SOURCE,
        )
    return Quantity(magnitude=w / v_d, unit="Pa").to("kPa")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _power_cycles_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_power_cycles_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _power_cycles_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_power_cycles_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
