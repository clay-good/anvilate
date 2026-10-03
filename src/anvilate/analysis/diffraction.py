"""T1 analytical wave-diffraction (Bragg / grating) checks (closed-form).

When waves scatter off a regular array of spacings comparable to their wavelength, they interfere
and reinforce only at specific angles. Two instruments live on this: X-ray diffraction reads the
angles a crystal reflects to recover its atomic plane spacing (the fingerprint that identifies a
material), and a diffraction grating splits light into its spectrum for a spectrometer. This is
wave-interference optics, distinct from the ray optics and single-aperture resolution limit of
:mod:`anvilate.analysis.optics`.

Bragg's law, n*lambda = 2*d*sin(theta), gives the angle at which X-rays of wavelength lambda reflect
in phase off crystal planes spaced d apart (order n) — and, inverted, the plane spacing d from a
measured reflection angle, which is how a diffractometer identifies a phase. The grating equation,
m*lambda = D*sin(theta), gives the angle a transmission grating of groove spacing D sends the m-th
diffraction order to, spreading a spectrum by wavelength. A reflection or order exists only when the
implied sine stays at or below one; beyond that the geometry forbids it.

Sources: Hecht, *Optics* (diffraction and the diffraction grating) — Bragg's law and the plane
spacing it inverts to, the grating equation d·sin θ = m·λ, and the resolving power R = m·N with
the angular dispersion that goes with it.
"""

from __future__ import annotations

from math import asin, cos, degrees, radians, sin

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_SOURCE_SPEC_SOURCE = "the radiation source's wavelength specification"
_CRYSTAL_SOURCE = "the crystal's lattice spacing from the cited diffraction table"
_GRATING_SOURCE = "the grating datasheet (groove density and illuminated width)"
_SETUP_SOURCE = "the spectrometer setup record (order and measured angle)"


class _DiffractionInputError(RefusalError, ValueError):
    """A diffraction input that cannot be used without correction."""


def _diffraction_refusal(message: str, *, subject: str, source: str) -> _DiffractionInputError:
    return _DiffractionInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _diffraction_input_source(name: str) -> str:
    if name == "wavelength":
        return _SOURCE_SPEC_SOURCE
    if name == "plane_spacing":
        return _CRYSTAL_SOURCE
    if name in {"groove_spacing", "illuminated_lines"}:
        return _GRATING_SOURCE
    return _SETUP_SOURCE


__all__ = [
    "bragg_angle",
    "bragg_plane_spacing",
    "grating_diffraction_angle",
    "grating_resolving_power",
    "grating_resolved_wavelength_separation",
    "grating_angular_dispersion",
]


def bragg_angle(*, wavelength: Quantity, plane_spacing: Quantity, order: int = 1) -> float:
    """The Bragg reflection angle, theta = arcsin(n*lambda/(2*d)).

    The angle (from the crystal plane) at which X-rays of ``wavelength`` lambda reflect in phase off
    planes of spacing ``plane_spacing`` d, for diffraction ``order`` n: n*lambda = 2*d*sin(theta).
    It is where an X-ray diffractometer sees a peak. The order exists only if n*lambda <= 2*d (else
    the sine exceeds one and there is no reflection). Returns the Bragg angle in degrees.
    """
    _check(wavelength, "[length]", "wavelength")
    _check(plane_spacing, "[length]", "plane_spacing")
    lam = wavelength.to("m").magnitude
    d = plane_spacing.to("m").magnitude
    if lam <= 0:
        raise _diffraction_refusal(
            "wavelength must be positive", subject="wavelength", source=_SOURCE_SPEC_SOURCE
        )
    if d <= 0:
        raise _diffraction_refusal(
            "plane_spacing must be positive", subject="plane_spacing", source=_CRYSTAL_SOURCE
        )
    if order < 1:
        raise _diffraction_refusal(
            "order must be a positive integer", subject="order", source=_SETUP_SOURCE
        )
    ratio = order * lam / (2.0 * d)
    if ratio > 1.0:
        raise _diffraction_refusal(
            "no Bragg reflection at this order: n*lambda exceeds 2*d (the wavelength is too long)",
            subject="wavelength, plane_spacing, and order",
            source=_SETUP_SOURCE,
        )
    return degrees(asin(ratio))


def bragg_plane_spacing(*, wavelength: Quantity, angle: float, order: int = 1) -> Quantity:
    """The crystal plane spacing from a Bragg angle, d = n*lambda/(2*sin(theta)).

    The materials-characterization inverse of :func:`bragg_angle`: the atomic ``plane_spacing`` d a
    measured Bragg ``angle`` theta (degrees) implies for X-rays of ``wavelength`` lambda at
    diffraction ``order`` n, d = n*lambda/(2*sin(theta)). It is how X-ray diffraction turns a peak
    position into the lattice spacing that fingerprints a crystalline phase. Returns d as a length.
    """
    _check(wavelength, "[length]", "wavelength")
    lam = wavelength.to("m").magnitude
    if lam <= 0:
        raise _diffraction_refusal(
            "wavelength must be positive", subject="wavelength", source=_SOURCE_SPEC_SOURCE
        )
    if order < 1:
        raise _diffraction_refusal(
            "order must be a positive integer", subject="order", source=_SETUP_SOURCE
        )
    if not 0.0 < angle < 90.0:
        raise _diffraction_refusal(
            "angle must be in (0, 90) degrees", subject="angle", source=_SETUP_SOURCE
        )
    return Quantity(magnitude=order * lam / (2.0 * sin(radians(angle))), unit="m")


