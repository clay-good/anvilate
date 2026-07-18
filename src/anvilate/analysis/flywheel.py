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

These are the Shigley / Norton rigid-flywheel forms for energy-storage sizing,
paired with the thin-rim hoop-stress screen a real rim needs at speed: a rotating
ring's centrifugal loading raises a tangential (hoop) stress σ = ρ·v² that depends
only on the rim material density and its rim speed v = ω·r — not on the rim
thickness — so past a burst speed the rim tears itself apart regardless of how
stout it is. Inertia, speed, energy, density, and radius inputs are dimension-checked
:class:`~anvilate.units.Quantity` values; the mass moment of inertia can come from
:func:`~anvilate.analysis.solid_disc_polar_mass_moment`.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "coefficient_of_fluctuation",
    "flywheel_energy_fluctuation",
    "flywheel_inertia_for_fluctuation",
    "rotating_rim_hoop_stress",
    "rotating_rim_burst_speed",
    "rotating_rim_radial_growth",
    "rotating_solid_disc_max_stress",
    "rotating_solid_disc_radial_stress",
    "rotating_solid_disc_tangential_stress",
    "rotating_annular_disc_bore_stress",
    "rotating_annular_disc_radial_stress",
    "rotating_annular_disc_tangential_stress",
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


def rotating_rim_hoop_stress(
    *, density: Quantity, mean_radius: Quantity, rotational_speed: Quantity
) -> Quantity:
    """The hoop (bursting) stress of a thin rotating rim, σ = ρ·v².

    A thin rim spinning at rim speed v = ω·r carries a tangential tensile stress
    σ = ρ·v² = ρ·(ω·r)² from its own centrifugal loading — the stress that bursts a
    flywheel rim or a grinding wheel. Strikingly it depends only on the material
    ``density`` ρ and the rim speed, *not* on the rim thickness, so a heavier rim
    buys no margin: what matters is how fast the rim surface travels.
    ``mean_radius`` r is the rim's mean radius and ``rotational_speed`` ω a positive
    rotational frequency (rpm or rad/s). Screen the result against the rim
    material's allowable tensile stress. Returns the hoop stress in MPa.
    """
    _require(density, "[mass] / [length]**3", "density")
    _require(mean_radius, "[length]", "mean_radius")
    _require(rotational_speed, "[frequency]", "rotational_speed")
    rho = density.to("kg/m**3").magnitude
    r = mean_radius.to("m").magnitude
    omega = rotational_speed.to("rad/s").magnitude
    if r <= 0:
        raise ValueError(f"mean_radius must be positive; got {mean_radius}")
    if omega <= 0:
        raise ValueError(f"rotational_speed must be positive; got {rotational_speed}")
    v = omega * r
    return Quantity(magnitude=rho * v**2 / 1e6, unit="MPa")


def rotating_rim_burst_speed(
    *, allowable_stress: Quantity, density: Quantity, mean_radius: Quantity
) -> Quantity:
    """The speed at which a thin rotating rim reaches its allowable stress.

    The inverse of :func:`rotating_rim_hoop_stress`: setting σ = ρ·(ω·r)² equal to
    the rim material's ``allowable_stress`` gives the limiting speed
    ω = √(σ_allow/ρ)/r — the burst (or design-limit) speed of a flywheel rim or
    grinding wheel. ``allowable_stress`` σ_allow is the rim material's allowable
    tensile stress, ``density`` ρ its density, and ``mean_radius`` r the rim's mean
    radius (positive). Because the limit rides on rim speed, a larger rim reaches it
    at a lower rotational speed. Returns the limiting speed in rpm.
    """
    _require(allowable_stress, "[pressure]", "allowable_stress")
    _require(density, "[mass] / [length]**3", "density")
    _require(mean_radius, "[length]", "mean_radius")
    sigma = allowable_stress.to("Pa").magnitude
    rho = density.to("kg/m**3").magnitude
    r = mean_radius.to("m").magnitude
    if r <= 0:
        raise ValueError(f"mean_radius must be positive; got {mean_radius}")
    if sigma <= 0:
        raise ValueError(f"allowable_stress must be positive; got {allowable_stress}")
    omega = sqrt(sigma / rho) / r  # rad/s
    return Quantity(magnitude=omega, unit="rad/s").to("rpm")


