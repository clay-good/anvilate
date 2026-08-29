"""T1 analytical Gaussian-beam (laser) propagation checks (closed-form).

A laser does not travel as a ray or a plane wave but as a Gaussian beam: a bundle that is narrowest
at a waist, spreads by diffraction on either side, and never collimates perfectly. Four numbers
govern it, and they are all closed-form — the ray optics of :mod:`anvilate.analysis.optics` gives
the geometry of imaging, this gives the diffraction-limited reality of a real laser beam.

At the waist the beam has radius w₀; the distance over which it stays roughly collimated is the
Rayleigh range z_R = π·w₀²/λ, and beyond it the radius grows as w(z) = w₀·√(1 + (z/z_R)²), reaching
√2·w₀ at one Rayleigh range. Far from the waist the beam opens into a cone of half-angle
θ = λ/(π·w₀) — the diffraction divergence, which trades off against waist size, so a tightly focused
beam spreads fast and a well-collimated beam must be wide. Focusing a collimated beam of radius w
through a lens of focal length f concentrates it to a spot of radius w_f = λ·f/(π·w), the reason a
laser cutter expands its beam before the final lens. Waists, ranges, and focused spots are
dimension-checked :class:`~anvilate.units.Quantity` values; the divergence half-angle is a plain
float in radians (a dimensionless angle).
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

__all__ = [
    "rayleigh_range",
    "beam_radius_at_distance",
    "beam_divergence_half_angle",
    "beam_waist_for_divergence",
    "focused_spot_radius",
    "gaussian_beam_peak_intensity",
]


def rayleigh_range(*, beam_waist: Quantity, wavelength: Quantity) -> Quantity:
    """The Rayleigh range, z_R = π·w₀²/λ.

    The distance from the waist over which a Gaussian beam stays roughly collimated — where its
    cross-sectional area doubles and its radius grows to √2·w₀: z_R = π·w₀²/λ, from the waist radius
    ``beam_waist`` w₀ and the ``wavelength`` λ. It is the natural depth of focus of a laser beam; a
    tighter waist collimates over a shorter range (z_R falls with the *square* of the waist), which
    is the fundamental focus-versus-depth trade. Returns the Rayleigh range in metres.
    """
    _check(beam_waist, "[length]", "beam_waist")
    _check(wavelength, "[length]", "wavelength")
    w0 = beam_waist.to("m").magnitude
    lam = wavelength.to("m").magnitude
    if w0 <= 0:
        raise ValueError("beam_waist must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    return Quantity(magnitude=pi * w0**2 / lam, unit="m")


def beam_radius_at_distance(
    *, beam_waist: Quantity, wavelength: Quantity, distance: Quantity
) -> Quantity:
    """The beam radius a distance from the waist, w(z) = w₀·√(1 + (z/z_R)²).

    How wide a Gaussian beam has spread a ``distance`` z from its waist: w(z) = w₀·√(1 + (z/z_R)²),
    with the waist radius ``beam_waist`` w₀ and the Rayleigh range z_R = π·w₀²/λ
    (:func:`rayleigh_range`) from the ``wavelength`` λ. Near the waist (z ≪ z_R) it barely grows; at
    z = z_R it is √2·w₀; far out it opens linearly at the divergence angle. Returns the beam radius
    at z in metres.
    """
    _check(beam_waist, "[length]", "beam_waist")
    _check(wavelength, "[length]", "wavelength")
    _check(distance, "[length]", "distance")
    w0 = beam_waist.to("m").magnitude
    lam = wavelength.to("m").magnitude
    z = distance.to("m").magnitude
    if w0 <= 0:
        raise ValueError("beam_waist must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    z_r = pi * w0**2 / lam
    return Quantity(magnitude=w0 * sqrt(1.0 + (z / z_r) ** 2), unit="m")


def beam_divergence_half_angle(*, beam_waist: Quantity, wavelength: Quantity) -> float:
    """The far-field divergence half-angle, θ = λ/(π·w₀).

    The half-angle of the cone a Gaussian beam opens into far from its waist: θ = λ/(π·w₀), from the
    ``wavelength`` λ and the waist radius ``beam_waist`` w₀. It is set by diffraction and trades
    directly against the waist — a tightly focused beam (small w₀) diverges fast, a well-collimated
    beam must be wide — so it cannot be beaten without enlarging the beam. Returns the divergence
    half-angle in radians as a plain float (a dimensionless angle; multiply by 1000 for mrad).
    """
    _check(beam_waist, "[length]", "beam_waist")
    _check(wavelength, "[length]", "wavelength")
    w0 = beam_waist.to("m").magnitude
    lam = wavelength.to("m").magnitude
    if w0 <= 0:
        raise ValueError("beam_waist must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    return lam / (pi * w0)


def beam_waist_for_divergence(*, divergence_half_angle: float, wavelength: Quantity) -> Quantity:
    """The waist radius a target divergence requires, w₀ = λ/(π·θ).

    The design inverse of :func:`beam_divergence_half_angle`: to hold the far-field spread to a
    half-angle ``divergence_half_angle`` θ (radians), the beam must have a waist of at least
    w₀ = λ/(π·θ) at the ``wavelength`` λ. This is how a beam expander is sized — a tighter pointing
    or a smaller far-field spot demands a bigger beam. θ must be positive. Returns the required
    waist radius in metres.
    """
    _check(wavelength, "[length]", "wavelength")
    lam = wavelength.to("m").magnitude
    if divergence_half_angle <= 0:
        raise ValueError("divergence_half_angle must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    return Quantity(magnitude=lam / (pi * divergence_half_angle), unit="m")


def focused_spot_radius(
    *, wavelength: Quantity, focal_length: Quantity, input_beam_radius: Quantity
) -> Quantity:
    """The focused spot radius of a collimated beam, w_f = λ·f/(π·w).

    The smallest spot a lens can form from a collimated Gaussian beam: w_f = λ·f/(π·w), from the
    ``wavelength`` λ, the lens ``focal_length`` f, and the ``input_beam_radius`` w at the lens. The
    spot shrinks as the input beam is *widened*, which is why a laser cutter or marker expands its
    beam before the final lens — a bigger beam focuses tighter. Returns the focused spot (waist)
    radius in metres.
    """
    _check(wavelength, "[length]", "wavelength")
    _check(focal_length, "[length]", "focal_length")
    _check(input_beam_radius, "[length]", "input_beam_radius")
    lam = wavelength.to("m").magnitude
    f = focal_length.to("m").magnitude
    w = input_beam_radius.to("m").magnitude
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    if f <= 0:
        raise ValueError("focal_length must be positive")
    if w <= 0:
        raise ValueError("input_beam_radius must be positive")
    return Quantity(magnitude=lam * f / (pi * w), unit="m")


def gaussian_beam_peak_intensity(*, power: Quantity, beam_radius: Quantity) -> Quantity:
    """The on-axis peak intensity of a Gaussian beam, I₀ = 2·P/(π·w²).

    A Gaussian beam concentrates its ``power`` P toward the centre, so its on-axis intensity is
    twice the power spread evenly over the beam area: I₀ = 2·P/(π·w²), from the total power and the
    ``beam_radius`` w (the 1/e² radius at the plane of interest — use the focused-spot or waist
    radius for the peak). This is the number that governs optical damage thresholds, self-focusing,
    and nonlinear conversion — all set by the peak irradiance, not the average power — which is why
    even a modest laser becomes destructive once focused to a small spot. Returns the peak intensity
    in W/m².
    """
    _check(power, "[power]", "power")
    _check(beam_radius, "[length]", "beam_radius")
    p = power.to("W").magnitude
    w = beam_radius.to("m").magnitude
    if p < 0:
        raise ValueError("power must be non-negative")
    if w <= 0:
        raise ValueError("beam_radius must be positive")
    return Quantity(magnitude=2.0 * p / (pi * w**2), unit="W/m**2")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
