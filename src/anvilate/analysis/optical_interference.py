"""T1 analytical two-beam and single-slit optical interference (closed-form).

When coherent light passes through two close slits it recombines on a distant screen into a pattern
of bright and dark bands — Young's fringes — the experiment that first proved light is a wave and
measured its wavelength. The geometry is all closed-form, and it is distinct from the wavelength-
scale scattering of a diffraction grating (:mod:`anvilate.analysis.diffraction`, many slits) and
from the ray optics of :mod:`anvilate.analysis.optics`.

Two slits a distance d apart, lit by light of wavelength λ, send bright fringes to angles where the
path difference is a whole wavelength, sin θ = m·λ/d; projected onto a screen a distance L away
(L ≫ d) the bright bands are evenly spaced by Δy = λ·L/d. Inverting that spacing is how the
experiment yields the wavelength, λ = Δy·d/L. A single slit of width a instead casts a diffraction
envelope whose dark fringes fall at sin θ = m·λ/a — the finite width that ultimately blurs the
two-slit fringes. Wavelengths, slit dimensions, and fringe spacings are dimension-checked
:class:`~anvilate.units.Quantity` values; angles are plain floats in degrees.

Sources: Hecht, *Optics* (interference and single-slit diffraction) — the double-slit fringe
spacing and angle, the single-slit minima, and the wavelength a measured fringe spacing infers.
"""

from __future__ import annotations

from math import asin, degrees

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_SOURCE_SOURCE = "the light source's datasheet wavelength"
_APERTURE_SOURCE = "the slit manufacturer's specification (slit width and separation)"
_BENCH_SOURCE = "the optical bench setup record (screen distance and order)"
_MEASUREMENT_SOURCE = "the measured fringe spacing on the screen"


class _OpticalInterferenceInputError(RefusalError, ValueError):
    """An optical-interference input that cannot be used without correction."""


def _optical_interference_refusal(
    message: str, *, subject: str, source: str
) -> _OpticalInterferenceInputError:
    return _OpticalInterferenceInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _optical_interference_input_source(name: str) -> str:
    if name == "wavelength":
        return _SOURCE_SOURCE
    if name in {"order", "screen_distance"}:
        return _BENCH_SOURCE
    if name == "fringe_spacing":
        return _MEASUREMENT_SOURCE
    return _APERTURE_SOURCE


__all__ = [
    "double_slit_fringe_spacing",
    "double_slit_fringe_angle",
    "single_slit_minimum_angle",
    "wavelength_from_fringe_spacing",
]


def double_slit_fringe_spacing(
    *, wavelength: Quantity, slit_separation: Quantity, screen_distance: Quantity
) -> Quantity:
    """The spacing of Young's double-slit fringes, Δy = λ·L/d.

    The even spacing between adjacent bright (or dark) bands on a screen a distance
    ``screen_distance`` L behind two slits ``slit_separation`` d apart, lit by ``wavelength`` λ:
    Δy = λ·L/d, valid in the small-angle (L ≫ d) limit. Fringes spread with a longer wavelength or a
    farther screen and crowd together as the slits move apart — the trade a two-slit measurement is
    set up around. Returns the fringe spacing as a length.
    """
    _check(wavelength, "[length]", "wavelength")
    _check(slit_separation, "[length]", "slit_separation")
    _check(screen_distance, "[length]", "screen_distance")
    lam = wavelength.to("m").magnitude
    d = slit_separation.to("m").magnitude
    ell = screen_distance.to("m").magnitude
    if lam <= 0:
        raise _optical_interference_refusal(
            "wavelength must be positive", subject="wavelength", source=_SOURCE_SOURCE
        )
    if d <= 0:
        raise _optical_interference_refusal(
            "slit_separation must be positive", subject="slit_separation", source=_APERTURE_SOURCE
        )
    if ell <= 0:
        raise _optical_interference_refusal(
            "screen_distance must be positive", subject="screen_distance", source=_BENCH_SOURCE
        )
    return Quantity(magnitude=lam * ell / d, unit="m")