def rotating_rim_radial_growth(
    *,
    density: Quantity,
    mean_radius: Quantity,
    rotational_speed: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The radial growth δ = ρ·ω²·r³/E of a thin spinning rim.

    The same centrifugal hoop stress that can burst a rim also *stretches* it: the
    rim's radius grows by δ = σ_hoop·r/E = ρ·ω²·r³/E as it spins up. This is why a
    shrink-fit ring, gear, or rotor loosens at speed — the rim grows away from its
    shaft and the interference bleeds off, so a fit that grips at rest can slip at
    running speed. ``density`` ρ, ``mean_radius`` r, ``rotational_speed`` ω, and the
    rim material's ``elastic_modulus`` E describe the rim; r and ω must be positive.
    Compare the growth against the shrink-fit interference to check the fit holds at
    speed. Returns the radial growth in millimetres.
    """
    _require(density, "[mass] / [length]**3", "density")
    _require(mean_radius, "[length]", "mean_radius")
    _require(rotational_speed, "[frequency]", "rotational_speed")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    rho = density.to("kg/m**3").magnitude
    r = mean_radius.to("m").magnitude
    omega = rotational_speed.to("rad/s").magnitude
    e = elastic_modulus.to("Pa").magnitude
    if r <= 0:
        raise ValueError(f"mean_radius must be positive; got {mean_radius}")
    if omega <= 0:
        raise ValueError(f"rotational_speed must be positive; got {rotational_speed}")
    if e <= 0:
        raise ValueError(f"elastic_modulus must be positive; got {elastic_modulus}")
    growth = rho * omega**2 * r**3 / e  # metres
    return Quantity(magnitude=growth * 1000.0, unit="mm")


def rotating_solid_disc_max_stress(
    *,
    density: Quantity,
    outer_radius: Quantity,
    rotational_speed: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The peak stress σ = (3 + ν)/8·ρ·(ω·R)² at the centre of a solid spinning disc.

    A *solid* disc (a turbine wheel, a flywheel machined from plate) does not carry
    the thin-rim's uniform ρ·v²: its stress is highest at the centre, where the
    radial and tangential stresses are equal at σ = (3 + ν)/8·ρ·ω²·R². This is the
    stress that bursts a solid rotor from the middle out, distinct from the
    :func:`rotating_rim_hoop_stress` of a thin ring. ``density`` ρ, ``outer_radius``
    R, ``rotational_speed`` ω (positive), and Poisson's ratio ``poisson`` ν
    (0 ≤ ν < 0.5) describe the disc. Screen it against the material's allowable.
    Returns the peak centre stress in MPa.
    """
    _require(density, "[mass] / [length]**3", "density")
    _require(outer_radius, "[length]", "outer_radius")
    _require(rotational_speed, "[frequency]", "rotational_speed")
    if not 0 <= poisson < 0.5:
        raise ValueError(f"poisson must lie in [0, 0.5); got {poisson}")
    rho = density.to("kg/m**3").magnitude
    r = outer_radius.to("m").magnitude
    omega = rotational_speed.to("rad/s").magnitude
    if r <= 0:
        raise ValueError(f"outer_radius must be positive; got {outer_radius}")
    if omega <= 0:
        raise ValueError(f"rotational_speed must be positive; got {rotational_speed}")
    sigma = (3.0 + poisson) / 8.0 * rho * (omega * r) ** 2
    return Quantity(magnitude=sigma / 1e6, unit="MPa")


def _rotating_disc_inputs(
    density: Quantity,
    outer_radius: Quantity,
    radius: Quantity,
    rotational_speed: Quantity,
    poisson: float,
) -> tuple[float, float, float, float]:
    """Validate a rotating solid disc and return (rho, R, r, omega) in SI."""
    _require(density, "[mass] / [length]**3", "density")
    _require(outer_radius, "[length]", "outer_radius")
    _require(radius, "[length]", "radius")
    _require(rotational_speed, "[frequency]", "rotational_speed")
    if not 0 <= poisson < 0.5:
        raise ValueError(f"poisson must lie in [0, 0.5); got {poisson}")
    rho = density.to("kg/m**3").magnitude
    big_r = outer_radius.to("m").magnitude
    r = radius.to("m").magnitude
    omega = rotational_speed.to("rad/s").magnitude
    if big_r <= 0:
        raise ValueError(f"outer_radius must be positive; got {outer_radius}")
    if omega <= 0:
        raise ValueError(f"rotational_speed must be positive; got {rotational_speed}")
    if not 0 <= r <= big_r:
        raise ValueError(
            f"radius ({radius}) must be between 0 and the outer_radius ({outer_radius})"
        )
    return rho, big_r, r, omega


def rotating_solid_disc_radial_stress(
    *,
    density: Quantity,
    outer_radius: Quantity,
    radius: Quantity,
    rotational_speed: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The radial stress σ_r = (3 + ν)/8·ρ·ω²·(R² − r²) at a radius in a spinning disc.

    The radial stress in a solid rotating disc peaks at the centre (r = 0), where it
    equals the tangential stress and the :func:`rotating_solid_disc_max_stress`, and
    falls to *zero* at the free rim (r = R). ``density`` ρ, ``outer_radius`` R,
    ``radius`` r (between 0 and R), ``rotational_speed`` ω, and Poisson's ratio
    ``poisson`` ν describe the disc and the point of interest. Returns the radial
    stress in MPa.
    """
    rho, big_r, r, omega = _rotating_disc_inputs(
        density, outer_radius, radius, rotational_speed, poisson
    )
    sigma = (3.0 + poisson) / 8.0 * rho * omega**2 * (big_r**2 - r**2)
    return Quantity(magnitude=sigma / 1e6, unit="MPa")


def rotating_solid_disc_tangential_stress(
    *,
    density: Quantity,
    outer_radius: Quantity,
    radius: Quantity,
    rotational_speed: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The tangential (hoop) stress σ_θ = (ρ·ω²/8)·[(3 + ν)·R² − (1 + 3ν)·r²] at a
    radius in a spinning disc.

    The hoop stress in a solid rotating disc is also highest at the centre (r = 0),
    where it equals the radial stress and the :func:`rotating_solid_disc_max_stress`;
    unlike the radial stress it does *not* vanish at the rim but settles to the
    non-zero σ_θ = ρ·ω²·R²·(1 − ν)/4 there — the hoop tension that a rim feature or
    keyway must survive. ``density`` ρ, ``outer_radius`` R, ``radius`` r (0 to R),
    ``rotational_speed`` ω, and Poisson's ratio ``poisson`` ν are as in
    :func:`rotating_solid_disc_radial_stress`. Returns the tangential stress in MPa.
    """
    rho, big_r, r, omega = _rotating_disc_inputs(
        density, outer_radius, radius, rotational_speed, poisson
    )
    sigma = rho * omega**2 / 8.0 * ((3.0 + poisson) * big_r**2 - (1.0 + 3.0 * poisson) * r**2)
    return Quantity(magnitude=sigma / 1e6, unit="MPa")


def rotating_annular_disc_bore_stress(
    *,
    density: Quantity,
    outer_radius: Quantity,
    inner_radius: Quantity,
    rotational_speed: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The bore tangential stress of a rotating annular disc,
    σ = (ρ·ω²/4)·[(3 + ν)·R_o² + (1 − ν)·R_i²].

    Bore a hole in a spinning disc and the peak stress moves to the bore and *jumps*:
    the tangential stress there is σ = (ρ·ω²/4)·[(3 + ν)·R_o² + (1 − ν)·R_i²]. As the
    hole shrinks to nothing (R_i → 0) this tends to (3 + ν)/4·ρ·ω²·R_o² — exactly
    *twice* the solid disc's centre stress (:func:`rotating_solid_disc_max_stress`),
    so even a pinhole at the axis doubles the peak stress. That is why turbine and
    flywheel discs with a central bore burst at half the speed a solid one would.
    ``density`` ρ, ``outer_radius`` R_o, ``inner_radius`` R_i (0 < R_i < R_o),
    ``rotational_speed`` ω, and Poisson's ratio ``poisson`` ν describe the disc.
    Returns the bore tangential stress in MPa.
    """
    _require(density, "[mass] / [length]**3", "density")
    _require(outer_radius, "[length]", "outer_radius")
    _require(inner_radius, "[length]", "inner_radius")
    _require(rotational_speed, "[frequency]", "rotational_speed")
    if not 0 <= poisson < 0.5:
        raise ValueError(f"poisson must lie in [0, 0.5); got {poisson}")
    rho = density.to("kg/m**3").magnitude
    ro = outer_radius.to("m").magnitude
    ri = inner_radius.to("m").magnitude
    omega = rotational_speed.to("rad/s").magnitude
    if ri <= 0:
        raise ValueError(f"inner_radius must be positive; got {inner_radius}")
    if ro <= ri:
        raise ValueError(f"outer_radius ({outer_radius}) must exceed inner_radius ({inner_radius})")
    if omega <= 0:
        raise ValueError(f"rotational_speed must be positive; got {rotational_speed}")
    sigma = rho * omega**2 / 4.0 * ((3.0 + poisson) * ro**2 + (1.0 - poisson) * ri**2)
    return Quantity(magnitude=sigma / 1e6, unit="MPa")


def _annular_disc_inputs(
    density: Quantity,
    outer_radius: Quantity,
    inner_radius: Quantity,
    radius: Quantity,
    rotational_speed: Quantity,
    poisson: float,
) -> tuple[float, float, float, float, float]:
    """Validate a rotating annular disc and return (rho, ro, ri, r, omega) in SI."""
    _require(density, "[mass] / [length]**3", "density")
    _require(outer_radius, "[length]", "outer_radius")
    _require(inner_radius, "[length]", "inner_radius")
    _require(radius, "[length]", "radius")
    _require(rotational_speed, "[frequency]", "rotational_speed")
    if not 0 <= poisson < 0.5:
        raise ValueError(f"poisson must lie in [0, 0.5); got {poisson}")
    rho = density.to("kg/m**3").magnitude
    ro = outer_radius.to("m").magnitude
    ri = inner_radius.to("m").magnitude
    r = radius.to("m").magnitude
    omega = rotational_speed.to("rad/s").magnitude
    if ri <= 0:
        raise ValueError(f"inner_radius must be positive; got {inner_radius}")
    if ro <= ri:
        raise ValueError(f"outer_radius ({outer_radius}) must exceed inner_radius ({inner_radius})")
    if omega <= 0:
        raise ValueError(f"rotational_speed must be positive; got {rotational_speed}")
    if not ri <= r <= ro:
        raise ValueError(
            f"radius ({radius}) must lie between the inner and outer radii "
            f"({inner_radius}, {outer_radius})"
        )
    return rho, ro, ri, r, omega


def rotating_annular_disc_radial_stress(
    *,
    density: Quantity,
    outer_radius: Quantity,
    inner_radius: Quantity,
    radius: Quantity,
    rotational_speed: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The radial stress at a radius in a rotating annular disc,
    σ_r = (3 + ν)/8·ρ·ω²·(R_o² + R_i² − R_i²·R_o²/r² − r²).

    The radial stress vanishes at both free edges (the bore R_i and the rim R_o) and
    peaks in between at r = √(R_i·R_o). ``density`` ρ, ``outer_radius`` R_o,
    ``inner_radius`` R_i, ``radius`` r (between R_i and R_o), ``rotational_speed`` ω,
    and Poisson's ratio ``poisson`` ν describe the disc and the point. Returns the
    radial stress in MPa.
    """
    rho, ro, ri, r, omega = _annular_disc_inputs(
        density, outer_radius, inner_radius, radius, rotational_speed, poisson
    )
    sigma = (3.0 + poisson) / 8.0 * rho * omega**2 * (ro**2 + ri**2 - ri**2 * ro**2 / r**2 - r**2)
    return Quantity(magnitude=sigma / 1e6, unit="MPa")


def rotating_annular_disc_tangential_stress(
    *,
    density: Quantity,
    outer_radius: Quantity,
    inner_radius: Quantity,
    radius: Quantity,
    rotational_speed: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The tangential (hoop) stress at a radius in a rotating annular disc,
    σ_θ = (3 + ν)/8·ρ·ω²·(R_o² + R_i² + R_i²·R_o²/r² − (1 + 3ν)/(3 + ν)·r²).

    The tangential stress is greatest at the bore (r = R_i), where it equals the
    :func:`rotating_annular_disc_bore_stress`, and falls monotonically to the rim.
    ``density`` ρ, ``outer_radius`` R_o, ``inner_radius`` R_i, ``radius`` r (between
    R_i and R_o), ``rotational_speed`` ω, and Poisson's ratio ``poisson`` ν are as in
    :func:`rotating_annular_disc_radial_stress`. Returns the tangential stress in MPa.
    """
    rho, ro, ri, r, omega = _annular_disc_inputs(
        density, outer_radius, inner_radius, radius, rotational_speed, poisson
    )
    sigma = (
        (3.0 + poisson)
        / 8.0
        * rho
        * omega**2
        * (ro**2 + ri**2 + ri**2 * ro**2 / r**2 - (1.0 + 3.0 * poisson) / (3.0 + poisson) * r**2)
    )
    return Quantity(magnitude=sigma / 1e6, unit="MPa")
