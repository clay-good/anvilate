"""T1 analytical corrosion / asset-integrity checks (metal-loss rates, closed-form).

Where :mod:`anvilate.analysis.wear` handles mechanical metal loss, this module handles
electrochemical loss — the wall thinning that governs the life of tanks, pipe, and pressure vessels.
Two measurements feed a rate, and the rate feeds a remaining life.

A coupon exposed and weighed gives the mass-loss rate directly: the uniform penetration rate is
CR = ΔW/(ρ·A·t), the lost volume (mass over density) spread over the exposed area and the exposure
time — a thickness lost per unit time (the ASTM G1 method, here computed in clean units with no
tabulated constant).

An electrochemical measurement gives a corrosion current density instead, which Faraday's law turns
into the same penetration rate: CR = 3.27×10⁻³·i_corr·EW/ρ (mm/yr), with i_corr in µA/cm², the
equivalent weight EW in grams per equivalent, and ρ in g/cm³ — the constant folds in Faraday's
number and the unit conversions.

Either rate, against the wall a component has left above its retirement thickness, gives the
remaining life a fitness-for-service assessment reports. Equivalent weight and density are the
caller's material values; the assessment belongs to the integrity engineer.
"""

from __future__ import annotations

from math import log10

from ..units import Quantity

__all__ = [
    "corrosion_penetration_rate",
    "faraday_corrosion_rate",
    "remaining_wall_life",
    "tafel_overpotential",
    "stern_geary_corrosion_current",
]


def corrosion_penetration_rate(
    *,
    mass_loss: Quantity,
    exposed_area: Quantity,
    exposure_time: Quantity,
    density: Quantity,
) -> Quantity:
    """The uniform corrosion penetration rate from a weight-loss coupon, CR = ΔW/(ρ·A·t).

    The ASTM G1 weight-loss method: a coupon of known ``exposed_area`` A and material ``density`` ρ
    loses ``mass_loss`` ΔW over ``exposure_time`` t, and the wall thins at CR = ΔW/(ρ·A·t) — the
    lost volume ΔW/ρ spread over the area and the time. Returns the penetration rate as a velocity
    (thickness per time) in mm/yr.
    """
    _check(mass_loss, "[mass]", "mass_loss")
    _check(exposed_area, "[length]**2", "exposed_area")
    _check(exposure_time, "[time]", "exposure_time")
    _check(density, "[mass]/[length]**3", "density")
    if mass_loss.to("kg").magnitude < 0:
        raise ValueError("mass_loss must be non-negative")
    if exposed_area.to("m**2").magnitude <= 0:
        raise ValueError("exposed_area must be positive")
    if exposure_time.to("s").magnitude <= 0:
        raise ValueError("exposure_time must be positive")
    if density.to("kg/m**3").magnitude <= 0:
        raise ValueError("density must be positive")
    rate = mass_loss.pint / (density.pint * exposed_area.pint * exposure_time.pint)
    return Quantity(magnitude=float(rate.to("mm/year").magnitude), unit="mm/year")


def faraday_corrosion_rate(
    *,
    corrosion_current_density: Quantity,
    equivalent_weight: float,
    density: Quantity,
) -> Quantity:
    """The penetration rate from a corrosion current density by Faraday's law, CR = 3.27e-3·i·EW/ρ.

    An electrochemical test (linear polarization, Tafel) yields a ``corrosion_current_density``
    i_corr rather than a weight loss; Faraday's law converts it to the same uniform penetration
    rate, CR = 3.27×10⁻³·i_corr·EW/ρ in mm/yr, with i_corr in µA/cm², the ``equivalent_weight`` EW
    (atomic weight over electrons transferred, g/equiv) as a plain number, and ``density`` ρ in
    g/cm³.
    The constant embeds Faraday's number and the unit conversions. Returns the penetration rate in
    mm/yr.
    """
    _check(corrosion_current_density, "[current]/[length]**2", "corrosion_current_density")
    _check(density, "[mass]/[length]**3", "density")
    if equivalent_weight <= 0:
        raise ValueError("equivalent_weight must be positive")
    rho = density.to("g/cm**3").magnitude
    if rho <= 0:
        raise ValueError("density must be positive")
    i_corr = corrosion_current_density.to("uA/cm**2").magnitude
    if i_corr < 0:
        raise ValueError("corrosion_current_density must be non-negative")
    cr = 3.27e-3 * i_corr * equivalent_weight / rho
    return Quantity(magnitude=cr, unit="mm/year")


