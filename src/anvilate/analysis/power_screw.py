"""T1 analytical power-screw (lead-screw) mechanics for square threads (closed-form).

A power screw turns torque into axial thrust — a jack, a press, a vice, a linear
actuator. For a square thread of mean diameter d_m and lead l (the axial travel
per turn), carrying an axial load F against a thread friction coefficient μ, the
torque to *raise* the load (drive it against the load) is

    T_raise = (F·d_m/2)·(l + π·μ·d_m)/(π·d_m − μ·l)

and the torque to *lower* it is the same with the friction and lead terms
reversed, T_lower = (F·d_m/2)·(π·μ·d_m − l)/(π·d_m + μ·l). A positive lowering
torque means the screw is *self-locking* — it holds the load without a brake,
which happens exactly when μ ≥ tan λ for the lead angle tan λ = l/(π·d_m). The
efficiency of raising is e = tan λ·(1 − μ·tan λ)/(tan λ + μ); self-locking screws
run below 50%, the price of not backdriving.

These are the square-thread Shigley forms and exclude collar/thrust-bearing
friction (add that torque separately). Trapezoidal/ACME threads carry an extra
sec(α) on the friction terms for the thread half-angle α. Loads and lengths are
dimension-checked :class:`~anvilate.units.Quantity` values; μ is a dimensionless
coefficient the user supplies.
"""

from __future__ import annotations

from math import atan, degrees, pi

from ..units import Quantity

