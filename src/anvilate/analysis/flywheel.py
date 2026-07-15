"""T1 analytical flywheel energy-smoothing sizing (closed-form).

A flywheel evens out a machine that delivers or draws power in bursts — a punch
press, a piston engine, a shear. It absorbs energy when the drive runs ahead and
gives it back when the load spikes, letting the shaft speed wander only within a
tolerated band. The speed ripple is measured by the coefficient of fluctuation

    C_s = (ω_max − ω_min)/ω_mean

and the energy a flywheel of mass moment of inertia I trades over one cycle is

    ΔE = I·ω_mean²·C_s

so sizing a flywheel to hold a required smoothness inverts to I = ΔE/(ω_mean²·C_s).
Because the inertia buys smoothness through ω² — the speed squared — a flywheel on
a fast shaft is far smaller than one doing the same job slowly.

These are the Shigley / Norton rigid-flywheel forms (energy-storage sizing, not a
stress or burst-speed check — a real rim also needs a hoop-stress screen at speed).
Inertia, speed, and energy inputs are dimension-checked
:class:`~anvilate.units.Quantity` values; the mass moment of inertia can come from
:func:`~anvilate.analysis.solid_disc_polar_mass_moment`.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "coefficient_of_fluctuation",
    "flywheel_energy_fluctuation",
    "flywheel_inertia_for_fluctuation",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def coefficient_of_fluctuation(*, max_speed: Quantity, min_speed: Quantity) -> float:
    """The coefficient of fluctuation C_s = (ω_max − ω_min)/ω_mean of a shaft's
    speed ripple.

    ``max_speed`` and ``min_speed`` are the peak and trough angular speeds over a
    cycle (rpm or rad/s); the mean is their average. A smaller C_s is a steadier
    shaft — presses tolerate ~0.2, generators need ~0.01. ``max_speed`` must exceed
    ``min_speed`` and both be positive rotational frequencies. Returns the
    dimensionless C_s.
    """
    _require(max_speed, "[frequency]", "max_speed")
    _require(min_speed, "[frequency]", "min_speed")
    wmax = max_speed.to("rad/s").magnitude
    wmin = min_speed.to("rad/s").magnitude
    if wmin <= 0:
        raise ValueError(f"min_speed must be positive; got {min_speed}")
    if wmax <= wmin:
        raise ValueError(
            f"max_speed ({max_speed}) must exceed min_speed ({min_speed}) for a speed ripple"
        )
    return (wmax - wmin) / ((wmax + wmin) / 2.0)


def flywheel_energy_fluctuation(
    *,
    inertia: Quantity,
    mean_speed: Quantity,
    coefficient_of_fluctuation: float,
) -> Quantity:
    """The energy a flywheel trades over a cycle, ΔE = I·ω_mean²·C_s.

    ``inertia`` I is the flywheel's mass moment of inertia, ``mean_speed`` ω_mean
    the mean shaft speed (rpm or rad/s), and ``coefficient_of_fluctuation`` C_s the
    tolerated speed ripple. This is the energy the flywheel can absorb and return
    while the speed stays within the C_s band. ``inertia`` must be a mass·length²
    and ``mean_speed`` a positive rotational frequency; C_s must be positive.
    Returns the energy in joules.
    """
    _require(inertia, "[mass] * [length]**2", "inertia")
    _require(mean_speed, "[frequency]", "mean_speed")
    if coefficient_of_fluctuation <= 0:
        raise ValueError(
            f"coefficient_of_fluctuation must be positive; got {coefficient_of_fluctuation}"
        )
    i = inertia.to("kg*m**2").magnitude
    omega = mean_speed.to("rad/s").magnitude
    if omega <= 0:
        raise ValueError(f"mean_speed must be positive; got {mean_speed}")
    return Quantity(magnitude=i * omega**2 * coefficient_of_fluctuation, unit="J")


def flywheel_inertia_for_fluctuation(
    *,
    energy_fluctuation: Quantity,
    mean_speed: Quantity,
    coefficient_of_fluctuation: float,
) -> Quantity:
    """The mass moment of inertia a flywheel needs, I = ΔE/(ω_mean²·C_s).

    The inverse of :func:`flywheel_energy_fluctuation`: the inertia to absorb an
    energy swing ``energy_fluctuation`` ΔE while holding the shaft speed within the
    ``coefficient_of_fluctuation`` C_s band about ``mean_speed`` ω_mean — the
    flywheel-sizing step. Note the ω² lever: doubling the mean speed quarters the
    inertia (and mass) for the same job. ``energy_fluctuation`` must be an energy
    and ``mean_speed`` a positive rotational frequency; C_s must be positive.
    Returns the inertia in kg·m².
    """
    _require(energy_fluctuation, "[energy]", "energy_fluctuation")
    _require(mean_speed, "[frequency]", "mean_speed")
    if coefficient_of_fluctuation <= 0:
        raise ValueError(
            f"coefficient_of_fluctuation must be positive; got {coefficient_of_fluctuation}"
        )
    de = energy_fluctuation.to("J").magnitude
    omega = mean_speed.to("rad/s").magnitude
    if omega <= 0:
        raise ValueError(f"mean_speed must be positive; got {mean_speed}")
    inertia = de / (omega**2 * coefficient_of_fluctuation)
    return Quantity(magnitude=inertia, unit="kg*m**2")
