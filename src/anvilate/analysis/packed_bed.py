"""T1 analytical packed-bed flow checks (Ergun pressure drop, closed-form).

Push a fluid through a bed of packed particles — a catalyst reactor, an adsorption or ion-exchange
column, a filter, a pebble-bed heat store — and it loses pressure to two effects at once: viscous
drag along the tortuous pore walls (dominant at low flow) and inertial losses as the fluid weaves
around the particles (dominant at high flow). The Ergun equation sums both:

    ΔP/L = 150·(1−ε)²/ε³ · μ·U/d_p²  +  1.75·(1−ε)/ε³ · ρ·U²/d_p

from the bed ``void_fraction`` ε (the fraction of the bed that is open space), the
``particle_diameter`` d_p, the ``superficial_velocity`` U (the volumetric flow divided by the empty
column's cross-section, not the faster interstitial speed), and the fluid ``density`` ρ and
``viscosity`` μ. The first term is the viscous (Kozeny-Carman) contribution, the second the inertial
(Burke-Plummer) one; the (1−ε)/ε³ grouping is why a small drop in voidage raises the pressure drop
steeply. The void fraction itself follows from how loosely the particles pack, ε = 1 − ρ_bulk/ρ_p,
the bulk (poured) density over the solid particle density. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values; the void fraction is a plain float.
"""

from __future__ import annotations

from ..units import Quantity

_GRAVITY = 9.80665  # m/s^2, standard gravity

__all__ = [
    "ergun_pressure_drop",
    "minimum_fluidization_velocity",
    "packed_bed_void_fraction",
]


def ergun_pressure_drop(
    *,
    bed_length: Quantity,
    particle_diameter: Quantity,
    void_fraction: float,
    superficial_velocity: Quantity,
    fluid_density: Quantity,
    fluid_viscosity: Quantity,
) -> Quantity:
    """The Ergun packed-bed pressure drop, ΔP = L·[150·(1−ε)²/ε³·μU/d_p² + 1.75·(1−ε)/ε³·ρU²/d_p].

    The pressure lost driving a fluid through a bed of packing: from the ``bed_length`` L, the
    ``particle_diameter`` d_p, the ``void_fraction`` ε, the ``superficial_velocity`` U (flow over
    the empty-column area), and the fluid ``fluid_density`` ρ and ``fluid_viscosity`` μ. The first
    term is the viscous (Kozeny-Carman) loss that dominates in laminar creeping flow; the second is
    the inertial (Burke-Plummer) loss that dominates at high flow — the Ergun equation blends both
    across the whole range. It sizes the blower or pump for a catalyst reactor, adsorption column,
    or pebble bed, and warns when a fine or densely packed bed will choke on pressure drop. Returns
    the pressure drop in Pa.
    """
    _check(bed_length, "[length]", "bed_length")
    _check(particle_diameter, "[length]", "particle_diameter")
    _check(superficial_velocity, "[length]/[time]", "superficial_velocity")
    _check(fluid_density, "[mass]/[length]**3", "fluid_density")
    _check(fluid_viscosity, "[pressure]*[time]", "fluid_viscosity")
    if not 0.0 < void_fraction < 1.0:
        raise ValueError(f"void_fraction must be in (0, 1); got {void_fraction}")
    length = bed_length.to("m").magnitude
    dp = particle_diameter.to("m").magnitude
    u = superficial_velocity.to("m/s").magnitude
    rho = fluid_density.to("kg/m**3").magnitude
    mu = fluid_viscosity.to("Pa*s").magnitude
    if length < 0:
        raise ValueError("bed_length must be non-negative")
    if dp <= 0:
        raise ValueError("particle_diameter must be positive")
    if u < 0:
        raise ValueError("superficial_velocity must be non-negative")
    if rho <= 0 or mu <= 0:
        raise ValueError("fluid_density and fluid_viscosity must be positive")
    eps = void_fraction
    viscous = 150.0 * (1.0 - eps) ** 2 / eps**3 * mu * u / dp**2
    inertial = 1.75 * (1.0 - eps) / eps**3 * rho * u**2 / dp
    return Quantity(magnitude=(viscous + inertial) * length, unit="Pa")


