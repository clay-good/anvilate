"""T1 analytical thin-film anti-reflection coating checks (closed-form).

A thin transparent coating on a lens or panel can cancel its surface reflection by interference: the
wave reflected from the coating's top surface and the one from the coating-substrate interface
arrive out of phase and subtract. This is how camera lenses, eyeglasses, and solar-panel cover glass
are made to reflect less and transmit more. It is wave-interference optics, distinct from the
crystal and grating diffraction of :mod:`anvilate.analysis.diffraction` (one film, not an array).

The coating works best when it is a quarter-wavelength thick in the film, t = lambda/(4*n), so the
round-trip path adds half a wavelength and the two reflections cancel — the standard single-layer
anti-reflection coating. The cancellation is most complete when the coating's refractive index is
the geometric mean of the two media it sits between, n = sqrt(n_medium * n_substrate) (why MgF2, n
about 1.38, suits glass). Inverting the thickness relation gives the wavelength a coating is tuned
to, lambda = 4*n*t — so a coating optimized for green light reflects more in the red and blue.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "optimal_ar_coating_index",
    "quarter_wave_thickness",
    "thin_film_tuned_wavelength",
]


def quarter_wave_thickness(*, wavelength: Quantity, coating_index: float) -> Quantity:
    """The quarter-wave anti-reflection coating thickness, t = lambda/(4*n).

    The minimum physical thickness of a single-layer AR coating of refractive index
    ``coating_index`` n that cancels the reflection of ``wavelength`` lambda: a quarter of the
    wavelength within the film, t = lambda/(4*n). About 100 nm for green light on a typical fluoride
    coating. Returns the coating thickness in m.
    """
    _check(wavelength, "[length]", "wavelength")
    lam = wavelength.to("m").magnitude
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    if coating_index <= 0:
        raise ValueError("coating_index must be positive")
    return Quantity(magnitude=lam / (4.0 * coating_index), unit="m")


def optimal_ar_coating_index(*, substrate_index: float, medium_index: float = 1.0) -> float:
    """The ideal AR coating index, n = sqrt(n_medium * n_substrate).

    The refractive index a single-layer coating should have to cancel reflection completely: the
    geometric mean of the ``medium_index`` (the medium the light comes from, air = 1) and the
    ``substrate_index`` it coats, n = sqrt(n_medium * n_substrate). A real material is picked close
    to this ideal (MgF2 at 1.38 for glass at ~1.5). Returns the index as a plain float.
    """
    if substrate_index <= 0:
        raise ValueError("substrate_index must be positive")
    if medium_index <= 0:
        raise ValueError("medium_index must be positive")
    return sqrt(medium_index * substrate_index)


def thin_film_tuned_wavelength(*, thickness: Quantity, coating_index: float) -> Quantity:
    """The wavelength a coating is tuned to, lambda = 4*n*t.

    The inverse of :func:`quarter_wave_thickness`: the wavelength a quarter-wave coating of
    ``thickness`` t and refractive index ``coating_index`` n cancels most strongly, lambda = 4*n*t.
    A coating optimized for one color reflects more at other wavelengths, which is the residual
    purple tint of many AR-coated lenses. Returns the tuned wavelength in m.
    """
    _check(thickness, "[length]", "thickness")
    t = thickness.to("m").magnitude
    if t <= 0:
        raise ValueError("thickness must be positive")
    if coating_index <= 0:
        raise ValueError("coating_index must be positive")
    return Quantity(magnitude=4.0 * coating_index * t, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
