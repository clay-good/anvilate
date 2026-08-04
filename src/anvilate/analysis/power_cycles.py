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


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
