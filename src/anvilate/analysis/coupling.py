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

from ..units import Quantity

__all__ = [
    "flange_coupling_torque",
    "flange_coupling_bolt_force",
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
