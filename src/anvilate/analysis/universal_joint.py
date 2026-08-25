"""T1 analytical universal-joint (Cardan/Hooke) kinematics checks (closed-form).

A single Cardan universal joint transmits rotation between two shafts meeting at an angle, but not
uniformly: even at constant input speed the output speeds up and slows down twice per
revolution. This velocity ripple is the price of the angle, and it is why drivelines use two joints
out of phase (or a constant-velocity joint) to cancel it. This joins the other intermittent- and
non-uniform-motion mechanisms of :mod:`anvilate.analysis.geneva` and
:mod:`anvilate.analysis.scotch_yoke`.

The instantaneous speed ratio is ω₂/ω₁ = cosβ/(1 − sin²β·cos²θ), from the shaft misalignment β and
the input rotation angle θ. It swings between a maximum of 1/cosβ (when the input fork lies in the
plane of the shafts) and a minimum of cosβ (a quarter-turn later), so the peak-to-peak speed
fluctuation over a revolution is 1/cosβ − cosβ. The larger the joint angle, the worse the ripple —
which is why single Cardan joints are kept to small angles. Angles are **plain floats in degrees**;
the returned ratios are dimensionless plain floats.

Sources: Norton, *Design of Machinery* (Hooke's coupling) — the non-constant output-to-input
speed ratio of a single Cardan joint at an operating angle, its maximum, and the peak-to-peak
fluctuation over a revolution.
"""

from __future__ import annotations

from math import cos, radians, sin

__all__ = [
    "universal_joint_max_speed_ratio",
    "universal_joint_speed_fluctuation",
    "universal_joint_speed_ratio",
]


def universal_joint_speed_ratio(*, shaft_angle: float, input_angle: float) -> float:
    """The instantaneous speed ratio, ω₂/ω₁ = cosβ/(1 − sin²β·cos²θ).

    The output-to-input angular-speed ratio of a single Cardan joint, from the ``shaft_angle`` β
    (the misalignment between the shafts) and the ``input_angle`` θ (the driver's rotation), both
    plain floats in degrees: ω₂/ω₁ = cosβ/(1 − sin²β·cos²θ). It rises above 1 and falls below it
    twice per revolution. Returns the speed ratio as a plain float.
    """
    if not 0.0 <= shaft_angle < 90.0:
        raise ValueError(f"shaft_angle must be in [0, 90) degrees; got {shaft_angle}")
    beta = radians(shaft_angle)
    theta = radians(input_angle)
    return cos(beta) / (1.0 - sin(beta) ** 2 * cos(theta) ** 2)


def universal_joint_max_speed_ratio(*, shaft_angle: float) -> float:
    """The maximum speed ratio over a revolution, (ω₂/ω₁)_max = 1/cosβ.

    The largest instantaneous output-to-input speed ratio a single Cardan joint reaches, from the
    ``shaft_angle`` β (a plain float in degrees): 1/cosβ, occurring when the driving fork lies in
    the plane of the two shafts. The minimum a quarter-turn later is cosβ. Returns the ratio as a
    float (≥ 1).
    """
    if not 0.0 <= shaft_angle < 90.0:
        raise ValueError(f"shaft_angle must be in [0, 90) degrees; got {shaft_angle}")
    return 1.0 / cos(radians(shaft_angle))


def universal_joint_speed_fluctuation(*, shaft_angle: float) -> float:
    """The peak-to-peak speed fluctuation, 1/cosβ − cosβ.

    The swing in the output-to-input speed ratio over one revolution of a single Cardan joint, from
    the ``shaft_angle`` β (a plain float in degrees): (ω₂/ω₁)_max − (ω₂/ω₁)_min = 1/cosβ − cosβ. It
    grows steeply with the joint angle, which is why single joints are kept small or paired to
    cancel the ripple. Returns the fluctuation as a plain float.
    """
    if not 0.0 <= shaft_angle < 90.0:
        raise ValueError(f"shaft_angle must be in [0, 90) degrees; got {shaft_angle}")
    c = cos(radians(shaft_angle))
    return 1.0 / c - c
