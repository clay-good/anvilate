"""T1 analytical real-gas (non-ideal) behaviour (closed-form).

The ideal-gas law PV = nRT of :mod:`anvilate.analysis.ideal_gas` assumes molecules with no size and
no attraction. Real gases deviate — most at high pressure and near their condensation temperature —
and screening a compressor, a storage cylinder, or a natural-gas line at those conditions needs the
correction. This module supplies the two standard ways to carry it: the empirical compressibility
factor and the Van der Waals equation of state.

The compressibility factor Z = P·v̄/(R·T) measures the deviation directly — Z = 1 is ideal, Z < 1
means attraction has pulled the gas denser than ideal (the usual case at moderate pressure), Z > 1
means finite molecular volume dominates (very high pressure). Read Z off a generalized chart at the
reduced conditions and the real molar volume follows as v̄ = Z·R·T/P, the ideal volume scaled by Z.
The Van der Waals equation P = R·T/(v̄ − b) − a/v̄² predicts the pressure from first principles
instead: the covolume b shrinks the space the molecules move in, and the cohesion term a/v̄² is the
inward pull that lowers the wall pressure. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values; temperatures must be absolute.

Sources: Perry's *Chemical Engineers' Handbook* and Cengel & Boles,
*Thermodynamics*, for the compressibility-factor and Redlich-Kwong / Peng-Robinson
equation-of-state relations.
"""

from __future__ import annotations

from ..units import Quantity

_GAS_CONSTANT = 8.314462618  # J/(mol*K), universal

__all__ = [
    "compressibility_factor",
    "real_gas_molar_volume",
    "reduced_pressure",
    "reduced_temperature",
    "van_der_waals_cohesion_a",
    "van_der_waals_covolume_b",
    "van_der_waals_pressure",
]


def compressibility_factor(
    *,
    pressure: Quantity,
    molar_volume: Quantity,
    temperature: Quantity,
) -> float:
    """The compressibility factor, Z = P·v̄/(R·T).

    The dimensionless deviation of a real gas from ideal behaviour: Z = ``pressure`` P ·
    ``molar_volume`` v̄ / (R·``temperature`` T). Z = 1 is the ideal-gas value; Z < 1 (the common
    case at moderate pressure) means intermolecular attraction has made the gas denser than ideal,
    and Z > 1 (very high pressure) means finite molecular volume dominates. It is the factor that
    turns PV = nRT into PV = ZnRT. Temperature must be absolute. Returns the dimensionless Z.
    """
    _check(pressure, "[pressure]", "pressure")
    _check(molar_volume, "[volume]/[substance]", "molar_volume")
    _check(temperature, "[temperature]", "temperature")
    p = pressure.to("Pa").magnitude
    v = molar_volume.to("m**3/mol").magnitude
    t = temperature.to("K").magnitude
    if p <= 0 or v <= 0 or t <= 0:
        raise ValueError("pressure, molar_volume, and temperature must be positive")
    return p * v / (_GAS_CONSTANT * t)


def real_gas_molar_volume(
    *,
    pressure: Quantity,
    temperature: Quantity,
    compressibility_factor: float,
) -> Quantity:
    """The real-gas molar volume, v̄ = Z·R·T/P.

    The actual volume one mole of a real gas occupies, the ideal value scaled by its
    ``compressibility_factor`` Z: v̄ = Z·R·``temperature`` T / ``pressure`` P. Given Z from a
    generalized compressibility chart (at the gas's reduced pressure and temperature), this is the
    volume the ideal-gas law would get wrong — the quantity that sizes a real high-pressure cylinder
    or receiver. Z must be positive and the temperature absolute. Returns the molar volume (m³/mol).
    """
    _check(pressure, "[pressure]", "pressure")
    _check(temperature, "[temperature]", "temperature")
    p = pressure.to("Pa").magnitude
    t = temperature.to("K").magnitude
    if p <= 0 or t <= 0:
        raise ValueError("pressure and temperature must be positive")
    if compressibility_factor <= 0:
        raise ValueError("compressibility_factor must be positive")
    return Quantity(magnitude=compressibility_factor * _GAS_CONSTANT * t / p, unit="m**3/mol")


def van_der_waals_pressure(
    *,
    temperature: Quantity,
    molar_volume: Quantity,
    cohesion_a: Quantity,
    covolume_b: Quantity,
) -> Quantity:
    """The Van der Waals pressure, P = R·T/(v̄ − b) − a/v̄².

    The pressure a real gas exerts by the Van der Waals equation of state: P =
    R·``temperature`` T / (``molar_volume`` v̄ − ``covolume_b`` b) − ``cohesion_a`` a / v̄². The
    covolume b (m³/mol) is the space the molecules themselves take up, which raises the pressure by
    crowding; the cohesion term a/v̄² (a in Pa·m⁶/mol²) is the intermolecular pull that lowers it.
    Both a and b are gas-specific constants (a ≈ 0.364 Pa·m⁶/mol², b ≈ 4.27e-5 m³/mol for CO₂). The
    molar volume must exceed the covolume. Temperature must be absolute. Returns the pressure in Pa.
    """
    _check(temperature, "[temperature]", "temperature")
    _check(molar_volume, "[volume]/[substance]", "molar_volume")
    _check(cohesion_a, "[pressure] * [volume]**2 / [substance]**2", "cohesion_a")
    _check(covolume_b, "[volume]/[substance]", "covolume_b")
    t = temperature.to("K").magnitude
    v = molar_volume.to("m**3/mol").magnitude
    a = cohesion_a.to("Pa*m**6/mol**2").magnitude
    b = covolume_b.to("m**3/mol").magnitude
    if t <= 0:
        raise ValueError("temperature must be positive absolute (kelvin)")
    if v <= 0 or a < 0 or b < 0:
        raise ValueError("molar_volume must be positive; cohesion_a and covolume_b non-negative")
    if v <= b:
        raise ValueError("molar_volume must exceed the covolume b (v̄ > b)")
    return Quantity(magnitude=_GAS_CONSTANT * t / (v - b) - a / (v * v), unit="Pa")


