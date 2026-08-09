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
"""

from __future__ import annotations

from ..units import Quantity

_GAS_CONSTANT = 8.314462618  # J/(mol*K), universal

__all__ = [
    "compressibility_factor",
    "real_gas_molar_volume",
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


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
