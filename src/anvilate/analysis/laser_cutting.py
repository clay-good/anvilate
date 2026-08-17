"""T1 analytical laser-cutting checks (closed-form energy balance).

Laser cutting severs a sheet by focusing a beam to melt (or vaporize) a narrow kerf and blowing the
melt out with an assist gas. Unlike the mechanical cuts of :mod:`anvilate.analysis.machining`, there
is no tool and no force — the limit is *energy*. The beam must pour in enough power to heat and melt
every bit of metal the kerf sweeps up as it advances, so the process is a straight power balance:
the faster the cut or the thicker the plate, the more power the melt front demands, and when demand
outruns the beam the cut stops severing and the plate is merely scored.

Three numbers describe the balance. The specific removal energy e_m = c·ΔT + L_f is the energy to
take a unit mass of metal from room temperature to its melting point (c·ΔT) and then melt it (the
latent heat L_f) — the price per kilogram of kerf. The cutting speed v = η·P/(ρ·t·w·e_m) is what the
beam power P buys once coupled at an efficiency η: the melt front consumes ρ·t·w·e_m of energy per
unit length of the kerf (thickness t, width w), so the speed is power over that. Inverting it gives
the design limit: the greatest thickness t_max = η·P/(ρ·v·w·e_m) a laser of a given power can sever
at a chosen speed — the number that decides whether a job fits the machine.
"""

from __future__ import annotations

from ..units import Quantity
from ..units.temperature import temperature_difference_kelvin

__all__ = [
    "laser_cutting_speed",
    "laser_max_cut_thickness",
    "laser_specific_removal_energy",
]


def laser_specific_removal_energy(
    *, specific_heat: Quantity, temperature_rise: Quantity, latent_heat_of_fusion: Quantity
) -> Quantity:
    """The specific removal energy, e_m = c·ΔT + L_f.

    The energy to remove a unit mass of metal at the kerf: the sensible heat c·ΔT to raise it from
    room temperature to melting — the ``specific_heat`` c times the ``temperature_rise`` ΔT to the
    melting point — plus the ``latent_heat_of_fusion`` L_f to actually melt it, so e_m = c·ΔT + L_f.
    It is the price per kilogram of kerf that sets the cutting speed (:func:`laser_cutting_speed`).
    A pure-vaporization cut would add the latent heat of vaporization on top; this melt-and-blow
    form is the usual model for oxygen- or nitrogen-assisted cutting. Returns e_m in MJ/kg.
    """
    _check(specific_heat, "[energy]/([mass]*[temperature])", "specific_heat")
    _check(temperature_rise, "[temperature]", "temperature_rise")
    _check(latent_heat_of_fusion, "[energy]/[mass]", "latent_heat_of_fusion")
    c = specific_heat.to("J/(kg*K)").magnitude
    dt = temperature_difference_kelvin(temperature_rise, name="temperature_rise")
    lf = latent_heat_of_fusion.to("J/kg").magnitude
    if c <= 0:
        raise ValueError("specific_heat must be positive")
    if dt <= 0:
        raise ValueError("temperature_rise must be positive")
    if lf < 0:
        raise ValueError("latent_heat_of_fusion must be non-negative")
    return Quantity(magnitude=(c * dt + lf) / 1.0e6, unit="MJ/kg")


def laser_cutting_speed(
    *,
    beam_power: Quantity,
    coupling_efficiency: float,
    thickness: Quantity,
    kerf_width: Quantity,
    density: Quantity,
    specific_removal_energy: Quantity,
) -> Quantity:
    """The laser cutting speed, v = η·P/(ρ·t·w·e_m).

    The traverse speed the beam can sustain and still sever the plate: the ``beam_power`` P coupled
    into the metal at the ``coupling_efficiency`` η, spread over the energy the melt front consumes
    per unit length of kerf — the ``density`` ρ times the ``thickness`` t, the ``kerf_width`` w, and
    the ``specific_removal_energy`` e_m (from :func:`laser_specific_removal_energy`) — so
    v = η·P/(ρ·t·w·e_m). Go faster than this and the beam cannot melt the full depth, and the cut
    stops severing. Returns the cutting speed in m/min.
    """
    _check(beam_power, "[power]", "beam_power")
    _check(thickness, "[length]", "thickness")
    _check(kerf_width, "[length]", "kerf_width")
    _check(density, "[mass]/[length]**3", "density")
    _check(specific_removal_energy, "[energy]/[mass]", "specific_removal_energy")
    _fraction(coupling_efficiency, "coupling_efficiency")
    p = beam_power.to("W").magnitude
    t = thickness.to("m").magnitude
    w = kerf_width.to("m").magnitude
    rho = density.to("kg/m**3").magnitude
    e_m = specific_removal_energy.to("J/kg").magnitude
    if p <= 0:
        raise ValueError("beam_power must be positive")
    if t <= 0:
        raise ValueError("thickness must be positive")
    if w <= 0:
        raise ValueError("kerf_width must be positive")
    if rho <= 0:
        raise ValueError("density must be positive")
    if e_m <= 0:
        raise ValueError("specific_removal_energy must be positive")
    v_m_per_s = coupling_efficiency * p / (rho * t * w * e_m)
    return Quantity(magnitude=v_m_per_s * 60.0, unit="m/min")


def laser_max_cut_thickness(
    *,
    beam_power: Quantity,
    coupling_efficiency: float,
    cutting_speed: Quantity,
    kerf_width: Quantity,
    density: Quantity,
    specific_removal_energy: Quantity,
) -> Quantity:
    """The greatest thickness a laser can sever, t_max = η·P/(ρ·v·w·e_m).

    Inverting the cutting-speed balance (:func:`laser_cutting_speed`) for thickness: the thickest
    plate a ``beam_power`` P (coupled at ``coupling_efficiency`` η) can cut through at a chosen
    ``cutting_speed`` v, t_max = η·P/(ρ·v·w·e_m), from the ``density`` ρ, the ``kerf_width`` w, and
    the ``specific_removal_energy`` e_m. It is the reach of the machine: a plate thicker than this
    cannot be severed at that speed no matter the gas pressure, and the cut must be slowed or moved
    to a bigger laser. Returns the maximum thickness in mm.
    """
    _check(beam_power, "[power]", "beam_power")
    _check(cutting_speed, "[length]/[time]", "cutting_speed")
    _check(kerf_width, "[length]", "kerf_width")
    _check(density, "[mass]/[length]**3", "density")
    _check(specific_removal_energy, "[energy]/[mass]", "specific_removal_energy")
    _fraction(coupling_efficiency, "coupling_efficiency")
    p = beam_power.to("W").magnitude
    v = cutting_speed.to("m/s").magnitude
    w = kerf_width.to("m").magnitude
    rho = density.to("kg/m**3").magnitude
    e_m = specific_removal_energy.to("J/kg").magnitude
    if p <= 0:
        raise ValueError("beam_power must be positive")
    if v <= 0:
        raise ValueError("cutting_speed must be positive")
    if w <= 0:
        raise ValueError("kerf_width must be positive")
    if rho <= 0:
        raise ValueError("density must be positive")
    if e_m <= 0:
        raise ValueError("specific_removal_energy must be positive")
    t_max_m = coupling_efficiency * p / (rho * v * w * e_m)
    return Quantity(magnitude=t_max_m * 1000.0, unit="mm")


def _fraction(value: float, name: str) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be a fraction in (0, 1]; got {value}")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