def van_der_waals_cohesion_a(
    *, critical_temperature: Quantity, critical_pressure: Quantity
) -> Quantity:
    """The Van der Waals cohesion constant from the critical point, a = 27·R²·T_c²/(64·P_c).

    :func:`van_der_waals_pressure` takes the cohesion constant a as given and the user has had to
    look it up. It is not an independent property: the Van der Waals isotherm has an inflection at
    the critical point (∂P/∂v̄ = ∂²P/∂v̄² = 0), and solving those two conditions pins a and b to the
    ``critical_temperature`` T_c and ``critical_pressure`` P_c the module's own
    :func:`reduced_temperature` and :func:`reduced_pressure` already take. Hence
    a = 27·R²·T_c²/(64·P_c), the strength of the intermolecular pull inferred from the conditions
    where that pull just manages to condense the gas. Temperature must be absolute. Returns the
    cohesion constant in Pa·m⁶/mol².
    """
    _check(critical_temperature, "[temperature]", "critical_temperature")
    _check(critical_pressure, "[pressure]", "critical_pressure")
    t_c = critical_temperature.to("K").magnitude
    p_c = critical_pressure.to("Pa").magnitude
    if t_c <= 0:
        raise ValueError("critical_temperature must be positive absolute (kelvin)")
    if p_c <= 0:
        raise ValueError("critical_pressure must be positive")
    a = 27.0 * _GAS_CONSTANT**2 * t_c**2 / (64.0 * p_c)
    return Quantity(magnitude=a, unit="Pa*m**6/mol**2")


def van_der_waals_covolume_b(
    *, critical_temperature: Quantity, critical_pressure: Quantity
) -> Quantity:
    """The Van der Waals covolume from the critical point, b = R·T_c/(8·P_c).

    The companion of :func:`van_der_waals_cohesion_a`, from the same pair of critical-point
    conditions: b = R·``critical_temperature`` T_c/(8·``critical_pressure`` P_c), the volume the
    molecules themselves occupy. The two together make :func:`van_der_waals_pressure` computable
    from tabulated critical properties alone, which is the form real data comes in. They also fix
    the critical molar volume at v̄_c = 3·b, so feeding both constants back into the equation of
    state at T_c and v̄ = 3·b returns P_c exactly — the closed loop that checks them. Temperature
    must be absolute. Returns the covolume in m³/mol.
    """
    _check(critical_temperature, "[temperature]", "critical_temperature")
    _check(critical_pressure, "[pressure]", "critical_pressure")
    t_c = critical_temperature.to("K").magnitude
    p_c = critical_pressure.to("Pa").magnitude
    if t_c <= 0:
        raise ValueError("critical_temperature must be positive absolute (kelvin)")
    if p_c <= 0:
        raise ValueError("critical_pressure must be positive")
    return Quantity(magnitude=_GAS_CONSTANT * t_c / (8.0 * p_c), unit="m**3/mol")


def reduced_temperature(*, temperature: Quantity, critical_temperature: Quantity) -> float:
    """The reduced temperature, T_r = T/T_c.

    A gas's temperature measured against its own critical point: T_r = ``temperature`` T /
    ``critical_temperature`` T_c, both absolute. It is one of the two corresponding-states
    coordinates (with :func:`reduced_pressure`) that enter the generalized (Nelson-Obert)
    compressibility chart — the principle that all gases at the same T_r and P_r share nearly the
    same compressibility factor Z, so one chart serves every gas. T_r > 1 means the gas is above its
    critical temperature and cannot be liquefied by pressure alone. Returns the dimensionless
    reduced temperature.
    """
    _check(temperature, "[temperature]", "temperature")
    _check(critical_temperature, "[temperature]", "critical_temperature")
    t = temperature.to("K").magnitude
    t_c = critical_temperature.to("K").magnitude
    if t <= 0:
        raise ValueError("temperature must be positive")
    if t_c <= 0:
        raise ValueError("critical_temperature must be positive")
    return t / t_c


def reduced_pressure(*, pressure: Quantity, critical_pressure: Quantity) -> float:
    """The reduced pressure, P_r = P/P_c.

    A gas's pressure measured against its own critical point: P_r = ``pressure`` P /
    ``critical_pressure`` P_c. It is the second corresponding-states coordinate (with
    :func:`reduced_temperature`) for the generalized compressibility chart, so a mixture of gases at
    the same T_r and P_r deviate from ideal by nearly the same factor. Near P_r ≪ 1 the gas is
    effectively ideal; the deviations grow as P_r approaches and passes 1. Returns the dimensionless
    reduced pressure.
    """
    _check(pressure, "[pressure]", "pressure")
    _check(critical_pressure, "[pressure]", "critical_pressure")
    p = pressure.to("Pa").magnitude
    p_c = critical_pressure.to("Pa").magnitude
    if p <= 0:
        raise ValueError("pressure must be positive")
    if p_c <= 0:
        raise ValueError("critical_pressure must be positive")
    return p / p_c


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
