"""T1 analytical Fickian diffusion (mass-transport) checks (closed-form).

Matter spreads from where it is concentrated to where it is not, driven by random molecular motion —
diffusion. Fick's law sets the rate: the flux through a layer is proportional to the concentration
gradient across it. This governs how fast a gas permeates a barrier film, a drug releases from a
patch, a dopant penetrates a wafer, or a contaminant migrates through soil. It is the mass-transport
counterpart of heat conduction (:mod:`anvilate.analysis.thermal`), with the same square-root-of-time
penetration behavior.

Across a layer of thickness L with a concentration difference Delta_C, the steady flux is
J = D * Delta_C / L (Fick's first law), from the diffusivity D. Time enters through the mean-square
spreading: a diffusion front advances a characteristic distance x = sqrt(D * t) in a time t (the
Einstein relation), so the time to diffuse a distance is t = x^2 / D. These fix the two practical
questions — how fast matter crosses a barrier, and how far (or how long) a transient front reaches.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "diffusion_length",
    "diffusion_time",
    "steady_diffusion_flux",
]


def steady_diffusion_flux(
    *, diffusivity: Quantity, concentration_difference: Quantity, thickness: Quantity
) -> Quantity:
    """The steady diffusion flux, J = D * Delta_C / L (Fick's first law).

    The molar flux through a layer at steady state: the ``diffusivity`` D times the
    ``concentration_difference`` Delta_C across the layer, over its ``thickness`` L,
    J = D*Delta_C/L. It is the permeation rate through a barrier film or membrane per unit area,
    larger for a thinner
    layer or a steeper gradient. Returns the flux in mol/(m**2*s).
    """
    _check(diffusivity, "[length]**2/[time]", "diffusivity")
    _check(concentration_difference, "[substance]/[length]**3", "concentration_difference")
    _check(thickness, "[length]", "thickness")
    d = diffusivity.to("m**2/s").magnitude
    dc = concentration_difference.to("mol/m**3").magnitude
    length = thickness.to("m").magnitude
    if d < 0:
        raise ValueError("diffusivity must be non-negative")
    if length <= 0:
        raise ValueError("thickness must be positive")
    return Quantity(magnitude=d * dc / length, unit="mol/(m**2*s)")


def diffusion_length(*, diffusivity: Quantity, time: Quantity) -> Quantity:
    """The diffusion penetration length, x = sqrt(D * t).

    The characteristic distance a diffusion front advances in a time ``time`` t at a ``diffusivity``
    D, x = sqrt(D * t) (the Einstein relation). Because it grows only with the square root of time,
    diffusion is quick over microns and glacially slow over centimetres — the reason thin films and
    fine particles equilibrate fast. Returns the diffusion length in m.
    """
    _check(diffusivity, "[length]**2/[time]", "diffusivity")
    _check(time, "[time]", "time")
    d = diffusivity.to("m**2/s").magnitude
    t = time.to("s").magnitude
    if d < 0:
        raise ValueError("diffusivity must be non-negative")
    if t < 0:
        raise ValueError("time must be non-negative")
    return Quantity(magnitude=sqrt(d * t), unit="m")


def diffusion_time(*, diffusion_length: Quantity, diffusivity: Quantity) -> Quantity:
    """The diffusion time over a distance, t = x^2 / D.

    The inverse of :func:`diffusion_length`: the time for a diffusion front to reach a distance
    ``diffusion_length`` x at a ``diffusivity`` D, t = x^2 / D. It quadruples for each doubling of
    the distance, so a process that diffuses across a thin section in seconds takes hours across a
    thick one. Returns the time in s.
    """
    _check(diffusion_length, "[length]", "diffusion_length")
    _check(diffusivity, "[length]**2/[time]", "diffusivity")
    x = diffusion_length.to("m").magnitude
    d = diffusivity.to("m**2/s").magnitude
    if x < 0:
        raise ValueError("diffusion_length must be non-negative")
    if d <= 0:
        raise ValueError("diffusivity must be positive")
    return Quantity(magnitude=x * x / d, unit="s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
