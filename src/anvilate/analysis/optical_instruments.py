"""T1 analytical optical-instrument magnification checks (closed-form).

A telescope, a magnifying glass, and a microscope all make things look bigger, but each does it a
different way, and the angular magnification — how much larger an object subtends at the eye —
follows from the instrument's focal lengths. This is the design arithmetic of visual instruments,
distinct from the single-lens imaging (image distance and transverse magnification) of
:mod:`anvilate.analysis.optics`: here the concern is the angular size an eye perceives through a
multi-element system.

A telescope's angular magnification is M = f_o/f_e, the objective focal length over the eyepiece
focal length — a long objective and short eyepiece give high power. A simple magnifier held for a
relaxed eye gives M = D/f, the near-point distance D (about 250 mm for a normal eye) over the lens
focal length f. A compound microscope multiplies the objective's linear magnification L/f_o (from
the tube length L) by the eyepiece's angular magnification D/f_e, for M = (L/f_o)*(D/f_e). All three
return a dimensionless magnification.

Sources: Hecht, *Optics* (optical instruments) — the angular magnification of a telescope from
its focal lengths, of a simple magnifier at the near point, and the compound-microscope product
of objective and eyepiece.
"""

from __future__ import annotations

from ..units import Quantity

_NEAR_POINT = 0.25  # m, standard least distance of distinct vision (250 mm)

__all__ = [
    "magnifier_angular_magnification",
    "microscope_magnification",
    "telescope_angular_magnification",
]


def telescope_angular_magnification(
    *, objective_focal_length: Quantity, eyepiece_focal_length: Quantity
) -> float:
    """The telescope angular magnification, M = f_o/f_e.

    The factor by which a telescope enlarges the angular size of a distant object: the
    ``objective_focal_length`` f_o over the ``eyepiece_focal_length`` f_e, M = f_o/f_e. A long
    objective and a short eyepiece give high magnification (but a narrower field). Returns the
    magnification as a plain float.
    """
    _check(objective_focal_length, "[length]", "objective_focal_length")
    _check(eyepiece_focal_length, "[length]", "eyepiece_focal_length")
    f_o = objective_focal_length.to("m").magnitude
    f_e = eyepiece_focal_length.to("m").magnitude
    if f_o <= 0:
        raise ValueError("objective_focal_length must be positive")
    if f_e <= 0:
        raise ValueError("eyepiece_focal_length must be positive")
    return f_o / f_e


def magnifier_angular_magnification(
    *, focal_length: Quantity, near_point: Quantity | None = None
) -> float:
    """The simple-magnifier angular magnification, M = D/f.

    The angular magnification of a single-lens magnifier for a relaxed eye (image at infinity): the
    ``near_point`` distance D (the least distance of distinct vision, defaulting to 250 mm) over the
    lens ``focal_length`` f, M = D/f. A shorter focal length magnifies more. Returns a plain float.
    """
    _check(focal_length, "[length]", "focal_length")
    f = focal_length.to("m").magnitude
    if f <= 0:
        raise ValueError("focal_length must be positive")
    if near_point is None:
        d = _NEAR_POINT
    else:
        _check(near_point, "[length]", "near_point")
        d = near_point.to("m").magnitude
        if d <= 0:
            raise ValueError("near_point must be positive")
    return d / f


def microscope_magnification(
    *,
    tube_length: Quantity,
    objective_focal_length: Quantity,
    eyepiece_focal_length: Quantity,
    near_point: Quantity | None = None,
) -> float:
    """The compound-microscope magnification, M = (L/f_o)*(D/f_e).

    The total magnification of a compound microscope: the objective's linear magnification (the
    ``tube_length`` L over the ``objective_focal_length`` f_o) times the eyepiece's angular
    magnification (``near_point`` D over ``eyepiece_focal_length`` f_e), M = (L/f_o)*(D/f_e).
    Short objective and eyepiece focal lengths give the high powers a microscope needs. Returns a
    plain float.
    """
    _check(tube_length, "[length]", "tube_length")
    _check(objective_focal_length, "[length]", "objective_focal_length")
    _check(eyepiece_focal_length, "[length]", "eyepiece_focal_length")
    length = tube_length.to("m").magnitude
    f_o = objective_focal_length.to("m").magnitude
    f_e = eyepiece_focal_length.to("m").magnitude
    if length <= 0:
        raise ValueError("tube_length must be positive")
    if f_o <= 0:
        raise ValueError("objective_focal_length must be positive")
    if f_e <= 0:
        raise ValueError("eyepiece_focal_length must be positive")
    if near_point is None:
        d = _NEAR_POINT
    else:
        _check(near_point, "[length]", "near_point")
        d = near_point.to("m").magnitude
        if d <= 0:
            raise ValueError("near_point must be positive")
    return (length / f_o) * (d / f_e)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
