"""T1 analytical refrigeration and heat-pump checks (cycle performance, closed-form).

The machine behind a cooling coil is a refrigeration cycle, and how well it performs is measured by
its coefficient of performance — the heat it moves per unit of work it takes. Thermodynamics sets a
hard ceiling on it. A reversible (Carnot) cycle running between a cold reservoir at T_c and a hot
one at T_h can do no better than

    COP_cooling = T_c/(T_h − T_c)        COP_heating = T_h/(T_h − T_c),

with the temperatures absolute — and the heating COP is always exactly one more than the cooling
COP, because a heat pump delivers both the heat it pumped and the work it spent. A real cycle falls
short of that ceiling (its ratio to Carnot is the second-law efficiency), and its actual COP is
just the capacity it delivers over the compressor power it draws. The tighter the temperature lift
T_h − T_c, the higher the ceiling — which is why a heat pump loses efficiency on a cold day.
Temperatures are :class:`~anvilate.units.Quantity` values (pass them in kelvin); COPs are
dimensionless.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "carnot_cop_cooling",
    "carnot_cop_heating",
    "coefficient_of_performance",
]


def carnot_cop_cooling(*, cold_temperature: Quantity, hot_temperature: Quantity) -> float:
    """The Carnot (ideal) cooling coefficient of performance, COP = T_c/(T_h − T_c).

    The best cooling COP thermodynamics allows between a ``cold_temperature`` T_c (the evaporator /
    cold space) and a ``hot_temperature`` T_h (the condenser / heat rejection), both absolute:
    COP = T_c/(T_h − T_c). No real refrigerator or air conditioner beats it, and the smaller the
    lift T_h − T_c, the larger it is. Returns the dimensionless Carnot cooling COP.
    """
    _check(cold_temperature, "[temperature]", "cold_temperature")
    _check(hot_temperature, "[temperature]", "hot_temperature")
    t_c = cold_temperature.to("K").magnitude
    t_h = hot_temperature.to("K").magnitude
    if t_c <= 0 or t_h <= 0:
        raise ValueError("temperatures must be positive (absolute)")
    if t_h <= t_c:
        raise ValueError("hot_temperature must exceed cold_temperature")
    return t_c / (t_h - t_c)


def carnot_cop_heating(*, cold_temperature: Quantity, hot_temperature: Quantity) -> float:
    """The Carnot (ideal) heating coefficient of performance, COP = T_h/(T_h − T_c).

    The best heating COP of a heat pump moving heat from a ``cold_temperature`` T_c (the source) up
    to a ``hot_temperature`` T_h (the heated space), both absolute: COP = T_h/(T_h − T_c). It is
    always exactly one more than the cooling COP (see :func:`carnot_cop_cooling`), because the pump
    delivers both the heat it lifted and the work it consumed. Returns the dimensionless Carnot
    heating COP.
    """
    _check(cold_temperature, "[temperature]", "cold_temperature")
    _check(hot_temperature, "[temperature]", "hot_temperature")
    t_c = cold_temperature.to("K").magnitude
    t_h = hot_temperature.to("K").magnitude
    if t_c <= 0 or t_h <= 0:
        raise ValueError("temperatures must be positive (absolute)")
    if t_h <= t_c:
        raise ValueError("hot_temperature must exceed cold_temperature")
    return t_h / (t_h - t_c)


def coefficient_of_performance(*, capacity: Quantity, power_input: Quantity) -> float:
    """The actual coefficient of performance of a cycle, COP = Q/W.

    What a real machine achieves: the useful heat it moves — the cooling or heating ``capacity`` Q —
    over the ``power_input`` W its compressor draws. Compared against the Carnot ceiling
    (:func:`carnot_cop_cooling`/:func:`carnot_cop_heating`) it gives the second-law efficiency; a
    good vapor-compression system reaches roughly half of Carnot. Returns the dimensionless COP.
    """
    _check(capacity, "[power]", "capacity")
    _check(power_input, "[power]", "power_input")
    q = capacity.to("W").magnitude
    w = power_input.to("W").magnitude
    if q <= 0 or w <= 0:
        raise ValueError("capacity and power_input must be positive")
    return q / w


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