def double_slit_fringe_angle(
    *, wavelength: Quantity, slit_separation: Quantity, order: int = 1
) -> float:
    """The angle of a double-slit bright fringe, θ = arcsin(m·λ/d).

    The exact angular position of the ``order`` m bright fringe (m = 0 is the central maximum): the
    two beams reinforce where their path difference is a whole number of wavelengths, d·sin θ = m·λ,
    so θ = arcsin(m·λ/d), from the ``wavelength`` λ and ``slit_separation`` d. Unlike the
    small-angle :func:`double_slit_fringe_spacing` this holds at any angle. An order exists only
    while m·λ ≤ d;
    beyond that the sine exceeds one and the fringe is not formed. Returns the fringe angle in
    degrees.
    """
    _check(wavelength, "[length]", "wavelength")
    _check(slit_separation, "[length]", "slit_separation")
    lam = wavelength.to("m").magnitude
    d = slit_separation.to("m").magnitude
    if lam <= 0:
        raise _optical_interference_refusal(
            "wavelength must be positive", subject="wavelength", source=_SOURCE_SOURCE
        )
    if d <= 0:
        raise _optical_interference_refusal(
            "slit_separation must be positive", subject="slit_separation", source=_APERTURE_SOURCE
        )
    if order < 0:
        raise _optical_interference_refusal(
            "order must be a non-negative integer", subject="order", source=_BENCH_SOURCE
        )
    ratio = order * lam / d
    if ratio > 1.0:
        raise _optical_interference_refusal(
            "no fringe at this order: m*lambda exceeds the slit separation d",
            subject="wavelength, slit_separation, and order",
            source=_BENCH_SOURCE,
        )
    return degrees(asin(ratio))


def single_slit_minimum_angle(
    *, wavelength: Quantity, slit_width: Quantity, order: int = 1
) -> float:
    """The angle of a single-slit diffraction minimum, θ = arcsin(m·λ/a).

    A single slit of width ``slit_width`` a spreads light into a diffraction envelope whose dark
    bands fall where the slit's own halves cancel, a·sin θ = m·λ (m = 1, 2, … — there is no m = 0
    minimum, that is the central bright peak): θ = arcsin(m·λ/a), from the ``wavelength`` λ. The
    narrower the slit, the wider the central lobe — the finite-width envelope that modulates and
    eventually washes out two-slit fringes. An order exists only while m·λ ≤ a. Returns the minimum
    angle in degrees.
    """
    _check(wavelength, "[length]", "wavelength")
    _check(slit_width, "[length]", "slit_width")
    lam = wavelength.to("m").magnitude
    a = slit_width.to("m").magnitude
    if lam <= 0:
        raise _optical_interference_refusal(
            "wavelength must be positive", subject="wavelength", source=_SOURCE_SOURCE
        )
    if a <= 0:
        raise _optical_interference_refusal(
            "slit_width must be positive", subject="slit_width", source=_APERTURE_SOURCE
        )
    if order < 1:
        raise _optical_interference_refusal(
            "order must be a positive integer (there is no m = 0 minimum)",
            subject="order",
            source=_BENCH_SOURCE,
        )
    ratio = order * lam / a
    if ratio > 1.0:
        raise _optical_interference_refusal(
            "no minimum at this order: m*lambda exceeds the slit width a",
            subject="wavelength, slit_width, and order",
            source=_BENCH_SOURCE,
        )
    return degrees(asin(ratio))


def wavelength_from_fringe_spacing(
    *, fringe_spacing: Quantity, slit_separation: Quantity, screen_distance: Quantity
) -> Quantity:
    """The wavelength from a measured fringe spacing, λ = Δy·d/L.

    The measurement inverse of :func:`double_slit_fringe_spacing`, and how Young's experiment yields
    the wavelength: from the observed ``fringe_spacing`` Δy, the ``slit_separation`` d, and the
    ``screen_distance`` L, λ = Δy·d/L. Measuring many fringes at once (a large Δy over many bands)
    sharpens the estimate. Returns the wavelength as a length.
    """
    _check(fringe_spacing, "[length]", "fringe_spacing")
    _check(slit_separation, "[length]", "slit_separation")
    _check(screen_distance, "[length]", "screen_distance")
    dy = fringe_spacing.to("m").magnitude
    d = slit_separation.to("m").magnitude
    ell = screen_distance.to("m").magnitude
    if dy <= 0:
        raise _optical_interference_refusal(
            "fringe_spacing must be positive", subject="fringe_spacing", source=_MEASUREMENT_SOURCE
        )
    if d <= 0:
        raise _optical_interference_refusal(
            "slit_separation must be positive", subject="slit_separation", source=_APERTURE_SOURCE
        )
    if ell <= 0:
        raise _optical_interference_refusal(
            "screen_distance must be positive", subject="screen_distance", source=_BENCH_SOURCE
        )
    return Quantity(magnitude=dy * d / ell, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _optical_interference_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_optical_interference_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _optical_interference_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_optical_interference_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
