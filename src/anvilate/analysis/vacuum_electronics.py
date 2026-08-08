"""T1 analytical vacuum electron-emission checks (closed-form).

A hot cathode in a vacuum tube, an electron microscope, or an X-ray source emits electrons, and how
much current it can deliver is set by two competing limits. When the cathode is the bottleneck the
current is *emission-limited* and follows the Richardson-Dushman law; when the space between cathode
and anode fills with electron charge that repels further emission the current is *space-charge-
limited* and follows the Child-Langmuir law. These are the electron-source counterparts to the solid
-state carrier transport of :mod:`anvilate.analysis.diode`.

The Richardson-Dushman law gives the saturation emission current density J = A·T²·exp(−W/(k·T)) from
the absolute temperature T and the work function W, with A the Richardson constant (about
1.2×10⁶ A/(m²·K²)) — steeply temperature-dependent through the exponential. An applied field lowers
the effective barrier by the Schottky amount ΔW = √(e³·E/(4π·ε₀)), boosting emission (about 0.12 eV
at 10 MV/m). Once emission is plentiful the diode instead obeys Child-Langmuir, J = (4/9)·ε₀·√(2e/m)
·V^{3/2}/d², rising with the anode voltage V and falling with the gap d. Inputs and outputs are
dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import exp, pi, sqrt

from ..units import Quantity

_BOLTZMANN = 1.380649e-23  # J/K
_ELEMENTARY_CHARGE = 1.602176634e-19  # C
_VACUUM_PERMITTIVITY = 8.8541878128e-12  # F/m
_ELECTRON_MASS = 9.1093837015e-31  # kg
_RICHARDSON_CONSTANT = 1.20173e6  # A/(m**2*K**2), universal value

__all__ = [
    "child_langmuir_current_density",
    "schottky_barrier_lowering",
    "thermionic_current_density",
]


def thermionic_current_density(
    *,
    temperature: Quantity,
    work_function: Quantity,
    richardson_constant: Quantity | None = None,
) -> Quantity:
    """The Richardson-Dushman emission current density, J = A*T²*exp(-W/(k*T)).

    The saturation (emission-limited) current density a hot cathode delivers, from the absolute
    ``temperature`` T, the ``work_function`` W, and the ``richardson_constant`` A (defaulting to the
    universal 1.2e6 A/(m²·K²)): J = A*T²*exp(-W/(k*T)). The exponential makes it climb steeply with
    temperature and fall sharply with work function. Returns the current density in A/m**2.
    """
    _check(temperature, "[temperature]", "temperature")
    _check(work_function, "[energy]", "work_function")
    t = temperature.to("K").magnitude
    w = work_function.to("J").magnitude
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    if w <= 0:
        raise ValueError("work_function must be positive")
    a = _richardson_value(richardson_constant)
    j = a * t * t * exp(-w / (_BOLTZMANN * t))
    return Quantity(magnitude=j, unit="A/m**2")


def schottky_barrier_lowering(*, electric_field: Quantity) -> Quantity:
    """The Schottky barrier lowering, ΔW = √(e³*E/(4π*ε₀)).

    The reduction in a cathode's effective work function under an applied surface ``electric_field``
    E, which enhances thermionic emission: ΔW = √(e³*E/(4π*ε₀)). It is about 0.12 eV at 10 MV/m and
    grows as √E. Returns the barrier lowering as an energy in J.
    """
    _check(electric_field, "[electric_potential]/[length]", "electric_field")
    e_field = electric_field.to("V/m").magnitude
    if e_field < 0:
        raise ValueError("electric_field must be non-negative")
    q = _ELEMENTARY_CHARGE
    dw = sqrt(q**3 * e_field / (4.0 * pi * _VACUUM_PERMITTIVITY))
    return Quantity(magnitude=dw, unit="J")


def child_langmuir_current_density(*, anode_voltage: Quantity, gap: Quantity) -> Quantity:
    """The Child-Langmuir space-charge-limited current density, J = (4/9)*ε₀*√(2e/m)*V^{3/2}/d².

    The maximum current density a planar vacuum diode passes once space charge, not emission, limits
    it, from the ``anode_voltage`` V and the cathode-anode ``gap`` d:
    J = (4/9)*ε₀*√(2e/m)*V^{3/2}/d². It rises as the 3/2 power of voltage (the diode's perveance)
    and falls as the inverse square of the gap. Returns the current density in A/m**2.
    """
    _check(anode_voltage, "[electric_potential]", "anode_voltage")
    _check(gap, "[length]", "gap")
    v = anode_voltage.to("V").magnitude
    d = gap.to("m").magnitude
    if v <= 0:
        raise ValueError("anode_voltage must be positive")
    if d <= 0:
        raise ValueError("gap must be positive")
    coeff = (4.0 / 9.0) * _VACUUM_PERMITTIVITY * sqrt(2.0 * _ELEMENTARY_CHARGE / _ELECTRON_MASS)
    j = coeff * v**1.5 / (d * d)
    return Quantity(magnitude=j, unit="A/m**2")


def _richardson_value(richardson_constant: Quantity | None) -> float:
    if richardson_constant is None:
        return _RICHARDSON_CONSTANT
    _check(richardson_constant, "[current]/[area]/[temperature]**2", "richardson_constant")
    a = richardson_constant.to("A/(m**2*K**2)").magnitude
    if a <= 0:
        raise ValueError("richardson_constant must be positive")
    return a


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
