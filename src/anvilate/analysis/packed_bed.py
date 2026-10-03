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

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_BED_SOURCE = "the bed design drawing (bed length) and packing specification"
_PARTICLE_SOURCE = "the packing datasheet (particle size, density, and voidage)"
_FLUID_SOURCE = "the fluid's density and viscosity at operating conditions from its datasheet"
_OPERATING_SOURCE = "the superficial velocity from the process operating case"
_SCOPE_SOURCE = "finer particles, or the full Ergun or Wen-Yu correlation"


class _PackedBedInputError(RefusalError, ValueError):
    """A packed-bed input that cannot be used without correction."""


def _packed_bed_refusal(message: str, *, subject: str, source: str) -> _PackedBedInputError:
    return _PackedBedInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _packed_bed_input_source(name: str) -> str:
    if name == "bed_length":
        return _BED_SOURCE
    if name == "superficial_velocity":
        return _OPERATING_SOURCE
    if name in {"fluid_density", "fluid_viscosity"}:
        return _FLUID_SOURCE
    return _PARTICLE_SOURCE


_GRAVITY = 9.80665  # m/s^2, standard gravity

__all__ = [
    "ergun_pressure_drop",
    "minimum_fluidization_velocity",
    "packed_bed_void_fraction",
    "specific_surface_area",
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
    require_finite(void_fraction, name="void_fraction")
    _check(bed_length, "[length]", "bed_length")
    _check(particle_diameter, "[length]", "particle_diameter")
    _check(superficial_velocity, "[length]/[time]", "superficial_velocity")
    _check(fluid_density, "[mass]/[length]**3", "fluid_density")
    _check(fluid_viscosity, "[pressure]*[time]", "fluid_viscosity")
    if not 0.0 < void_fraction < 1.0:
        raise _packed_bed_refusal(
            f"void_fraction must be in (0, 1); got {void_fraction}",
            subject="void_fraction",
            source=_PARTICLE_SOURCE,
        )
    length = bed_length.to("m").magnitude
    dp = particle_diameter.to("m").magnitude
    u = superficial_velocity.to("m/s").magnitude
    rho = fluid_density.to("kg/m**3").magnitude
    mu = fluid_viscosity.to("Pa*s").magnitude
    if length < 0:
        raise _packed_bed_refusal(
            "bed_length must be non-negative", subject="bed_length", source=_BED_SOURCE
        )
    if dp <= 0:
        raise _packed_bed_refusal(
            "particle_diameter must be positive",
            subject="particle_diameter",
            source=_PARTICLE_SOURCE,
        )
    if u < 0:
        raise _packed_bed_refusal(
            "superficial_velocity must be non-negative",
            subject="superficial_velocity",
            source=_OPERATING_SOURCE,
        )
    if rho <= 0 or mu <= 0:
        raise _packed_bed_refusal(
            "fluid_density and fluid_viscosity must be positive",
            subject="fluid_density and fluid_viscosity",
            source=_FLUID_SOURCE,
        )
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
        raise _packed_bed_refusal(
            "bulk_density must be non-negative", subject="bulk_density", source=_PARTICLE_SOURCE
        )
    if rho_p <= 0:
        raise _packed_bed_refusal(
            "particle_density must be positive", subject="particle_density", source=_PARTICLE_SOURCE
        )
    if rho_bulk > rho_p:
        raise _packed_bed_refusal(
            "bulk_density cannot exceed particle_density (ε < 0 is impossible)",
            subject="bulk_density and particle_density",
            source=_PARTICLE_SOURCE,
        )
    return 1.0 - rho_bulk / rho_p


# The Ergun viscous-only branch is a laminar result; Re_mf ≈ 20 is the usual seam.
_LAMINAR_FLUIDIZATION_REYNOLDS_LIMIT = 20.0


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
    require_finite(void_fraction, name="void_fraction")
    _check(particle_diameter, "[length]", "particle_diameter")
    _check(particle_density, "[mass]/[length]**3", "particle_density")
    _check(fluid_density, "[mass]/[length]**3", "fluid_density")
    if fluid_density.magnitude <= 0:
        raise _packed_bed_refusal(
            f"fluid_density must be positive; got {fluid_density}",
            subject="fluid_density",
            source=_FLUID_SOURCE,
        )
    _check(fluid_viscosity, "[pressure]*[time]", "fluid_viscosity")
    if not 0.0 < void_fraction < 1.0:
        raise _packed_bed_refusal(
            f"void_fraction must be in (0, 1); got {void_fraction}",
            subject="void_fraction",
            source=_PARTICLE_SOURCE,
        )
    dp = particle_diameter.to("m").magnitude
    rho_p = particle_density.to("kg/m**3").magnitude
    rho = fluid_density.to("kg/m**3").magnitude
    mu = fluid_viscosity.to("Pa*s").magnitude
    if dp <= 0:
        raise _packed_bed_refusal(
            "particle_diameter must be positive",
            subject="particle_diameter",
            source=_PARTICLE_SOURCE,
        )
    if mu <= 0:
        raise _packed_bed_refusal(
            "fluid_viscosity must be positive", subject="fluid_viscosity", source=_FLUID_SOURCE
        )
    if rho_p <= rho:
        raise _packed_bed_refusal(
            "particle_density must exceed fluid_density for the bed to fluidize",
            subject="particle_density and fluid_density",
            source=_PARTICLE_SOURCE,
        )
    eps = void_fraction
    u_mf = dp**2 * (rho_p - rho) * _GRAVITY * eps**3 / (150.0 * mu * (1.0 - eps))
    # This is the LAMINAR limit of the Ergun equation — the docstring says so — and the
    # particle Reynolds number that decides whether that limit applies is computable from
    # the arguments already passed. Past it the answer runs high without bound: 1 mm sand
    # in air is already 1.8x over Wen-Yu, 3 mm is 6.3x, and 5 mm returns 25.7 m/s, above
    # the particle's own terminal velocity — a bed that would be conveyed away rather than
    # fluidized. The inertial (Ergun/Wen-Yu) form is needed there.
    reynolds = rho * u_mf * dp / mu
    if reynolds > _LAMINAR_FLUIDIZATION_REYNOLDS_LIMIT:
        raise _packed_bed_refusal(
            f"the result implies a particle Reynolds number of {reynolds:.4g}, past the "
            f"~{_LAMINAR_FLUIDIZATION_REYNOLDS_LIMIT:.0f} where this laminar limit of the "
            f"Ergun equation holds. Above it the viscous-only form overpredicts without "
            f"bound (6.3x for 3 mm sand in air); use the full Ergun or the Wen-Yu "
            f"correlation for coarse particles.",
            subject=(
                "particle_diameter, particle_density, fluid_density, fluid_viscosity, and "
                "void_fraction"
            ),
            source=_SCOPE_SOURCE,
        )
    return Quantity(magnitude=u_mf, unit="m/s")


def specific_surface_area(*, void_fraction: float, particle_diameter: Quantity) -> Quantity:
    """A packed bed's interfacial area per unit bed volume, a_v = 6·(1−ε)/d_p.

    The surface the fluid actually meets, per cubic metre of bed. A sphere of diameter d_p has a
    surface-to-volume ratio of 6/d_p, and a fraction (1 − ``void_fraction`` ε) of the bed volume is
    solid, so a_v = 6·(1−ε)/d_p from the ``particle_diameter`` d_p. This is the quantity Ergun's
    150 and 1.75 constants (:func:`ergun_pressure_drop`) are built on, and the module consumed both
    ε and d_p without ever exposing it.

    It is the number that decides everything the bed is for: catalyst activity, adsorption
    capacity, and the heat- and mass-transfer area of a packed column all scale with it, and so
    does the pressure drop, which is the trade. Inverse in particle size — halving the packing
    diameter doubles the area and costs four times the drop — which is why packing size is the
    central design choice in a reactor or a scrubber. Assumes spherical particles; multiply by a
    sphericity below 1 for irregular packing. Returns the specific surface area in 1/m (m² of
    surface per m³ of bed).
    """
    require_finite(void_fraction, name="void_fraction")
    _check(particle_diameter, "[length]", "particle_diameter")
    d_p = particle_diameter.to("m").magnitude
    if not 0.0 <= void_fraction < 1.0:
        raise _packed_bed_refusal(
            f"void_fraction must be in 0..1 (a fraction, not a percent); got {void_fraction}",
            subject="void_fraction",
            source=_PARTICLE_SOURCE,
        )
    if d_p <= 0:
        raise _packed_bed_refusal(
            "particle_diameter must be positive",
            subject="particle_diameter",
            source=_PARTICLE_SOURCE,
        )
    return Quantity(magnitude=6.0 * (1.0 - void_fraction) / d_p, unit="1/m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _packed_bed_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_packed_bed_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _packed_bed_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_packed_bed_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
