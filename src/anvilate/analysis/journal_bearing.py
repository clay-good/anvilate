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
    "journal_bearing_unit_load",
    "sommerfeld_number",
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


def journal_bearing_unit_load(
    *,
    radial_load: Quantity,
    journal_diameter: Quantity,
    bearing_length: Quantity,
) -> Quantity:
    """The bearing unit load (projected pressure) P = W/(D·L).

    A journal bearing's load is quoted as a pressure over its *projected* area, the
    diameter times the length — ``radial_load`` W over ``journal_diameter`` D and
    ``bearing_length`` L. This P is the pressure the film must support and the
    denominator of the :func:`sommerfeld_number`. W must be a force and the
    dimensions positive lengths. Returns the unit load in MPa.
    """
    _require(radial_load, "[force]", "radial_load")
    _require(journal_diameter, "[length]", "journal_diameter")
    _require(bearing_length, "[length]", "bearing_length")
    d = journal_diameter.to("mm").magnitude
    ell = bearing_length.to("mm").magnitude
    if d <= 0 or ell <= 0:
        raise ValueError("journal_diameter and bearing_length must be positive")
    pressure = radial_load.pint / (journal_diameter.pint * bearing_length.pint)
    return Quantity(magnitude=float(pressure.to("MPa").magnitude), unit="MPa")


def sommerfeld_number(
    *,
    journal_radius: Quantity,
    radial_clearance: Quantity,
    viscosity: Quantity,
    speed: Quantity,
    unit_load: Quantity,
) -> float:
    """The Sommerfeld (bearing characteristic) number S = (r/c)²·(μ·N/P).

    The dimensionless group that characterises a journal bearing's operating point
    and indexes the Raimondi-Boyd design charts for film thickness, friction, and
    flow. ``journal_radius`` r and ``radial_clearance`` c form the clearance ratio
    r/c (~1000 typically), ``viscosity`` μ is the oil's, ``speed`` N the journal
    speed, and ``unit_load`` P the projected pressure (:func:`journal_bearing_unit_load`).
    A larger S means a more lightly loaded / faster / more viscous bearing — a
    thicker, safer film. All quantities are positive. Returns the dimensionless S.
    """
    _require(journal_radius, "[length]", "journal_radius")
    _require(radial_clearance, "[length]", "radial_clearance")
    _require(viscosity, "[pressure] * [time]", "viscosity")
    _require(unit_load, "[pressure]", "unit_load")
    if not speed.has_dimension("[frequency]"):
        raise ValueError(
            f"speed must be a [frequency] quantity; got {speed.dimensionality} ({speed})"
        )
    r = journal_radius.to("m").magnitude
    c = radial_clearance.to("m").magnitude
    mu = viscosity.to("Pa*s").magnitude
    n = speed.to("rad/s").magnitude / (2.0 * pi)
    p = unit_load.to("Pa").magnitude
    if c <= 0 or r <= 0:
        raise ValueError("journal_radius and radial_clearance must be positive")
    if mu <= 0 or n <= 0 or p <= 0:
        raise ValueError("viscosity, speed, and unit_load must be positive")
    return (r / c) ** 2 * (mu * n / p)
