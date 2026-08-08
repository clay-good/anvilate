"""T1 analytical capillary-imbibition (Washburn) checks (closed-form).

When a wetting liquid touches a fine pore — paper, a wick, soil, a chromatography strip, a fabric —
surface tension pulls it in without any applied pressure. How fast it advances is the Washburn
problem: the capillary suction driving the flow is balanced against the viscous drag of the growing
liquid column, giving a penetration that slows as it goes. This is the *dynamic* companion to the
static equilibrium height h = 2σ·cosθ/(ρgr) of :mod:`anvilate.analysis.fluid_statics` — that gives
where the liquid finally stops, this gives how it gets there.

The Young-Laplace suction across the curved meniscus is Δp = 2σ·cosθ/r, from the surface tension σ,
the ``contact_angle`` θ, and the pore radius r. Balancing it against Poiseuille drag gives the
Washburn law L = √(σ·r·cosθ·t/(2μ)): the penetration grows as the square root of time, so wicking
starts fast and crawls later. Inverting it gives the time to reach a given distance,
t = 2μL²/(σ·r·cosθ), which rises with the square of the distance. The **contact angle is a plain
float in degrees**; other inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import cos, radians, sqrt

from ..units import Quantity

__all__ = [
    "washburn_capillary_pressure",
    "washburn_penetration_length",
    "washburn_penetration_time",
]


def washburn_capillary_pressure(
    *, surface_tension: Quantity, pore_radius: Quantity, contact_angle: float = 0.0
) -> Quantity:
    """The Young-Laplace capillary suction, Δp = 2σ·cosθ/r.

    The pressure difference across the meniscus that drives a wetting liquid into a pore, from the
    ``surface_tension`` σ, the ``pore_radius`` r, and the ``contact_angle`` θ (a plain float in
    degrees, 0 for perfect wetting): Δp = 2σ·cosθ/r. A finer pore sucks harder. Returns the pressure
    in Pa.
    """
    _check(surface_tension, "[force]/[length]", "surface_tension")
    _check(pore_radius, "[length]", "pore_radius")
    sigma = surface_tension.to("N/m").magnitude
    r = pore_radius.to("m").magnitude
    if sigma <= 0:
        raise ValueError("surface_tension must be positive")
    if r <= 0:
        raise ValueError("pore_radius must be positive")
    return Quantity(magnitude=2.0 * sigma * cos(radians(contact_angle)) / r, unit="Pa")


def washburn_penetration_length(
    *,
    surface_tension: Quantity,
    pore_radius: Quantity,
    viscosity: Quantity,
    time: Quantity,
    contact_angle: float = 0.0,
) -> Quantity:
    """The Washburn penetration length, L = √(σ·r·cosθ·t/(2μ)).

    How far a wetting liquid has wicked into a pore after a ``time`` t, from the ``surface_tension``
    σ, the ``pore_radius`` r, the dynamic ``viscosity`` μ, and the ``contact_angle`` θ (a plain
    float in degrees): L = √(σ·r·cosθ·t/(2μ)). The advance grows as √t, so it is fast at first and
    slows as the column lengthens. Returns the penetration length in m.
    """
    _check(surface_tension, "[force]/[length]", "surface_tension")
    _check(pore_radius, "[length]", "pore_radius")
    _check(viscosity, "[pressure]*[time]", "viscosity")
    _check(time, "[time]", "time")
    sigma = surface_tension.to("N/m").magnitude
    r = pore_radius.to("m").magnitude
    mu = viscosity.to("Pa*s").magnitude
    t = time.to("s").magnitude
    cos_theta = cos(radians(contact_angle))
    if sigma <= 0:
        raise ValueError("surface_tension must be positive")
    if r <= 0:
        raise ValueError("pore_radius must be positive")
    if mu <= 0:
        raise ValueError("viscosity must be positive")
    if t < 0:
        raise ValueError("time must be non-negative")
    if cos_theta <= 0:
        raise ValueError("contact_angle must be below 90 degrees for the liquid to wick in")
    return Quantity(magnitude=sqrt(sigma * r * cos_theta * t / (2.0 * mu)), unit="m")


def washburn_penetration_time(
    *,
    surface_tension: Quantity,
    pore_radius: Quantity,
    viscosity: Quantity,
    length: Quantity,
    contact_angle: float = 0.0,
) -> Quantity:
    """The Washburn penetration time, t = 2μL²/(σ·r·cosθ).

    The time for a wetting liquid to wick a distance ``length`` L into a pore, from the
    ``surface_tension`` σ, the ``pore_radius`` r, the dynamic ``viscosity`` μ, and the
    ``contact_angle`` θ (a plain float in degrees): t = 2μL²/(σ·r·cosθ). It rises with the square of
    the distance, so reaching twice as far takes four times as long. Returns the time in s.
    """
    _check(surface_tension, "[force]/[length]", "surface_tension")
    _check(pore_radius, "[length]", "pore_radius")
    _check(viscosity, "[pressure]*[time]", "viscosity")
    _check(length, "[length]", "length")
    sigma = surface_tension.to("N/m").magnitude
    r = pore_radius.to("m").magnitude
    mu = viscosity.to("Pa*s").magnitude
    ell = length.to("m").magnitude
    cos_theta = cos(radians(contact_angle))
    if sigma <= 0:
        raise ValueError("surface_tension must be positive")
    if r <= 0:
        raise ValueError("pore_radius must be positive")
    if mu <= 0:
        raise ValueError("viscosity must be positive")
    if ell < 0:
        raise ValueError("length must be non-negative")
    if cos_theta <= 0:
        raise ValueError("contact_angle must be below 90 degrees for the liquid to wick in")
    return Quantity(magnitude=2.0 * mu * ell * ell / (sigma * r * cos_theta), unit="s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
