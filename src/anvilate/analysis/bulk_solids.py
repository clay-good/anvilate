"""T1 analytical bulk-solids handling checks (closed-form).

Granular material — ore, grain, aggregate, powder, pellets — does not behave like a liquid, and two
of its habits govern handling plant. It discharges from a hopper orifice at a rate set by the
opening size and almost nothing else (not the head above it, unlike a draining tank), and heaped
it forms a cone at a fixed angle of repose. These give the feeder throughput and the stockpile
capacity that size a bulk-materials system, alongside the silo wall pressure of
:mod:`anvilate.analysis.geotechnical` (Janssen) and the belt throughput of
:mod:`anvilate.analysis.conveyor`.

Discharge follows the Beverloo correlation, W = C·ρ_b·√g·(D_o − k·d_p)^2.5, from the orifice
diameter D_o, the particle diameter d_p, and the bulk density ρ_b, with the empirical C (~0.58) and
shape factor k (~1.4 for smooth grains, higher for angular). The (D_o − k·d_p) term is why an
opening near a few particle diameters arches and stops, and the 2.5 power is why a small change
swings the rate hard. Inverting it sizes the orifice for a target feed. A heaped cone of base radius
R at the angle of repose φ holds V = (π/3)·R³·tan φ — the stockpile-capacity relation.

Sources: Schulze, *Powders and Bulk Solids* — the Beverloo correlation for gravity discharge
through an orifice, the orifice a target rate needs, and the volume of a conical stockpile at
its angle of repose.
"""

from __future__ import annotations

from math import pi, radians, sqrt, tan

from ..units import Quantity

STANDARD_GRAVITY_M_PER_S2 = 9.80665

__all__ = [
    "beverloo_discharge_rate",
    "beverloo_orifice_for_rate",
    "conical_stockpile_volume",
]


def beverloo_discharge_rate(
    *,
    orifice_diameter: Quantity,
    particle_diameter: Quantity,
    bulk_density: Quantity,
    discharge_coefficient: float = 0.58,
    shape_factor: float = 1.4,
) -> Quantity:
    """The Beverloo hopper discharge rate, W = C·ρ_b·√g·(D_o − k·d_p)^2.5.

    The mass flow of granular material through a flat-bottomed hopper orifice: from the
    ``orifice_diameter`` D_o, the ``particle_diameter`` d_p, and the ``bulk_density`` ρ_b, with the
    ``discharge_coefficient`` C (~0.58) and ``shape_factor`` k (~1.4 for smooth grains), W =
    C·ρ_b·√g·(D_o − k·d_p)^2.5. It is almost independent of the head of material above — a hopper
    empties at a near-constant rate, unlike a draining tank — and the 2.5 power makes it swing hard
    with the opening. Returns the mass flow in kg/s.
    """
    _check(orifice_diameter, "[length]", "orifice_diameter")
    _check(particle_diameter, "[length]", "particle_diameter")
    _check(bulk_density, "[mass]/[length]**3", "bulk_density")
    d_o = orifice_diameter.to("m").magnitude
    d_p = particle_diameter.to("m").magnitude
    rho = bulk_density.to("kg/m**3").magnitude
    if d_o <= 0:
        raise ValueError("orifice_diameter must be positive")
    if d_p <= 0:
        raise ValueError("particle_diameter must be positive")
    if rho <= 0:
        raise ValueError("bulk_density must be positive")
    if discharge_coefficient <= 0:
        raise ValueError("discharge_coefficient must be positive")
    if shape_factor <= 0:
        raise ValueError("shape_factor must be positive")
    effective = d_o - shape_factor * d_p
    if effective <= 0:
        raise ValueError(
            "orifice_diameter must exceed shape_factor*particle_diameter (else it arches and stops)"
        )
    w = discharge_coefficient * rho * sqrt(STANDARD_GRAVITY_M_PER_S2) * effective**2.5
    return Quantity(magnitude=w, unit="kg/s")


def beverloo_orifice_for_rate(
    *,
    mass_flow: Quantity,
    particle_diameter: Quantity,
    bulk_density: Quantity,
    discharge_coefficient: float = 0.58,
    shape_factor: float = 1.4,
) -> Quantity:
    """The orifice for a target discharge, D_o = k·d_p + (W/(C·ρ_b·√g))^(1/2.5).

    Inverting the Beverloo correlation (:func:`beverloo_discharge_rate`) for the opening: the
    diameter that discharges a target ``mass_flow`` W of material of ``particle_diameter`` d_p and
    ``bulk_density`` ρ_b, D_o = k·d_p + (W/(C·ρ_b·√g))^(1/2.5), with the ``discharge_coefficient`` C
    and ``shape_factor`` k. It is how a feeder or hopper outlet is sized to a required plant rate.
    Returns the orifice diameter in mm.
    """
    _check(mass_flow, "[mass]/[time]", "mass_flow")
    _check(particle_diameter, "[length]", "particle_diameter")
    _check(bulk_density, "[mass]/[length]**3", "bulk_density")
    w = mass_flow.to("kg/s").magnitude
    d_p = particle_diameter.to("m").magnitude
    rho = bulk_density.to("kg/m**3").magnitude
    if w <= 0:
        raise ValueError("mass_flow must be positive")
    if d_p <= 0:
        raise ValueError("particle_diameter must be positive")
    if rho <= 0:
        raise ValueError("bulk_density must be positive")
    if discharge_coefficient <= 0:
        raise ValueError("discharge_coefficient must be positive")
    if shape_factor <= 0:
        raise ValueError("shape_factor must be positive")
    effective = (w / (discharge_coefficient * rho * sqrt(STANDARD_GRAVITY_M_PER_S2))) ** (1.0 / 2.5)
    d_o = shape_factor * d_p + effective
    return Quantity(magnitude=d_o * 1000.0, unit="mm")


def conical_stockpile_volume(*, base_radius: Quantity, angle_of_repose: float) -> Quantity:
    """The conical stockpile volume, V = (π/3)·R³·tan φ.

    The volume of material heaped into a cone, as a stockpile poured from a fixed point forms: the
    base radius ``base_radius`` R and the ``angle_of_repose`` φ (degrees, the natural slope the
    material stands at) give a cone of height R·tan φ and volume V = (π/3)·R³·tan φ. It sizes
    stockpile capacity and, with the bulk density, the tonnage on the ground. Returns V in m**3.
    """
    _check(base_radius, "[length]", "base_radius")
    r = base_radius.to("m").magnitude
    if r <= 0:
        raise ValueError("base_radius must be positive")
    if not 0.0 < angle_of_repose < 90.0:
        raise ValueError("angle_of_repose must be in (0, 90) degrees")
    return Quantity(magnitude=pi / 3.0 * r**3 * tan(radians(angle_of_repose)), unit="m**3")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