def packed_bed_void_fraction(*, bulk_density: Quantity, particle_density: Quantity) -> float:
    """The bed void fraction from densities, ε = 1 − ρ_bulk/ρ_p.

    The fraction of a packed bed that is open space, from the poured ``bulk_density`` ρ_bulk of the
    bed and the ``particle_density`` ρ_p of the solid particles: ε = 1 − ρ_bulk/ρ_p. A loosely
    poured bed of spheres runs ε ≈ 0.4; denser packing lowers it. It is the voidage the Ergun
    equation (:func:`ergun_pressure_drop`) needs, obtained from two easy density measurements rather
    than a geometric packing model. Returns the void fraction (0 to 1) as a plain float.
    """
    _check(bulk_density, "[mass]/[length]**3", "bulk_density")
    _check(particle_density, "[mass]/[length]**3", "particle_density")
    rho_bulk = bulk_density.to("kg/m**3").magnitude
    rho_p = particle_density.to("kg/m**3").magnitude
    if rho_bulk < 0:
        raise ValueError("bulk_density must be non-negative")
    if rho_p <= 0:
        raise ValueError("particle_density must be positive")
    if rho_bulk > rho_p:
        raise ValueError("bulk_density cannot exceed particle_density (ε < 0 is impossible)")
    return 1.0 - rho_bulk / rho_p


def minimum_fluidization_velocity(
    *,
    particle_diameter: Quantity,
    particle_density: Quantity,
    fluid_density: Quantity,
    fluid_viscosity: Quantity,
    void_fraction: float,
) -> Quantity:
    """The minimum fluidization velocity, U_mf = d_p²·(ρ_p−ρ)·g·ε³/(150·μ·(1−ε)).

    The superficial velocity at which an upward gas flow just lifts a packed bed into a fluidized
    state — where the bed pressure drop equals the bed weight per area: from the
    ``particle_diameter`` d_p, the ``particle_density`` ρ_p, the ``fluid_density`` ρ, the
    ``fluid_viscosity`` μ, and the voidage ``void_fraction`` ε at minimum fluidization,
    U_mf = d_p²·(ρ_p−ρ)·g·ε³/(150·μ·(1−ε)). This
    is the laminar (small-particle) limit of the Ergun equation, valid for fine particles where the
    viscous term dominates; below U_mf the bed is a fixed bed (:func:`ergun_pressure_drop`), above
    it the particles are suspended. It sets the operating window of a fluidized-bed reactor or
    dryer. Returns the minimum fluidization velocity in m/s.
    """
    _check(particle_diameter, "[length]", "particle_diameter")
    _check(particle_density, "[mass]/[length]**3", "particle_density")
    _check(fluid_density, "[mass]/[length]**3", "fluid_density")
    _check(fluid_viscosity, "[pressure]*[time]", "fluid_viscosity")
    if not 0.0 < void_fraction < 1.0:
        raise ValueError(f"void_fraction must be in (0, 1); got {void_fraction}")
    dp = particle_diameter.to("m").magnitude
    rho_p = particle_density.to("kg/m**3").magnitude
    rho = fluid_density.to("kg/m**3").magnitude
    mu = fluid_viscosity.to("Pa*s").magnitude
    if dp <= 0:
        raise ValueError("particle_diameter must be positive")
    if mu <= 0:
        raise ValueError("fluid_viscosity must be positive")
    if rho_p <= rho:
        raise ValueError("particle_density must exceed fluid_density for the bed to fluidize")
    eps = void_fraction
    u_mf = dp**2 * (rho_p - rho) * _GRAVITY * eps**3 / (150.0 * mu * (1.0 - eps))
    return Quantity(magnitude=u_mf, unit="m/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
