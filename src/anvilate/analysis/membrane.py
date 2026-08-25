"""T1 analytical reverse-osmosis membrane transport checks (solution-diffusion, closed-form).

A reverse-osmosis membrane pushes water through while holding dissolved salt back, and the
solution-diffusion model describes both fluxes with two membrane coefficients.

Water crosses in proportion to the *net* driving pressure — the applied pressure beyond the osmotic
pressure the salt exerts back: J_w = A·(ΔP − Δπ), where A is the membrane's water permeability and
Δπ is the osmotic-pressure difference across it (from
:func:`anvilate.analysis.colligative.osmotic_pressure`). Below the osmotic pressure no water
permeates at all, which is why seawater RO runs at 55-70 bar.

Salt crosses by diffusion, driven by its concentration difference and largely independent of
pressure: J_s = B·ΔC, with B the salt permeability. Because raising pressure lifts the water flux
but not the salt flux, more pressure both makes more permeate and dilutes it — the permeate
concentration is C_p = J_s/J_w. The membrane's salt rejection is then R = 1 − C_p/C_f against the
feed. Permeabilities, pressures, and concentrations are dimension-checked
:class:`~anvilate.units.Quantity` values; rejection is a plain float.

Sources: Baker, *Membrane Technology and Applications* (reverse osmosis) — the solution-
diffusion water flux driven by the net pressure less the osmotic difference, the salt flux
driven by concentration alone, the permeate concentration those imply, and the salt rejection
that reports them together.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "membrane_permeate_concentration",
    "membrane_salt_flux",
    "reverse_osmosis_water_flux",
    "salt_rejection",
]


def reverse_osmosis_water_flux(
    *,
    water_permeability: Quantity,
    applied_pressure: Quantity,
    osmotic_pressure_difference: Quantity,
) -> Quantity:
    """The reverse-osmosis water flux, J_w = A·(ΔP − Δπ).

    The volume of water permeating per unit membrane area per time: from the ``water_permeability``
    A (a membrane property, e.g. L/(m²·h·bar)), the ``applied_pressure`` ΔP across the membrane, and
    the ``osmotic_pressure_difference`` Δπ the retained salt exerts back, J_w = A·(ΔP − Δπ). Only
    the net driving pressure ΔP − Δπ produces flux, so the applied pressure must exceed the osmotic
    pressure for any water to cross — the reason seawater RO needs 55-70 bar. Returns the flux in
    L/(m²·h) (LMH, the standard membrane flux unit).
    """
    _check(water_permeability, "[length]/([time]*[pressure])", "water_permeability")
    _check(applied_pressure, "[pressure]", "applied_pressure")
    _check(osmotic_pressure_difference, "[pressure]", "osmotic_pressure_difference")
    a = water_permeability.to("m/(s*Pa)").magnitude
    dp = applied_pressure.to("Pa").magnitude
    dpi = osmotic_pressure_difference.to("Pa").magnitude
    if a <= 0:
        raise ValueError("water_permeability must be positive")
    if dpi < 0:
        raise ValueError("osmotic_pressure_difference must be non-negative")
    if dp <= dpi:
        raise ValueError(
            "applied_pressure must exceed the osmotic pressure difference for net permeation"
        )
    flux = a * (dp - dpi)  # m/s
    return Quantity(magnitude=flux, unit="m/s").to("L/(m**2*hour)")


def membrane_salt_flux(
    *, salt_permeability: Quantity, concentration_difference: Quantity
) -> Quantity:
    """The membrane salt flux, J_s = B·ΔC.

    The mass of salt diffusing through the membrane per unit area per time: from the
    ``salt_permeability`` B (a membrane property with units of velocity) and the
    ``concentration_difference`` ΔC of salt across it, J_s = B·ΔC. Unlike the water flux it barely
    depends on pressure, so raising pressure dilutes the permeate (its concentration is J_s/J_w with
    the water flux of :func:`reverse_osmosis_water_flux`). Returns the salt flux in g/(m²·h).
    """
    _check(salt_permeability, "[length]/[time]", "salt_permeability")
    _check(concentration_difference, "[mass]/[length]**3", "concentration_difference")
    b = salt_permeability.to("m/s").magnitude
    dc = concentration_difference.to("kg/m**3").magnitude
    if b < 0:
        raise ValueError("salt_permeability must be non-negative")
    if dc < 0:
        raise ValueError("concentration_difference must be non-negative")
    flux = b * dc  # kg/(m^2*s)
    return Quantity(magnitude=flux, unit="kg/(m**2*s)").to("g/(m**2*hour)")


def membrane_permeate_concentration(*, salt_flux: Quantity, water_flux: Quantity) -> Quantity:
    """The permeate concentration, C_p = J_s/J_w.

    The salt left in the product water: the ``salt_flux`` J_s of :func:`membrane_salt_flux` divided
    by the ``water_flux`` J_w of :func:`reverse_osmosis_water_flux`, C_p = J_s/J_w — mass of salt
    per volume of water, both arriving through the same square metre of membrane. This is the link
    that makes the module's chain run end to end: the two fluxes are computed from the membrane's
    permeabilities, and :func:`salt_rejection` needs exactly this concentration to grade them.
    Because pressure lifts J_w but leaves J_s nearly alone, C_p falls as the system is pushed
    harder — the reason a membrane makes purer water at higher flux. Returns the permeate
    concentration in g/L (mg/L, i.e. ppm, is the same number times 1000).
    """
    _check(salt_flux, "[mass]/[length]**2/[time]", "salt_flux")
    _check(water_flux, "[length]/[time]", "water_flux")
    j_s = salt_flux.to("kg/(m**2*s)").magnitude
    j_w = water_flux.to("m/s").magnitude
    if j_s < 0:
        raise ValueError("salt_flux must be non-negative")
    if j_w <= 0:
        raise ValueError("water_flux must be positive")
    return Quantity(magnitude=j_s / j_w, unit="kg/m**3").to("g/L")


def salt_rejection(*, permeate_concentration: Quantity, feed_concentration: Quantity) -> float:
    """The membrane salt rejection, R = 1 − C_p/C_f.

    The fraction of feed salt the membrane keeps out of the permeate: from the
    ``permeate_concentration`` C_p and the ``feed_concentration`` C_f, R = 1 − C_p/C_f. A seawater
    RO membrane rejects ~0.995 (99.5%); the closer to 1, the purer the permeate. It is the headline
    quality figure of a membrane, complementing the water flux that sets its productivity. Returns
    the dimensionless rejection (0 to 1) as a plain float.
    """
    _check(permeate_concentration, "[mass]/[length]**3", "permeate_concentration")
    _check(feed_concentration, "[mass]/[length]**3", "feed_concentration")
    c_p = permeate_concentration.to("kg/m**3").magnitude
    c_f = feed_concentration.to("kg/m**3").magnitude
    if c_p < 0:
        raise ValueError("permeate_concentration must be non-negative")
    if c_f <= 0:
        raise ValueError("feed_concentration must be positive")
    if c_p > c_f:
        raise ValueError("permeate_concentration cannot exceed feed_concentration (R < 0)")
    return 1.0 - c_p / c_f


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