def remaining_wall_life(
    *,
    current_thickness: Quantity,
    minimum_thickness: Quantity,
    corrosion_rate: Quantity,
) -> Quantity:
    """The remaining life before a wall reaches its retirement thickness, t = (t_c − t_min)/CR.

    A fitness-for-service estimate: a wall now at ``current_thickness`` t_c, thinning at a uniform
    ``corrosion_rate`` CR, reaches its ``minimum_thickness`` t_min (the retirement limit) in
    t = (t_c − t_min)/CR. Raises if the wall is already at or below the minimum. Returns the
    remaining life as a time in years.
    """
    _check(current_thickness, "[length]", "current_thickness")
    _check(minimum_thickness, "[length]", "minimum_thickness")
    _check(corrosion_rate, "[length]/[time]", "corrosion_rate")
    remaining = current_thickness.to("mm").magnitude - minimum_thickness.to("mm").magnitude
    if remaining <= 0:
        raise ValueError("current_thickness must exceed minimum_thickness (wall already retired)")
    rate = corrosion_rate.to("mm/year").magnitude
    if rate <= 0:
        raise ValueError("corrosion_rate must be positive")
    life = (current_thickness.pint - minimum_thickness.pint) / corrosion_rate.pint
    return Quantity(magnitude=float(life.to("year").magnitude), unit="year")


def tafel_overpotential(
    *,
    current_density: Quantity,
    exchange_current_density: Quantity,
    tafel_slope: Quantity,
) -> Quantity:
    """The activation overpotential by the Tafel equation, η = b·log₁₀(i/i₀).

    How far an electrode must be driven from equilibrium to sustain a net current: η =
    ``tafel_slope`` b · log₁₀(``current_density`` i / ``exchange_current_density`` i₀). The
    ``tafel_slope`` b (volts per decade of current) is the electrode-kinetics steepness, and i₀ the
    exchange current density at equilibrium. Every tenfold rise in current costs one more Tafel
    slope of overpotential — a fast electrode (large i₀, small b) needs little. The current must be
    at least the exchange current. Returns the overpotential in volts.
    """
    _check(current_density, "[current]/[length]**2", "current_density")
    _check(exchange_current_density, "[current]/[length]**2", "exchange_current_density")
    _check(tafel_slope, "[electric_potential]", "tafel_slope")
    i = current_density.to("A/m**2").magnitude
    i0 = exchange_current_density.to("A/m**2").magnitude
    b = tafel_slope.to("V").magnitude
    if i0 <= 0:
        raise ValueError("exchange_current_density must be positive")
    if i < i0:
        raise ValueError("current_density must be at least the exchange_current_density")
    if b <= 0:
        raise ValueError("tafel_slope must be positive")
    return Quantity(magnitude=b * log10(i / i0), unit="V")


def stern_geary_corrosion_current(
    *,
    polarization_resistance: Quantity,
    anodic_tafel_slope: Quantity,
    cathodic_tafel_slope: Quantity,
) -> Quantity:
    """The corrosion current from linear polarization, i_corr = B/R_p (Stern-Geary).

    The corrosion current density an LPR (linear polarization resistance) test yields:
    i_corr = B/``polarization_resistance``, with the Stern-Geary coefficient B =
    b_a·b_c/(2.303·(b_a + b_c)) from the ``anodic_tafel_slope`` and ``cathodic_tafel_slope``.
    The ``polarization_resistance`` R_p is the area-specific slope of potential over current near
    the corrosion potential (Ω·m²) — a large R_p means a slow-corroding, protected surface. Feed the
    result to :func:`faraday_corrosion_rate` for the penetration rate. Returns i_corr in A/m².
    """
    _check(
        polarization_resistance,
        "[electric_potential] * [length]**2 / [current]",
        "polarization_resistance",
    )
    _check(anodic_tafel_slope, "[electric_potential]", "anodic_tafel_slope")
    _check(cathodic_tafel_slope, "[electric_potential]", "cathodic_tafel_slope")
    r_p = polarization_resistance.to("ohm*m**2").magnitude
    b_a = anodic_tafel_slope.to("V").magnitude
    b_c = cathodic_tafel_slope.to("V").magnitude
    if r_p <= 0:
        raise ValueError("polarization_resistance must be positive")
    if b_a <= 0 or b_c <= 0:
        raise ValueError("Tafel slopes must be positive")
    b_stern_geary = b_a * b_c / (2.303 * (b_a + b_c))
    return Quantity(magnitude=b_stern_geary / r_p, unit="A/m**2")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
