"""T1 analytical ideal-gas-law checks (closed-form).

The ideal gas law PV = nRT ties together the four quantities that describe a gas — pressure, volume,
amount, and temperature — and solving it for any one from the others is the first calculation in
almost any gas problem: sizing a tank, dosing a reactor, or reading a cylinder's contents. It is the
equation of state behind the compression work of :mod:`anvilate.analysis.gas_compression` (whose
density form ρ = PM/RT is the same law written per unit mass) and the stagnation relations of
:mod:`anvilate.analysis.compressible_flow`.

From the universal gas constant R, the law gives the pressure P = nRT/V a given amount of gas exerts
in a fixed volume, the volume V = nRT/P it occupies at a set pressure, and the amount n = PV/(RT) a
measured pressure, volume, and temperature imply — how many moles a cylinder actually holds. The
temperature is absolute (K), and the amount is in moles; inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity

_GAS_CONSTANT = 8.314462618  # J/(mol*K), universal

__all__ = [
    "ideal_gas_moles",
    "ideal_gas_pressure",
    "ideal_gas_volume",
]


def ideal_gas_pressure(*, amount: Quantity, volume: Quantity, temperature: Quantity) -> Quantity:
    """The ideal-gas pressure, P = nRT/V.

    The pressure a gas exerts, from the ``amount`` n (in moles), the ``volume`` V it fills, and the
    absolute ``temperature`` T: P = nRT/V. More gas, a smaller volume, or a higher temperature all
    raise the pressure. Returns the pressure in Pa.
    """
    _check(amount, "[substance]", "amount")
    _check(volume, "[volume]", "volume")
    _check(temperature, "[temperature]", "temperature")
    n = amount.to("mol").magnitude
    v = volume.to("m**3").magnitude
    t = temperature.to("K").magnitude
    if n <= 0:
        raise ValueError("amount must be positive")
    if v <= 0:
        raise ValueError("volume must be positive")
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    return Quantity(magnitude=n * _GAS_CONSTANT * t / v, unit="Pa")


def ideal_gas_volume(*, amount: Quantity, pressure: Quantity, temperature: Quantity) -> Quantity:
    """The ideal-gas volume, V = nRT/P.

    The volume a gas occupies, from the ``amount`` n (in moles), the ``pressure`` P holding it, and
    the absolute ``temperature`` T: V = nRT/P. One mole at 0 °C and one atmosphere fills about
    22.4 litres. Returns the volume in m**3.
    """
    _check(amount, "[substance]", "amount")
    _check(pressure, "[pressure]", "pressure")
    _check(temperature, "[temperature]", "temperature")
    n = amount.to("mol").magnitude
    p = pressure.to("Pa").magnitude
    t = temperature.to("K").magnitude
    if n <= 0:
        raise ValueError("amount must be positive")
    if p <= 0:
        raise ValueError("pressure must be positive")
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    return Quantity(magnitude=n * _GAS_CONSTANT * t / p, unit="m**3")


def ideal_gas_moles(*, pressure: Quantity, volume: Quantity, temperature: Quantity) -> Quantity:
    """The ideal-gas amount, n = PV/(RT).

    The number of moles of gas present, from the ``pressure`` P, the ``volume`` V, and the absolute
    ``temperature`` T: n = PV/(RT) — how much gas a cylinder of known pressure, volume, and
    temperature actually holds. Returns the amount in mol.
    """
    _check(pressure, "[pressure]", "pressure")
    _check(volume, "[volume]", "volume")
    _check(temperature, "[temperature]", "temperature")
    p = pressure.to("Pa").magnitude
    v = volume.to("m**3").magnitude
    t = temperature.to("K").magnitude
    if p <= 0:
        raise ValueError("pressure must be positive")
    if v <= 0:
        raise ValueError("volume must be positive")
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    return Quantity(magnitude=p * v / (_GAS_CONSTANT * t), unit="mol")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
