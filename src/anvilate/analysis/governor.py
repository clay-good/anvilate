"""T1 analytical centrifugal-governor checks (closed-form).

A flyball governor regulates an engine's speed by letting spinning weights rise against gravity: as
the shaft turns faster, the balls fly outward and up, and the linkage they drive closes the
throttle. The equilibrium geometry balances centrifugal action against weight, which fixes a
definite governor height for each running speed — the feedback that made the steam engine
self-regulating.
This joins the other rotating-mechanism kinematics of :mod:`anvilate.analysis.flywheel`.

For the simple Watt governor the height h (the vertical drop from the pivot to the plane of the
rotating balls) depends only on the speed: h = g/ω², so the balls hang lower at high speed and the
governor loses sensitivity as it speeds up. Inverting it gives the running speed from a measured
height, ω = √(g/h). Adding a central load turns it into a Porter governor, whose height
h = (g/ω²)·(m + M)/m is raised by the ratio of the central load M to the ball mass m — which makes
the governor stiffer and usable at higher speeds. The **angular speed is taken in genuine angular
units** (rad/s); inputs and outputs are dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity
from ..units.rotation import angular_speed_rad_per_s

_GRAVITY = 9.80665  # m/s**2

__all__ = [
    "porter_governor_height",
    "watt_governor_height",
    "watt_governor_speed",
]


def watt_governor_height(*, angular_speed: Quantity) -> Quantity:
    """The Watt-governor height, h = g/ω².

    The vertical distance from the pivot to the plane of the rotating balls at equilibrium, from the
    ``angular_speed`` ω: h = g/ω². It falls with the square of speed, so a Watt governor grows less
    sensitive the faster it runs. Returns the governor height in m.
    """
    _check(angular_speed, "1/[time]", "angular_speed")
    omega = angular_speed_rad_per_s(angular_speed, name="angular_speed")
    if omega <= 0:
        raise ValueError("angular_speed must be positive")
    return Quantity(magnitude=_GRAVITY / (omega * omega), unit="m")


def watt_governor_speed(*, height: Quantity) -> Quantity:
    """The Watt-governor speed, ω = √(g/h).

    The running speed a Watt governor settles at for a measured ``height`` h, by inverting the
    height relation: ω = √(g/h). A lower ball position corresponds to a higher speed. Returns the
    angular speed in rad/s.
    """
    _check(height, "[length]", "height")
    h = height.to("m").magnitude
    if h <= 0:
        raise ValueError("height must be positive")
    return Quantity(magnitude=sqrt(_GRAVITY / h), unit="rad/s")


def porter_governor_height(
    *, angular_speed: Quantity, ball_mass: Quantity, central_load: Quantity
) -> Quantity:
    """The Porter-governor height, h = (g/ω²)·(m + M)/m.

    The equilibrium height of a Porter governor — a Watt governor with a central load — from the
    ``angular_speed`` ω, the ``ball_mass`` m, and the ``central_load`` M (arms pivoted on the axis,
    friction neglected): h = (g/ω²)·(m + M)/m. The central load lifts the height by the
    factor (m + M)/m, stiffening the governor and letting it work at higher speeds. Reduces to the
    Watt case when M = 0. Returns the governor height in m.
    """
    _check(angular_speed, "1/[time]", "angular_speed")
    _check(ball_mass, "[mass]", "ball_mass")
    _check(central_load, "[mass]", "central_load")
    omega = angular_speed_rad_per_s(angular_speed, name="angular_speed")
    m = ball_mass.to("kg").magnitude
    big_m = central_load.to("kg").magnitude
    if omega <= 0:
        raise ValueError("angular_speed must be positive")
    if m <= 0:
        raise ValueError("ball_mass must be positive")
    if big_m < 0:
        raise ValueError("central_load must be non-negative")
    return Quantity(magnitude=(_GRAVITY / (omega * omega)) * (m + big_m) / m, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