__all__ = [
    "lead_angle",
    "power_screw_raise_torque",
    "power_screw_raise_load",
    "power_screw_lower_torque",
    "power_screw_efficiency",
    "power_screw_is_self_locking",
    "power_screw_collar_torque",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _geometry(
    mean_diameter: Quantity, lead: Quantity, friction_coefficient: float
) -> tuple[float, float, float]:
    """Validate and return (d_m, l, μ) in mm, mm, — the shared inputs."""
    _require(mean_diameter, "[length]", "mean_diameter")
    _require(lead, "[length]", "lead")
    dm = mean_diameter.to("mm").magnitude
    ell = lead.to("mm").magnitude
    if dm <= 0:
        raise ValueError(f"mean_diameter must be positive; got {mean_diameter}")
    if ell <= 0:
        raise ValueError(f"lead must be positive; got {lead}")
    if friction_coefficient < 0:
        raise ValueError(f"friction_coefficient must be non-negative; got {friction_coefficient}")
    return dm, ell, friction_coefficient


def lead_angle(*, mean_diameter: Quantity, lead: Quantity) -> Quantity:
    """The lead (helix) angle λ of a screw thread, tan λ = l/(π·d_m).

    ``mean_diameter`` d_m is the thread's pitch/mean diameter and ``lead`` l the
    axial advance per revolution (the pitch times the number of thread starts). A
    steeper lead angle raises efficiency but costs self-locking. Both must be
    positive lengths. Returns the angle in degrees.
    """
    dm, ell, _ = _geometry(mean_diameter, lead, 0.0)
    return Quantity(magnitude=degrees(atan(ell / (pi * dm))), unit="degree")


def power_screw_raise_torque(
    *,
    load: Quantity,
    mean_diameter: Quantity,
    lead: Quantity,
    friction_coefficient: float,
) -> Quantity:
    """The torque T_raise to drive a square-thread screw *against* an axial load.

    T_raise = (F·d_m/2)·(l + π·μ·d_m)/(π·d_m − μ·l) — the torque a jack or press
    needs to lift ``load`` F. ``mean_diameter`` d_m, ``lead`` l, and
    ``friction_coefficient`` μ describe the thread; collar friction is not
    included. The load must be a force. Returns the torque in N·m.
    """
    _require(load, "[force]", "load")
    dm, ell, mu = _geometry(mean_diameter, lead, friction_coefficient)
    f = load.to("N").magnitude
    dm_m = dm / 1000.0
    ell_m = ell / 1000.0
    torque = (f * dm_m / 2.0) * (ell_m + pi * mu * dm_m) / (pi * dm_m - mu * ell_m)
    return Quantity(magnitude=torque, unit="N*m")


def power_screw_raise_load(
    *,
    torque: Quantity,
    mean_diameter: Quantity,
    lead: Quantity,
    friction_coefficient: float,
) -> Quantity:
    """The axial load a given input ``torque`` can raise on a square-thread screw.

    The inverse of :func:`power_screw_raise_torque`: inverting
    T = (F·d_m/2)·(l + π·μ·d_m)/(π·d_m − μ·l) for the load gives
    F = 2·T·(π·d_m − μ·l)/(d_m·(l + π·μ·d_m)) — the lifting capacity of a screw jack or
    press for the ``torque`` a handle, wrench, or motor applies. ``mean_diameter`` d_m,
    ``lead`` l, and ``friction_coefficient`` μ describe the thread; collar friction is
    not included. The torque must be a torque. Returns the load in N.
    """
    _require(torque, "[force] * [length]", "torque")
    dm, ell, mu = _geometry(mean_diameter, lead, friction_coefficient)
    t = torque.to("N*m").magnitude
    dm_m = dm / 1000.0
    ell_m = ell / 1000.0
    load = 2.0 * t * (pi * dm_m - mu * ell_m) / (dm_m * (ell_m + pi * mu * dm_m))
    return Quantity(magnitude=load, unit="N")


def power_screw_lower_torque(
    *,
    load: Quantity,
    mean_diameter: Quantity,
    lead: Quantity,
    friction_coefficient: float,
) -> Quantity:
    """The torque T_lower to lower an axial load on a square-thread screw.

    T_lower = (F·d_m/2)·(π·μ·d_m − l)/(π·d_m + μ·l). A **positive** result is the
    holding/lowering torque of a self-locking screw; a **negative** result means
    the screw backdrives — the load overhauls it and drives it down on its own, so
    a brake is required. Arguments as in :func:`power_screw_raise_torque`. Returns
    the signed torque in N·m.
    """
    _require(load, "[force]", "load")
    dm, ell, mu = _geometry(mean_diameter, lead, friction_coefficient)
    f = load.to("N").magnitude
    dm_m = dm / 1000.0
    ell_m = ell / 1000.0
    torque = (f * dm_m / 2.0) * (pi * mu * dm_m - ell_m) / (pi * dm_m + mu * ell_m)
    return Quantity(magnitude=torque, unit="N*m")


def power_screw_efficiency(
    *,
    mean_diameter: Quantity,
    lead: Quantity,
    friction_coefficient: float,
) -> float:
    """The raising efficiency e = tan λ·(1 − μ·tan λ)/(tan λ + μ) of a square-thread
    screw.

    The fraction of input work delivered as axial thrust (the rest is lost to
    thread friction), a function only of the lead angle and μ, not the load. A
    self-locking screw (μ ≥ tan λ) always runs below 50%. Returns the dimensionless
    efficiency in (0, 1); a frictionless screw (μ = 0) returns 1.
    """
    dm, ell, mu = _geometry(mean_diameter, lead, friction_coefficient)
    tan_lambda = ell / (pi * dm)
    if mu == 0:
        return 1.0
    return tan_lambda * (1.0 - mu * tan_lambda) / (tan_lambda + mu)


def power_screw_is_self_locking(
    *,
    mean_diameter: Quantity,
    lead: Quantity,
    friction_coefficient: float,
) -> bool:
    """Whether a square-thread screw holds its load without a brake, μ ≥ tan λ.

    A self-locking screw does not backdrive under the axial load — the friction
    torque exceeds the load-induced unwinding torque. This is the boundary the
    lowering torque crosses zero at. Returns ``True`` when ``friction_coefficient``
    μ is at least the tangent of the lead angle.
    """
    dm, ell, mu = _geometry(mean_diameter, lead, friction_coefficient)
    return mu >= ell / (pi * dm)


def power_screw_collar_torque(
    *,
    load: Quantity,
    collar_mean_radius: Quantity,
    collar_friction_coefficient: float,
) -> Quantity:
    """The collar (thrust-bearing) friction torque T_c = μ_c·F·r_c of a power screw.

    The thread torque (:func:`power_screw_raise_torque`) turns the screw, but the
    axial ``load`` F also presses on a thrust collar or bearing that rubs as the screw
    turns, adding a separate friction torque T_c = μ_c·F·r_c. ``collar_mean_radius``
    r_c is the mean radius of the collar's rubbing face and ``collar_friction_coefficient``
    μ_c its friction coefficient (often lower than the thread's if the collar is a
    rolling thrust bearing). Add T_c to the thread torque for the total driving torque;
    unlike the thread friction it does *no* useful lifting, so it drops the overall
    efficiency. The load must be a force, r_c a positive length, and μ_c non-negative.
    Returns the collar torque in N·m.
    """
    _require(load, "[force]", "load")
    _require(collar_mean_radius, "[length]", "collar_mean_radius")
    if collar_friction_coefficient < 0:
        raise ValueError(
            f"collar_friction_coefficient must be non-negative; got {collar_friction_coefficient}"
        )
    f = load.to("N").magnitude
    r_c = collar_mean_radius.to("m").magnitude
    if r_c <= 0:
        raise ValueError(f"collar_mean_radius must be positive; got {collar_mean_radius}")
    return Quantity(magnitude=collar_friction_coefficient * f * r_c, unit="N*m")
