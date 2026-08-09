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
    "second_law_efficiency",
    "refrigeration_effect",
    "compressor_work_of_compression",
    "refrigerant_mass_flow_rate",
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


def second_law_efficiency(*, actual_cop: float, carnot_cop: float) -> float:
    """The second-law (exergetic) efficiency of a cycle, η_II = COP/COP_Carnot.

    How close a real machine comes to the thermodynamic ceiling: the ``actual_cop`` (from
    :func:`coefficient_of_performance`) over the ``carnot_cop`` for the same reservoirs (from
    :func:`carnot_cop_cooling` or :func:`carnot_cop_heating`). Unlike the COP itself — which shrinks
    as the temperature lift grows even for a perfect machine — the second-law efficiency isolates
    how good the *machine* is, independent of how hard the duty is: a good vapor-compression chiller
    sits near 0.5, a poor one well below. It cannot exceed 1 (that would beat Carnot). Returns the
    dimensionless efficiency.
    """
    if actual_cop <= 0:
        raise ValueError("actual_cop must be positive")
    if carnot_cop <= 0:
        raise ValueError("carnot_cop must be positive")
    if actual_cop > carnot_cop:
        raise ValueError(
            "actual_cop cannot exceed the Carnot COP (that would beat the ideal cycle)"
        )
    return actual_cop / carnot_cop


def refrigeration_effect(
    *,
    evaporator_inlet_enthalpy: Quantity,
    evaporator_outlet_enthalpy: Quantity,
) -> Quantity:
    """The refrigeration effect per unit mass, q_L = h_out − h_in across the evaporator.

    The useful cooling each kilogram of refrigerant carries away in the evaporator: q_L =
    ``evaporator_outlet_enthalpy`` − ``evaporator_inlet_enthalpy`` (h₁ − h₄ in cycle notation, the
    outlet being the compressor-inlet vapor and the inlet the low-quality mixture leaving the
    expansion valve). It is the numerator of the cycle COP and, divided into a cooling load, sets
    the refrigerant flow (see :func:`refrigerant_mass_flow_rate`). The outlet enthalpy must exceed
    the inlet (the refrigerant absorbs heat). Returns the effect in kJ/kg.
    """
    _check(evaporator_inlet_enthalpy, "[energy]/[mass]", "evaporator_inlet_enthalpy")
    _check(evaporator_outlet_enthalpy, "[energy]/[mass]", "evaporator_outlet_enthalpy")
    h_in = evaporator_inlet_enthalpy.to("kJ/kg").magnitude
    h_out = evaporator_outlet_enthalpy.to("kJ/kg").magnitude
    if h_out <= h_in:
        raise ValueError("evaporator_outlet_enthalpy must exceed the inlet (heat is absorbed)")
    return Quantity(magnitude=h_out - h_in, unit="kJ/kg")


def compressor_work_of_compression(
    *,
    compressor_inlet_enthalpy: Quantity,
    compressor_outlet_enthalpy: Quantity,
) -> Quantity:
    """The compressor work per unit mass, w_c = h_out − h_in across the compressor.

    The shaft work each kilogram of refrigerant costs in the compressor: w_c =
    ``compressor_outlet_enthalpy`` − ``compressor_inlet_enthalpy`` (h₂ − h₁), the enthalpy rise as
    the vapor is squeezed from evaporator to condenser pressure. It is the denominator of the cycle
    COP (COP = q_L/w_c with the :func:`refrigeration_effect`), and the condenser must reject their
    sum q_H = q_L + w_c. The outlet enthalpy must exceed the inlet (work is added). Returns the work
    in kJ/kg.
    """
    _check(compressor_inlet_enthalpy, "[energy]/[mass]", "compressor_inlet_enthalpy")
    _check(compressor_outlet_enthalpy, "[energy]/[mass]", "compressor_outlet_enthalpy")
    h_in = compressor_inlet_enthalpy.to("kJ/kg").magnitude
    h_out = compressor_outlet_enthalpy.to("kJ/kg").magnitude
    if h_out <= h_in:
        raise ValueError("compressor_outlet_enthalpy must exceed the inlet (work is added)")
    return Quantity(magnitude=h_out - h_in, unit="kJ/kg")


def refrigerant_mass_flow_rate(
    *,
    cooling_capacity: Quantity,
    refrigeration_effect: Quantity,
) -> Quantity:
    """The refrigerant circulation rate, ṁ = Q_L/q_L.

    The mass of refrigerant a cycle must circulate to meet a cooling load: ṁ =
    ``cooling_capacity`` Q_L divided by the ``refrigeration_effect`` q_L (from
    :func:`refrigeration_effect`). It sizes the compressor's swept volume and the line diameters —
    a small refrigeration effect (a low-lift or wet cycle) demands a high flow for the same duty.
    Returns the mass flow rate in kg/s.
    """
    _check(cooling_capacity, "[power]", "cooling_capacity")
    _check(refrigeration_effect, "[energy]/[mass]", "refrigeration_effect")
    q = cooling_capacity.to("kW").magnitude
    qe = refrigeration_effect.to("kJ/kg").magnitude
    if q <= 0:
        raise ValueError("cooling_capacity must be positive")
    if qe <= 0:
        raise ValueError("refrigeration_effect must be positive")
    return Quantity(magnitude=q / qe, unit="kg/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
