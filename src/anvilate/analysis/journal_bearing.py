"""T1 analytical journal (plain sleeve) bearing friction — Petroff (closed-form).

A lightly-loaded, well-lubricated journal bearing runs on a full oil film with the
shaft nearly concentric in the bush. Petroff's model shears that film as a simple
Couette flow and gives the friction the bearing spends. For a journal of radius r
running at speed N in a bush of axial length L, with radial clearance c and oil of
dynamic viscosity μ, the friction torque is

    T_f = 4·π²·μ·N·L·r³ / c

and the power lost to friction is T_f·ω with ω = 2π·N. The friction coefficient
follows from the bearing load as f = T_f/(W·r).

Petroff is the concentric, no-load-eccentricity limit — an optimistic estimate of
the running friction, good for a first screen of viscous drag and heat generation
(a loaded bearing sits eccentric and needs the Sommerfeld/Raimondi-Boyd solution
for the film thickness and the true friction). Viscosity, speed, and geometry are
dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

__all__ = [
    "petroff_friction_torque",
    "petroff_friction_power",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _petroff_torque_nm(
    viscosity: Quantity,
    speed: Quantity,
    journal_radius: Quantity,
    bearing_length: Quantity,
    radial_clearance: Quantity,
) -> float:
    """The Petroff friction torque in N·m — the shared core (validates inputs)."""
    _require(viscosity, "[pressure] * [time]", "viscosity")
    _require(journal_radius, "[length]", "journal_radius")
    _require(bearing_length, "[length]", "bearing_length")
    _require(radial_clearance, "[length]", "radial_clearance")
    if not speed.has_dimension("[frequency]"):
        raise ValueError(
            f"speed must be a [frequency] quantity; got {speed.dimensionality} ({speed})"
        )
    mu = viscosity.to("Pa*s").magnitude
    n = speed.to("rad/s").magnitude / (2.0 * pi)  # revolutions per second
    r = journal_radius.to("m").magnitude
    ell = bearing_length.to("m").magnitude
    c = radial_clearance.to("m").magnitude
    if mu <= 0:
        raise ValueError(f"viscosity must be positive; got {viscosity}")
    if n <= 0:
        raise ValueError(f"speed must be positive; got {speed}")
    for value, name in ((r, "journal_radius"), (ell, "bearing_length"), (c, "radial_clearance")):
        if value <= 0:
            raise ValueError(f"{name} must be positive; got {value} m")
    return 4.0 * pi**2 * mu * n * ell * r**3 / c


def petroff_friction_torque(
    *,
    viscosity: Quantity,
    speed: Quantity,
    journal_radius: Quantity,
    bearing_length: Quantity,
    radial_clearance: Quantity,
) -> Quantity:
    """The Petroff friction torque T_f = 4·π²·μ·N·L·r³/c of a journal bearing.

    ``viscosity`` μ is the oil's dynamic viscosity, ``speed`` N the journal speed
    (rpm or rad/s), ``journal_radius`` r, ``bearing_length`` L the bearing's axial
    length, and ``radial_clearance`` c the radial gap between journal and bush. The
    torque grows with viscosity, speed, and radius and falls with clearance — the
    concentric (unloaded) drag the shaft must overcome. All quantities are
    dimension-checked and positive. Returns the torque in N·m.
    """
    torque = _petroff_torque_nm(viscosity, speed, journal_radius, bearing_length, radial_clearance)
    return Quantity(magnitude=torque, unit="N*m")


def petroff_friction_power(
    *,
    viscosity: Quantity,
    speed: Quantity,
    journal_radius: Quantity,
    bearing_length: Quantity,
    radial_clearance: Quantity,
) -> Quantity:
    """The power lost to friction in a journal bearing, P = T_f·ω.

    The heat a Petroff journal bearing generates: the friction torque
    (:func:`petroff_friction_torque`) times the angular speed ω = 2π·N. This is the
    load a lubrication/cooling system must carry away and the drag that saps
    efficiency at speed. Arguments as in :func:`petroff_friction_torque`. Returns the
    power in watts.
    """
    torque = _petroff_torque_nm(viscosity, speed, journal_radius, bearing_length, radial_clearance)
    omega = speed.to("rad/s").magnitude
    return Quantity(magnitude=torque * omega, unit="W")
