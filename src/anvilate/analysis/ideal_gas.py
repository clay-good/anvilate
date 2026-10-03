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

Sources: Cengel & Boles, *Thermodynamics: An Engineering Approach* (the ideal-gas equation of
state) — pV = nRT solved for each of its four variables, and the range over which a real gas
follows it.
"""

from __future__ import annotations

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_STATE_SOURCE = "the gas's measured absolute pressure and temperature"
_CONTAINMENT_SOURCE = "the vessel drawing volume"
_CHARGE_SOURCE = "the gas charge record (amount of substance)"


class _IdealGasInputError(RefusalError, ValueError):
    """An ideal-gas input that cannot be used without correction."""


def _ideal_gas_refusal(message: str, *, subject: str, source: str) -> _IdealGasInputError:
    return _IdealGasInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _ideal_gas_input_source(name: str) -> str:
    if name == "volume":
        return _CONTAINMENT_SOURCE
    if name == "amount":
        return _CHARGE_SOURCE
    return _STATE_SOURCE


_GAS_CONSTANT = 8.314462618  # J/(mol*K), universal

__all__ = [
    "ideal_gas_moles",
    "ideal_gas_pressure",
    "ideal_gas_temperature",
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
        raise _ideal_gas_refusal("amount must be positive", subject="amount", source=_CHARGE_SOURCE)
    if v <= 0:
        raise _ideal_gas_refusal(
            "volume must be positive", subject="volume", source=_CONTAINMENT_SOURCE
        )
    if t <= 0:
        raise _ideal_gas_refusal(
            "temperature must be positive (absolute temperature)",
            subject="temperature",
            source=_STATE_SOURCE,
        )
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
        raise _ideal_gas_refusal("amount must be positive", subject="amount", source=_CHARGE_SOURCE)
    if p <= 0:
        raise _ideal_gas_refusal(
            "pressure must be positive", subject="pressure", source=_STATE_SOURCE
        )
    if t <= 0:
        raise _ideal_gas_refusal(
            "temperature must be positive (absolute temperature)",
            subject="temperature",
            source=_STATE_SOURCE,
        )
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
        raise _ideal_gas_refusal(
            "pressure must be positive", subject="pressure", source=_STATE_SOURCE
        )
    if v <= 0:
        raise _ideal_gas_refusal(
            "volume must be positive", subject="volume", source=_CONTAINMENT_SOURCE
        )
    if t <= 0:
        raise _ideal_gas_refusal(
            "temperature must be positive (absolute temperature)",
            subject="temperature",
            source=_STATE_SOURCE,
        )
    return Quantity(magnitude=p * v / (_GAS_CONSTANT * t), unit="mol")


def ideal_gas_temperature(*, pressure: Quantity, volume: Quantity, amount: Quantity) -> Quantity:
    """The ideal-gas temperature, T = PV/(nR).

    The absolute temperature a fixed amount of gas must be at, from the ``pressure`` P, the
    ``volume`` V, and the ``amount`` n (in moles): T = PV/(nR). It closes the PV = nRT set alongside
    :func:`ideal_gas_pressure`, :func:`ideal_gas_volume`, and :func:`ideal_gas_moles` — the
    rearrangement a gas thermometer uses, reading temperature from a known quantity of gas at
    measured pressure and volume. Returns the temperature in kelvin.
    """
    _check(pressure, "[pressure]", "pressure")
    _check(volume, "[volume]", "volume")
    _check(amount, "[substance]", "amount")
    p = pressure.to("Pa").magnitude
    v = volume.to("m**3").magnitude
    n = amount.to("mol").magnitude
    if p <= 0:
        raise _ideal_gas_refusal(
            "pressure must be positive", subject="pressure", source=_STATE_SOURCE
        )
    if v <= 0:
        raise _ideal_gas_refusal(
            "volume must be positive", subject="volume", source=_CONTAINMENT_SOURCE
        )
    if n <= 0:
        raise _ideal_gas_refusal("amount must be positive", subject="amount", source=_CHARGE_SOURCE)
    return Quantity(magnitude=p * v / (n * _GAS_CONSTANT), unit="K")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _ideal_gas_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_ideal_gas_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _ideal_gas_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_ideal_gas_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
