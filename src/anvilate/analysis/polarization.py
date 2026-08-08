"""T1 analytical light-polarization (Malus's law) checks (closed-form).

A polarizer only passes the component of a light wave aligned with its transmission axis, so
rotating one sheet in front of another dims the beam by an amount that depends on the angle between
their axes. This is the transmission side of polarization optics — how much light gets *through* a
polarizer pair — as opposed to how reflection polarizes light at the Brewster angle of
:mod:`anvilate.analysis.fresnel`.

For light already polarized, an analyzer at angle θ to the polarization passes the fraction cos²θ of
the intensity: Malus's law, I = I₀·cos²θ. Crossed axes (θ = 90°) block the beam; aligned axes pass
it all. Inverting the law gives the analyzer angle for a target attenuation, θ = arccos(√(I/I₀)),
the basis of a variable optical attenuator. Unpolarized light is different: an ideal polarizer
passes exactly half of it, I = I₀/2, regardless of orientation, because random polarization averages
cos²θ to ½. The **angle is a plain float in radians**. Intensities are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import acos, cos, sqrt

from ..units import Quantity

__all__ = [
    "malus_angle_for_intensity",
    "malus_transmitted_intensity",
    "unpolarized_transmitted_intensity",
]


def malus_transmitted_intensity(*, incident_intensity: Quantity, angle: float) -> Quantity:
    """The Malus's-law transmitted intensity, I = I₀*cos²θ.

    The intensity of polarized light passed by an analyzer at ``angle`` θ (a plain float in radians)
    to the polarization, from the ``incident_intensity`` I₀: I = I₀*cos²θ. Aligned axes (θ = 0) pass
    everything; crossed axes (θ = π/2) block the beam. Returns the transmitted intensity in W/m**2.
    """
    _check(incident_intensity, "[power]/[area]", "incident_intensity")
    i0 = incident_intensity.to("W/m**2").magnitude
    if i0 < 0:
        raise ValueError("incident_intensity must be non-negative")
    c = cos(angle)
    return Quantity(magnitude=i0 * c * c, unit="W/m**2")


def malus_angle_for_intensity(
    *, incident_intensity: Quantity, transmitted_intensity: Quantity
) -> float:
    """The analyzer angle for a target attenuation, θ = arccos(√(I/I₀)).

    The angle between polarizer and analyzer that passes the ``transmitted_intensity`` I from the
    ``incident_intensity`` I₀ under Malus's law: θ = arccos(√(I/I₀)), the setting of a variable
    optical attenuator. Requires 0 <= I <= I₀. Returns the angle as a plain float in radians (in
    [0, π/2]).
    """
    _check(incident_intensity, "[power]/[area]", "incident_intensity")
    _check(transmitted_intensity, "[power]/[area]", "transmitted_intensity")
    i0 = incident_intensity.to("W/m**2").magnitude
    i = transmitted_intensity.to("W/m**2").magnitude
    if i0 <= 0:
        raise ValueError("incident_intensity must be positive")
    if i < 0:
        raise ValueError("transmitted_intensity must be non-negative")
    if i > i0:
        raise ValueError("transmitted_intensity must not exceed incident_intensity")
    return acos(sqrt(i / i0))


def unpolarized_transmitted_intensity(*, incident_intensity: Quantity) -> Quantity:
    """The unpolarized transmission through an ideal polarizer, I = I₀/2.

    The intensity of initially unpolarized light passed by an ideal polarizer, from the
    ``incident_intensity`` I₀: I = I₀/2, independent of the polarizer's orientation because the
    random polarization averages cos²θ to ½. Returns the transmitted intensity in W/m**2.
    """
    _check(incident_intensity, "[power]/[area]", "incident_intensity")
    i0 = incident_intensity.to("W/m**2").magnitude
    if i0 < 0:
        raise ValueError("incident_intensity must be non-negative")
    return Quantity(magnitude=0.5 * i0, unit="W/m**2")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
