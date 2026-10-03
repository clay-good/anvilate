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

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_CATHODE_SOURCE = "the cathode material's cited emission data (work function, Richardson constant)"
_THERMAL_SOURCE = "the cathode's measured or specified absolute operating temperature"
_ELECTRODE_SOURCE = "the electrode drawing and supply voltage specification"


class _VacuumElectronicsInputError(RefusalError, ValueError):
    """A vacuum electron-emission input that cannot be used without correction."""


def _vacuum_electronics_refusal(
    message: str, *, subject: str, source: str
) -> _VacuumElectronicsInputError:
    return _VacuumElectronicsInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _vacuum_electronics_input_source(name: str) -> str:
    if name in {"richardson_constant", "work_function"}:
        return _CATHODE_SOURCE
    if name == "temperature":
        return _THERMAL_SOURCE
    return _ELECTRODE_SOURCE


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
        raise _vacuum_electronics_refusal(
            "temperature must be positive (absolute temperature)",
            subject="temperature",
            source=_THERMAL_SOURCE,
        )
    if w <= 0:
        raise _vacuum_electronics_refusal(
            "work_function must be positive", subject="work_function", source=_CATHODE_SOURCE
        )
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
        raise _vacuum_electronics_refusal(
            "electric_field must be non-negative",
            subject="electric_field",
            source=_ELECTRODE_SOURCE,
        )
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
        raise _vacuum_electronics_refusal(
            "anode_voltage must be positive", subject="anode_voltage", source=_ELECTRODE_SOURCE
        )
    if d <= 0:
        raise _vacuum_electronics_refusal(
            "gap must be positive", subject="gap", source=_ELECTRODE_SOURCE
        )
    coeff = (4.0 / 9.0) * _VACUUM_PERMITTIVITY * sqrt(2.0 * _ELEMENTARY_CHARGE / _ELECTRON_MASS)
    j = coeff * v**1.5 / (d * d)
    return Quantity(magnitude=j, unit="A/m**2")


def _richardson_value(richardson_constant: Quantity | None) -> float:
    if richardson_constant is None:
        return _RICHARDSON_CONSTANT
    _check(richardson_constant, "[current]/[area]/[temperature]**2", "richardson_constant")
    a = richardson_constant.to("A/(m**2*K**2)").magnitude
    if a <= 0:
        raise _vacuum_electronics_refusal(
            "richardson_constant must be positive",
            subject="richardson_constant",
            source=_CATHODE_SOURCE,
        )
    return a


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _vacuum_electronics_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_vacuum_electronics_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _vacuum_electronics_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_vacuum_electronics_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
