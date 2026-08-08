"""T1 analytical calorimetry (sensible and latent heat) checks (closed-form).

Heating a substance takes energy in two forms: *sensible* heat, which raises its temperature, and
*latent* heat, which changes its phase at constant temperature. Together they size heaters,
chillers, melt pots, and thermal masses, and a heat balance between two bodies fixes the temperature
they
settle at when mixed. These are the general-purpose heat-quantity relations behind the airflow-
specific loads of :mod:`anvilate.analysis.psychrometrics` and the conduction/convection paths of
:mod:`anvilate.analysis.thermal`.

The sensible heat to change a mass m of specific heat c by a temperature difference ΔT is
Q = m·c·ΔT. Changing phase instead takes the latent heat Q = m·L, from the specific latent heat L of
fusion or vaporization, with no temperature change while it proceeds. When two bodies at different
temperatures are mixed and left to equilibrate with no loss, the heat one gives up equals the heat
the other takes in, so they meet at T = (m₁c₁T₁ + m₂c₂T₂)/(m₁c₁ + m₂c₂). Temperatures are taken as
absolute (K); inputs and outputs are dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "latent_heat",
    "mixing_equilibrium_temperature",
    "sensible_heat",
]


def sensible_heat(
    *, mass: Quantity, specific_heat: Quantity, temperature_change: Quantity
) -> Quantity:
    """The sensible heat, Q = m·c·ΔT.

    The energy to change the temperature of a mass ``mass`` m of ``specific_heat`` c by a
    ``temperature_change`` ΔT (a difference, in K): Q = m·c·ΔT. Positive to heat, negative to cool.
    Water's large specific heat is why it stores and moves so much thermal energy. Returns the heat
    in J.
    """
    _check(mass, "[mass]", "mass")
    _check(specific_heat, "[energy]/[mass]/[temperature]", "specific_heat")
    _check(temperature_change, "[temperature]", "temperature_change")
    m = mass.to("kg").magnitude
    c = specific_heat.to("J/(kg*K)").magnitude
    dt = temperature_change.to("K").magnitude
    if m <= 0:
        raise ValueError("mass must be positive")
    if c <= 0:
        raise ValueError("specific_heat must be positive")
    return Quantity(magnitude=m * c * dt, unit="J")


def latent_heat(*, mass: Quantity, specific_latent_heat: Quantity) -> Quantity:
    """The latent heat of a phase change, Q = m·L.

    The energy to change the phase of a mass ``mass`` m at constant temperature, from the
    ``specific_latent_heat`` L (of fusion for melting/freezing, of vaporization for boiling/
    condensing): Q = m·L. The temperature holds steady while the phase change proceeds. Returns the
    heat in J.
    """
    _check(mass, "[mass]", "mass")
    _check(specific_latent_heat, "[energy]/[mass]", "specific_latent_heat")
    m = mass.to("kg").magnitude
    lat = specific_latent_heat.to("J/kg").magnitude
    if m <= 0:
        raise ValueError("mass must be positive")
    if lat <= 0:
        raise ValueError("specific_latent_heat must be positive")
    return Quantity(magnitude=m * lat, unit="J")


def mixing_equilibrium_temperature(
    *,
    mass1: Quantity,
    specific_heat1: Quantity,
    temperature1: Quantity,
    mass2: Quantity,
    specific_heat2: Quantity,
    temperature2: Quantity,
) -> Quantity:
    """The mixing equilibrium temperature, T = (m₁c₁T₁ + m₂c₂T₂)/(m₁c₁ + m₂c₂).

    The temperature two bodies settle at when mixed and left to equilibrate with no heat loss (and
    no phase change): the heat-capacity-weighted average of their absolute temperatures
    ``temperature1`` T₁ and ``temperature2`` T₂, from the masses m₁, m₂ and specific heats c₁, c₂:
    T = (m₁c₁T₁ + m₂c₂T₂)/(m₁c₁ + m₂c₂). The result lies between the two starting temperatures.
    Returns the equilibrium temperature in K.
    """
    _check(mass1, "[mass]", "mass1")
    _check(specific_heat1, "[energy]/[mass]/[temperature]", "specific_heat1")
    _check(temperature1, "[temperature]", "temperature1")
    _check(mass2, "[mass]", "mass2")
    _check(specific_heat2, "[energy]/[mass]/[temperature]", "specific_heat2")
    _check(temperature2, "[temperature]", "temperature2")
    m1 = mass1.to("kg").magnitude
    c1 = specific_heat1.to("J/(kg*K)").magnitude
    t1 = temperature1.to("K").magnitude
    m2 = mass2.to("kg").magnitude
    c2 = specific_heat2.to("J/(kg*K)").magnitude
    t2 = temperature2.to("K").magnitude
    if m1 <= 0 or m2 <= 0:
        raise ValueError("masses must be positive")
    if c1 <= 0 or c2 <= 0:
        raise ValueError("specific heats must be positive")
    if t1 <= 0 or t2 <= 0:
        raise ValueError("temperatures must be positive (absolute temperature)")
    t_f = (m1 * c1 * t1 + m2 * c2 * t2) / (m1 * c1 + m2 * c2)
    return Quantity(magnitude=t_f, unit="K")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
