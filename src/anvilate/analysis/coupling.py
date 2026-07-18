"""T1 analytical rigid flange-coupling torque capacity (closed-form).

A rigid flange coupling joins two shafts by bolting their flanges together on a
bolt circle. The torque passes through the bolts in shear: n bolts, each carrying a
shear force F at the bolt-circle radius R, transmit

    T = n · F · R

so the torque a coupling can carry is set by the bolt shear capacity, and the shear
each bolt must resist for a given torque inverts to F = T/(n·R). Sizing the bolts
is then the ordinary shear check (:func:`~anvilate.analysis.bolt_shear_stress`)
against that force.

These are the rigid-coupling forms (the bolts share the torque equally on a true
rigid flange). Force, torque, and radius inputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import ceil

from ..units import Quantity

__all__ = [
    "flange_coupling_torque",
    "flange_coupling_bolt_force",
    "flange_coupling_bolt_count",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def flange_coupling_torque(
    *,
    bolt_shear_force: Quantity,
    bolt_circle_radius: Quantity,
    num_bolts: int,
) -> Quantity:
    """The torque a rigid flange coupling transmits, T = n·F·R.

    ``bolt_shear_force`` F is the shear each bolt carries, ``bolt_circle_radius`` R
    the radius of the bolt circle, and ``num_bolts`` n the number of bolts sharing
    the torque. F must be a force, R a positive length, and n a positive integer.
    Returns the torque in N·m.
    """
    _require(bolt_shear_force, "[force]", "bolt_shear_force")
    _require(bolt_circle_radius, "[length]", "bolt_circle_radius")
    if num_bolts < 1:
        raise ValueError(f"num_bolts must be a positive integer; got {num_bolts}")
    if bolt_circle_radius.to("mm").magnitude <= 0:
        raise ValueError(f"bolt_circle_radius must be positive; got {bolt_circle_radius}")
    torque = num_bolts * bolt_shear_force.pint * bolt_circle_radius.pint
    return Quantity(magnitude=float(torque.to("N*m").magnitude), unit="N*m")


def flange_coupling_bolt_force(
    *,
    torque: Quantity,
    bolt_circle_radius: Quantity,
    num_bolts: int,
) -> Quantity:
    """The shear force per bolt for a target torque, F = T/(n·R).

    The inverse of :func:`flange_coupling_torque`: the shear each of ``num_bolts`` n
    bolts on a ``bolt_circle_radius`` R must carry to transmit ``torque`` T — the
    load to feed a bolt shear-stress check when sizing the coupling. T must be a
    torque, R a positive length, and n a positive integer. Returns the force in
    newtons.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(bolt_circle_radius, "[length]", "bolt_circle_radius")
    if num_bolts < 1:
        raise ValueError(f"num_bolts must be a positive integer; got {num_bolts}")
    if bolt_circle_radius.to("mm").magnitude <= 0:
        raise ValueError(f"bolt_circle_radius must be positive; got {bolt_circle_radius}")
    force = torque.pint / (num_bolts * bolt_circle_radius.pint)
    return Quantity(magnitude=float(force.to("N").magnitude), unit="N")


def flange_coupling_bolt_count(
    *,
    torque: Quantity,
    bolt_circle_radius: Quantity,
    allowable_bolt_force: Quantity,
) -> int:
    """The fewest bolts n = ceil(T/(F_allow·R)) a flange coupling needs for a torque.

    The bolt-selection inverse of :func:`flange_coupling_torque`: having chosen a bolt size
    (hence an ``allowable_bolt_force`` F_allow from its shear capacity), the number of bolts
    on a ``bolt_circle_radius`` R that share the ``torque`` T is n = ceil(T/(F_allow·R)) --
    rounded up to a whole bolt, and in practice to an even number for a symmetric pattern.
    Fewer, bigger bolts or a larger bolt circle both cut the count. T must be a torque, R a
    positive length, and F_allow a positive force. Returns the minimum bolt count as an int.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(bolt_circle_radius, "[length]", "bolt_circle_radius")
    _require(allowable_bolt_force, "[force]", "allowable_bolt_force")
    r = bolt_circle_radius.to("m").magnitude
    f = allowable_bolt_force.to("N").magnitude
    if r <= 0:
        raise ValueError(f"bolt_circle_radius must be positive; got {bolt_circle_radius}")
    if f <= 0:
        raise ValueError(f"allowable_bolt_force must be positive; got {allowable_bolt_force}")
    t = torque.to("N*m").magnitude
    return ceil(t / (f * r))
