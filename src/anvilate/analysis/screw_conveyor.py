"""T1 analytical screw-conveyor (auger) capacity checks (closed-form).

A screw conveyor moves bulk material by rotating a helical flight inside a trough or tube, each turn
of the screw sweeping one pitch-length of the annulus forward. It is the auger of a grain feeder, a
cement screw, or an extruder's feed section, and it earns its own sizing separate from the belt
conveyor of :mod:`anvilate.analysis.conveyor`: the throughput comes from the swept volume per
revolution, not from a belt speed.

Each revolution advances the material one pitch, so the volumetric capacity is Q = (pi/4)(D^2 - d^2)
* P * N * f, from the screw outside diameter D, the core (shaft) diameter d, the pitch P, the
rotational speed N, and a trough loading (fill) fraction f that is well below one because the flight
cannot run full without flooding. Multiplying by the bulk density gives the mass throughput, and
inverting the capacity gives the screw speed a target feed rate needs.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity
from ..units.rotation import revolutions_per_second

__all__ = [
    "screw_conveyor_mass_capacity",
    "screw_conveyor_speed_for_capacity",
    "screw_conveyor_volumetric_capacity",
]


def screw_conveyor_volumetric_capacity(
    *,
    screw_diameter: Quantity,
    shaft_diameter: Quantity,
    pitch: Quantity,
    rotational_speed: Quantity,
    fill_fraction: float,
) -> Quantity:
    """The volumetric capacity, Q = (pi/4)(D^2 - d^2)*P*N*f.

    The volume a screw conveys per unit time: the flight annulus between the ``screw_diameter`` D
    and the ``shaft_diameter`` d, advanced one ``pitch`` P per turn at the ``rotational_speed`` N,
    filled to the ``fill_fraction`` f of the trough. A standard-pitch screw has P = D; the fill
    fraction runs about 0.15 for sluggish or abrasive material up to about 0.45 for free-flowing,
    because a fuller flight floods and stalls. Returns the volumetric capacity in m**3/h.
    """
    _check(screw_diameter, "[length]", "screw_diameter")
    _check(shaft_diameter, "[length]", "shaft_diameter")
    _check(pitch, "[length]", "pitch")
    _check(rotational_speed, "1/[time]", "rotational_speed")
    big = screw_diameter.to("m").magnitude
    small = shaft_diameter.to("m").magnitude
    p = pitch.to("m").magnitude
    n = revolutions_per_second(rotational_speed, name="rotational_speed")
    if big <= 0:
        raise ValueError("screw_diameter must be positive")
    if small < 0:
        raise ValueError("shaft_diameter must be non-negative")
    if small >= big:
        raise ValueError("shaft_diameter must be less than screw_diameter")
    if p <= 0:
        raise ValueError("pitch must be positive")
    if n <= 0:
        raise ValueError("rotational_speed must be positive")
    if not 0.0 < fill_fraction <= 1.0:
        raise ValueError("fill_fraction must be in (0, 1]")
    q = pi / 4.0 * (big * big - small * small) * p * n * fill_fraction
    return Quantity(magnitude=q, unit="m**3/s").to("m**3/h")


def screw_conveyor_mass_capacity(
    *, volumetric_capacity: Quantity, bulk_density: Quantity
) -> Quantity:
    """The mass capacity, m_dot = Q*rho.

    The mass throughput of a screw conveyor: its ``volumetric_capacity`` Q (from
    :func:`screw_conveyor_volumetric_capacity`) times the material ``bulk_density`` rho. It is the
    tonnage-per-hour a feeder is rated on, and it scales directly with both the swept volume and how
    heavy the material is. Returns the mass capacity in t/h.
    """
    _check(volumetric_capacity, "[volume]/[time]", "volumetric_capacity")
    _check(bulk_density, "[mass]/[length]**3", "bulk_density")
    q = volumetric_capacity.to("m**3/s").magnitude
    rho = bulk_density.to("kg/m**3").magnitude
    if q <= 0:
        raise ValueError("volumetric_capacity must be positive")
    if rho <= 0:
        raise ValueError("bulk_density must be positive")
    return Quantity(magnitude=q * rho, unit="kg/s").to("t/hr")


def screw_conveyor_speed_for_capacity(
    *,
    volumetric_capacity: Quantity,
    screw_diameter: Quantity,
    shaft_diameter: Quantity,
    pitch: Quantity,
    fill_fraction: float,
) -> Quantity:
    """The screw speed for a target capacity, N = Q / [(pi/4)(D^2 - d^2)*P*f].

    Inverting the capacity relation (:func:`screw_conveyor_volumetric_capacity`) for speed: the
    rotational speed a screw of ``screw_diameter`` D, ``shaft_diameter`` d, and ``pitch`` P must
    turn to deliver a target ``volumetric_capacity`` Q at a ``fill_fraction`` f. It sets the drive
    speed and, with the material, guards against over-speeding (which throws the load) or flooding.
    Returns the rotational speed in rpm.
    """
    _check(volumetric_capacity, "[volume]/[time]", "volumetric_capacity")
    _check(screw_diameter, "[length]", "screw_diameter")
    _check(shaft_diameter, "[length]", "shaft_diameter")
    _check(pitch, "[length]", "pitch")
    q = volumetric_capacity.to("m**3/s").magnitude
    big = screw_diameter.to("m").magnitude
    small = shaft_diameter.to("m").magnitude
    p = pitch.to("m").magnitude
    if q <= 0:
        raise ValueError("volumetric_capacity must be positive")
    if big <= 0:
        raise ValueError("screw_diameter must be positive")
    if small < 0:
        raise ValueError("shaft_diameter must be non-negative")
    if small >= big:
        raise ValueError("shaft_diameter must be less than screw_diameter")
    if p <= 0:
        raise ValueError("pitch must be positive")
    if not 0.0 < fill_fraction <= 1.0:
        raise ValueError("fill_fraction must be in (0, 1]")
    # n is revolutions per second; report as rpm (60 rpm per rev/s), not via a 1/s -> rpm
    # conversion which would divide by the 2*pi rad-per-revolution factor.
    n = q / (pi / 4.0 * (big * big - small * small) * p * fill_fraction)
    return Quantity(magnitude=n * 60.0, unit="rpm")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
