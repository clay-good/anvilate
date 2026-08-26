"""T1 analytical ball-screw drive checks (closed-form).

A ball screw turns rotation into linear motion through recirculating balls instead of sliding
threads, so it is far more efficient than the acme power screw — which changes both how it is sized
and how it must be held.

Driving a load takes a torque set by the lead and the efficiency: T = F·L/(2π·η), from the axial
``load`` F, the screw ``lead`` L (the linear travel per turn), and the forward ``efficiency`` η
(~0.9 for a ball screw, against ~0.3–0.5 for an acme screw). This is the torque the motor must
deliver to push the load.

The same low friction means a ball screw is *not self-locking*: an axial load will back-drive it,
spinning the motor unless a brake holds it. The back-driving torque the load applies is
T_b = F·L·η_b/(2π), with the back-drive efficiency η_b — the torque a holding brake (or the motor's
detent) must resist to keep a suspended or preloaded axis from creeping. The efficiencies are the
caller's from the screw's data; the torque balance is here.

Sources: *Machinery's Handbook* (ball and lead screws) — the drive torque a thrust load needs at
a lead and efficiency, and the back-drive torque the same load produces when the screw is not
self-locking.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

__all__ = [
    "ball_screw_back_drive_torque",
    "ball_screw_drive_torque",
]


def ball_screw_drive_torque(
    *,
    axial_load: Quantity,
    lead: Quantity,
    efficiency: float,
) -> Quantity:
    """The torque to drive a load along a ball screw, T = F·L/(2π·η).

    The motor torque to push an ``axial_load`` F along a ball screw of ``lead`` L (travel per
    revolution) at a forward ``efficiency`` η: T = F·L/(2π·η). A coarser lead moves the load faster
    but needs proportionally more torque, and the high efficiency of a ball screw (η ≈ 0.9) is why
    it needs far less motor than an acme screw for the same push. Efficiency must be in (0, 1].
    Returns the drive torque in N·m.
    """
    _check(axial_load, "[force]", "axial_load")
    _check(lead, "[length]", "lead")
    f = axial_load.to("N").magnitude
    length = lead.to("m").magnitude
    if f <= 0 or length <= 0:
        raise ValueError("axial_load and lead must be positive")
    if not 0.0 < efficiency <= 1.0:
        raise ValueError(f"efficiency must be in (0, 1]; got {efficiency}")
    return Quantity(magnitude=f * length / (2.0 * pi * efficiency), unit="N*m")


def ball_screw_back_drive_torque(
    *,
    axial_load: Quantity,
    lead: Quantity,
    back_drive_efficiency: float,
) -> Quantity:
    """The torque an axial load back-drives through a ball screw, T_b = F·L·η_b/(2π).

    A ball screw is not self-locking, so an ``axial_load`` F tries to spin it backward with a torque
    T_b = F·L·η_b/(2π), from the ``lead`` L and the ``back_drive_efficiency`` η_b. This is the
    torque a holding brake (or the motor's own detent torque) must resist to stop a vertical or
    preloaded axis from creeping under load when the drive is unpowered — the reason a ball-screw
    lift needs a brake and an acme-screw one often does not. η_b must be in (0, 1]. Returns the
    back-driving torque in N·m.
    """
    _check(axial_load, "[force]", "axial_load")
    _check(lead, "[length]", "lead")
    f = axial_load.to("N").magnitude
    length = lead.to("m").magnitude
    if f <= 0 or length <= 0:
        raise ValueError("axial_load and lead must be positive")
    if not 0.0 < back_drive_efficiency <= 1.0:
        raise ValueError(f"back_drive_efficiency must be in (0, 1]; got {back_drive_efficiency}")
    return Quantity(magnitude=f * length * back_drive_efficiency / (2.0 * pi), unit="N*m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