def grating_diffraction_angle(
    *, wavelength: Quantity, groove_spacing: Quantity, order: int = 1
) -> float:
    """The grating diffraction angle, theta = arcsin(m*lambda/D).

    The angle a diffraction grating of groove spacing ``groove_spacing`` D sends the ``order`` m
    diffraction of ``wavelength`` lambda to: m*lambda = D*sin(theta). A grating disperses a spectrum
    because longer wavelengths diffract to larger angles. The order exists only if m*lambda <= D.
    Returns the diffraction angle in degrees.
    """
    _check(wavelength, "[length]", "wavelength")
    _check(groove_spacing, "[length]", "groove_spacing")
    lam = wavelength.to("m").magnitude
    d = groove_spacing.to("m").magnitude
    if lam <= 0:
        raise _diffraction_refusal(
            "wavelength must be positive", subject="wavelength", source=_SOURCE_SPEC_SOURCE
        )
    if d <= 0:
        raise _diffraction_refusal(
            "groove_spacing must be positive", subject="groove_spacing", source=_GRATING_SOURCE
        )
    if order < 1:
        raise _diffraction_refusal(
            "order must be a positive integer", subject="order", source=_SETUP_SOURCE
        )
    ratio = order * lam / d
    if ratio > 1.0:
        raise _diffraction_refusal(
            "no diffraction at this order: m*lambda exceeds the groove spacing D",
            subject="wavelength, groove_spacing, and order",
            source=_SETUP_SOURCE,
        )
    return degrees(asin(ratio))


def grating_resolving_power(*, order: int = 1, illuminated_lines: int) -> float:
    """The grating resolving power, R = m*N = lambda/dlambda.

    How finely a grating can separate two close wavelengths: R = lambda/dlambda = m*N, set only by
    the diffraction ``order`` m and the number of grooves ``illuminated_lines`` N the beam actually
    covers — not by the groove spacing. Working in a higher order or flooding more of the grating
    both sharpen it, which is why a spectrometer's resolution scales with beam width. ``order`` and
    ``illuminated_lines`` are positive integers. Returns the dimensionless resolving power.
    """
    if order < 1:
        raise _diffraction_refusal(
            "order must be a positive integer", subject="order", source=_SETUP_SOURCE
        )
    if illuminated_lines < 1:
        raise _diffraction_refusal(
            "illuminated_lines must be a positive integer",
            subject="illuminated_lines",
            source=_GRATING_SOURCE,
        )
    return float(order * illuminated_lines)


def grating_resolved_wavelength_separation(
    *, wavelength: Quantity, order: int = 1, illuminated_lines: int
) -> Quantity:
    """The smallest wavelength gap a grating resolves, dlambda = lambda/(m*N).

    The application of :func:`grating_resolving_power`: two spectral lines near ``wavelength``
    lambda are just separated (the Rayleigh criterion) when their spacing reaches lambda/(m*N),
    for diffraction ``order`` m and ``illuminated_lines`` N grooves lit. A finer gap blurs into one
    line. ``wavelength`` is a length; ``order`` and ``illuminated_lines`` are positive integers.
    Returns the resolvable wavelength separation as a length.
    """
    _check(wavelength, "[length]", "wavelength")
    lam = wavelength.to("m").magnitude
    if lam <= 0:
        raise _diffraction_refusal(
            "wavelength must be positive", subject="wavelength", source=_SOURCE_SPEC_SOURCE
        )
    if order < 1:
        raise _diffraction_refusal(
            "order must be a positive integer", subject="order", source=_SETUP_SOURCE
        )
    if illuminated_lines < 1:
        raise _diffraction_refusal(
            "illuminated_lines must be a positive integer",
            subject="illuminated_lines",
            source=_GRATING_SOURCE,
        )
    return Quantity(magnitude=lam / (order * illuminated_lines), unit="m")


def grating_angular_dispersion(
    *, groove_spacing: Quantity, diffraction_angle: float, order: int = 1
) -> Quantity:
    """The grating angular dispersion, D = dtheta/dlambda = m/(D_g*cos(theta)).

    How fast a grating spreads angle with wavelength — the slope that sets how far apart a detector
    sees two colors: differentiating the grating equation gives dtheta/dlambda = m/(D_g*cos(theta)),
    for diffraction ``order`` m, groove spacing ``groove_spacing`` D_g, and the angle
    ``diffraction_angle`` theta (degrees, in [0, 90)) from :func:`grating_diffraction_angle`.
    Dispersion grows toward grazing angles and in higher orders. Returns the dispersion in rad/m.
    """
    _check(groove_spacing, "[length]", "groove_spacing")
    d = groove_spacing.to("m").magnitude
    if d <= 0:
        raise _diffraction_refusal(
            "groove_spacing must be positive", subject="groove_spacing", source=_GRATING_SOURCE
        )
    if order < 1:
        raise _diffraction_refusal(
            "order must be a positive integer", subject="order", source=_SETUP_SOURCE
        )
    if not 0.0 <= diffraction_angle < 90.0:
        raise _diffraction_refusal(
            "diffraction_angle must be in [0, 90) degrees",
            subject="diffraction_angle",
            source=_SETUP_SOURCE,
        )
    return Quantity(magnitude=order / (d * cos(radians(diffraction_angle))), unit="rad/m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _diffraction_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_diffraction_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _diffraction_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_diffraction_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
