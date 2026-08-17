"""Rotational speed: the one unit trap the dimension check cannot catch.

Pint's radian is dimensionless, so ``rad/s``, ``Hz``, and ``1/s`` all carry the same
dimensionality — plain inverse time. A rotational speed given as ``Quantity(100, "Hz")``
therefore converts to ``100 rad/s``, not the ``628.3 rad/s`` the writer meant, and every
dimension check in the library passes it. A function that means "revolutions per unit
time" then reads 100 rev/s as 15.9 rev/s: torque, power, friction, and bearing heat all
come out low by exactly 2π. The error is silent, dimensionally legal, and *unconservative*
in every case — the worst failure mode a screening library has.

:func:`angular_speed_rad_per_s` closes the hole. It accepts only a speed whose unit
actually names an angle (``rad/s``, ``deg/s``, ``rpm``, ``turn/s``) and rejects a bare
inverse time (``Hz``, ``1/s``, ``1/min``) with a message naming the spelling to use.
Rejecting is the only safe answer: ``rad/s`` and ``Hz`` are indistinguishable to the
dimension system, so a guess would be wrong 2π-fold half the time.
"""

from __future__ import annotations

from math import pi

from .quantity import Quantity, UnitError
from .registry import UREG

__all__ = [
    "AmbiguousRotationalSpeedError",
    "angular_speed_rad_per_s",
    "revolutions_per_minute",
    "revolutions_per_second",
]

# Unit-name fragments that mark a quantity as carrying a genuine angle. Pint spells
# rpm as "revolutions_per_minute" and rev/min as "turn / minute", so matching on
# fragments covers every spelling of the same physical unit.
# Matched against pint's CANONICAL spelling of the unit, which is not always the one written:
# "gradian" canonicalises to "grade" and "rpm" to "revolutions_per_minute", so the fragments have
# to cover what pint prints, not what the caller typed.
_ANGLE_TOKENS = (
    "radian",
    "degree",
    "grade",
    "turn",
    "revolution",
    "cycle",
    "arcminute",
    "arcsecond",
)


class AmbiguousRotationalSpeedError(UnitError):
    """A rotational speed was given in a unit that does not name an angle."""


def angular_speed_rad_per_s(speed: Quantity, *, name: str) -> float:
    """The angular speed ω in rad/s, rejecting a unit that does not name an angle.

    ``speed`` must be spelled with an angle in it — ``rad/s``, ``deg/s``, ``rpm``, or
    ``turn/s``. A bare inverse time (``Hz``, ``1/s``, ``1/min``) is refused because pint
    cannot tell it apart from ``rad/s``: the two differ by 2π and share a dimensionality,
    so accepting either spelling would silently return one of them 2π-fold wrong. ``name``
    is the caller's parameter name, echoed in the error so the fix is obvious.
    """
    unit_text = str(UREG.Unit(speed.unit))
    if not any(token in unit_text for token in _ANGLE_TOKENS):
        raise AmbiguousRotationalSpeedError(
            f"{name} was given as {speed} — a bare inverse time, which pint cannot tell "
            f"apart from rad/s (they differ by 2*pi and share a dimensionality). State "
            f"the angle: use 'rpm' or 'revolution/minute' for revolutions per minute, "
            f"'turn/s' for "
            f"revolutions per second, or 'rad/s' for a true angular rate."
        )
    return speed.to("rad/s").magnitude


def revolutions_per_second(speed: Quantity, *, name: str) -> float:
    """The rotational speed n in revolutions per second, guarded as above.

    The companion to :func:`angular_speed_rad_per_s` for the many formulas written in
    revolutions rather than radians (Petroff's law, rolling-mill power, pump specific
    speed): n = ω/(2π), with the same refusal of an angle-free unit.
    """
    return angular_speed_rad_per_s(speed, name=name) / (2.0 * pi)


def revolutions_per_minute(speed: Quantity, *, name: str) -> float:
    """The rotational speed in rpm, guarded as in :func:`angular_speed_rad_per_s`.

    The third face of the same conversion, for formulas and standards written in rpm — ISO 281
    bearing life, induction-motor slip. Converting straight with ``.to("rpm")`` looks like it
    sidesteps the radian problem and does not: pint's revolution is 2π radian, so ``.to("rpm")``
    applies exactly the same 2π factor as ``.to("rad/s")`` and reads 30 Hz as 286.5 rpm rather
    than 1800.
    """
    return angular_speed_rad_per_s(speed, name=name) * 60.0 / (2.0 * pi)
