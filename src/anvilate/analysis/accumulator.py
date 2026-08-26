"""T1 analytical gas-charged hydraulic accumulator checks (closed-form).

A gas-charged accumulator stores hydraulic energy by compressing a nitrogen precharge as fluid is
pushed in, and gives it back as the fluid is drawn out — for emergency actuation, pulsation damping,
or leveling a pump's demand. How much fluid it delivers between two system pressures follows
from the gas law.

As the system pressure swings between a minimum P₁ and a maximum P₂, the gas volume follows the
polytropic relation P·Vⁿ = constant (n = 1 for a slow, isothermal cycle; n ≈ 1.4 for a fast,
adiabatic one). The usable fluid volume is the difference in gas volume between the two pressures:
ΔV = V₀·[(P₀/P₁)^(1/n) − (P₀/P₂)^(1/n)], where V₀ is the accumulator's total (gas) volume and P₀ the
precharge pressure. The precharge is set below the minimum working pressure (typically ~0.9·P₁), or
the accumulator empties before the system reaches P₁. All pressures are *absolute*; the polytropic
exponent is the caller's from the duty cycle.

Sources: Esposito, *Fluid Power with Applications* (accumulators) — the usable volume a gas-
charged accumulator gives between its precharge and system pressures, and the size a required
volume needs.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "accumulator_size_for_volume",
    "accumulator_usable_volume",
]


def _fraction(precharge: float, p_min: float, p_max: float, n: float) -> float:
    if precharge <= 0 or p_min <= 0 or p_max <= 0:
        raise ValueError("all pressures must be positive (absolute)")
    if precharge > p_min:
        raise ValueError(
            "precharge_pressure must not exceed minimum_pressure (or no fluid is drawn)"
        )
    if p_max <= p_min:
        raise ValueError("maximum_pressure must exceed minimum_pressure")
    if n < 1.0:
        raise ValueError("polytropic_exponent must be at least 1 (1 isothermal, ~1.4 adiabatic)")
    return (precharge / p_min) ** (1.0 / n) - (precharge / p_max) ** (1.0 / n)


def accumulator_usable_volume(
    *,
    total_volume: Quantity,
    precharge_pressure: Quantity,
    minimum_pressure: Quantity,
    maximum_pressure: Quantity,
    polytropic_exponent: float = 1.4,
) -> Quantity:
    """The fluid delivered between two pressures, ΔV = V₀·[(P₀/P₁)^(1/n) − (P₀/P₂)^(1/n)].

    The usable fluid volume a gas-charged accumulator of ``total_volume`` V₀ and
    ``precharge_pressure`` P₀ gives up as the system pressure falls from ``maximum_pressure`` P₂
    to ``minimum_pressure`` P₁, following the polytropic gas law with ``polytropic_exponent`` n
    (1 isothermal, ~1.4 adiabatic). A slow (isothermal) cycle delivers more fluid than a fast
    (adiabatic) one from the same accumulator, because the gas has time to shed heat. All
    pressures are *absolute*, and the precharge must not exceed the minimum pressure. Returns the
    usable fluid volume in litres.
    """
    _check(total_volume, "[length]**3", "total_volume")
    _check(precharge_pressure, "[pressure]", "precharge_pressure")
    _check(minimum_pressure, "[pressure]", "minimum_pressure")
    _check(maximum_pressure, "[pressure]", "maximum_pressure")
    v0 = total_volume.to("L").magnitude
    if v0 <= 0:
        raise ValueError("total_volume must be positive")
    fraction = _fraction(
        precharge_pressure.to("Pa").magnitude,
        minimum_pressure.to("Pa").magnitude,
        maximum_pressure.to("Pa").magnitude,
        polytropic_exponent,
    )
    return Quantity(magnitude=v0 * fraction, unit="L")


def accumulator_size_for_volume(
    *,
    required_volume: Quantity,
    precharge_pressure: Quantity,
    minimum_pressure: Quantity,
    maximum_pressure: Quantity,
    polytropic_exponent: float = 1.4,
) -> Quantity:
    """The size a required delivery needs, V₀ = ΔV/[(P₀/P₁)^(1/n) − (P₀/P₂)^(1/n)].

    The inverse of :func:`accumulator_usable_volume`: the total (gas) volume an accumulator must
    have to deliver a ``required_volume`` ΔV of fluid as the pressure falls from
    ``maximum_pressure`` P₂ to ``minimum_pressure`` P₁ at ``precharge_pressure`` P₀, for a
    ``polytropic_exponent`` n. This is the sizing step — pick the next standard accumulator at or
    above the result. Returns the required total volume in litres.
    """
    _check(required_volume, "[length]**3", "required_volume")
    _check(precharge_pressure, "[pressure]", "precharge_pressure")
    _check(minimum_pressure, "[pressure]", "minimum_pressure")
    _check(maximum_pressure, "[pressure]", "maximum_pressure")
    dv = required_volume.to("L").magnitude
    if dv <= 0:
        raise ValueError("required_volume must be positive")
    fraction = _fraction(
        precharge_pressure.to("Pa").magnitude,
        minimum_pressure.to("Pa").magnitude,
        maximum_pressure.to("Pa").magnitude,
        polytropic_exponent,
    )
    return Quantity(magnitude=dv / fraction, unit="L")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
