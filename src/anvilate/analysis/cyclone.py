"""T1 analytical gas cyclone separator checks (Lapple model, closed-form).

A cyclone spins a dusty gas stream so that particles are flung to the wall and drop out while the
cleaned gas leaves through the top. Its performance is captured by one characteristic size and the
efficiency curve around it.

The cut diameter d_pc is the particle size collected with exactly 50% efficiency — the standard
figure of merit for a cyclone. Lapple's model gives it in closed form from the gas and geometry:
d_pc = √[9·μ·B / (2π·N_e·V_i·(ρ_p − ρ))], where μ is the gas viscosity, B the inlet width, N_e the
effective number of turns the gas makes in the body (≈ 5 for a standard high-efficiency cyclone),
V_i the inlet velocity, ρ_p the particle density, and ρ the gas density. A smaller cut diameter is a
sharper cyclone: higher inlet velocity, more turns, and denser particles all lower it.

Around the cut, Lapple's fractional-efficiency curve gives the collection efficiency of any particle
size, η = 1/(1 + (d_pc/d_p)²): particles at the cut are 50% collected, larger ones approach 100%,
finer ones slip through. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values; the turn count and efficiency are plain floats.
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

__all__ = [
    "cyclone_collection_efficiency",
    "cyclone_cut_diameter",
]


def cyclone_cut_diameter(
    *,
    gas_viscosity: Quantity,
    inlet_width: Quantity,
    effective_turns: float,
    inlet_velocity: Quantity,
    particle_density: Quantity,
    gas_density: Quantity,
) -> Quantity:
    """The Lapple cyclone cut diameter, d_pc = √[9·μ·B / (2π·N_e·V_i·(ρ_p − ρ))].

    The particle diameter a cyclone collects with 50% efficiency — its characteristic size: from the
    ``gas_viscosity`` μ, the ``inlet_width`` B, the ``effective_turns`` N_e the gas makes (≈ 5 for a
    standard cyclone), the ``inlet_velocity`` V_i, the ``particle_density`` ρ_p, and the
    ``gas_density`` ρ, d_pc = √[9·μ·B / (2π·N_e·V_i·(ρ_p − ρ))]. Faster inlet flow, more turns, and
    denser particles all shrink the cut diameter and sharpen the separation. Feed it to
    :func:`cyclone_collection_efficiency`. Returns the cut diameter (in µm).
    """
    _check(gas_viscosity, "[pressure]*[time]", "gas_viscosity")
    _check(inlet_width, "[length]", "inlet_width")
    _check(inlet_velocity, "[length]/[time]", "inlet_velocity")
    _check(particle_density, "[mass]/[length]**3", "particle_density")
    _check(gas_density, "[mass]/[length]**3", "gas_density")
    mu = gas_viscosity.to("Pa*s").magnitude
    b = inlet_width.to("m").magnitude
    v_i = inlet_velocity.to("m/s").magnitude
    rho_p = particle_density.to("kg/m**3").magnitude
    rho = gas_density.to("kg/m**3").magnitude
    if effective_turns <= 0:
        raise ValueError("effective_turns must be positive")
    if mu <= 0 or b <= 0 or v_i <= 0:
        raise ValueError("gas_viscosity, inlet_width, and inlet_velocity must be positive")
    if rho_p <= rho:
        raise ValueError("particle_density must exceed gas_density for the particle to separate")
    d_pc = sqrt(9.0 * mu * b / (2.0 * pi * effective_turns * v_i * (rho_p - rho)))
    return Quantity(magnitude=d_pc, unit="m").to("um")


def cyclone_collection_efficiency(*, particle_diameter: Quantity, cut_diameter: Quantity) -> float:
    """The Lapple fractional collection efficiency, η = 1/(1 + (d_pc/d_p)²).

    The fraction of particles of a given ``particle_diameter`` d_p that a cyclone captures, from its
    ``cut_diameter`` d_pc (from :func:`cyclone_cut_diameter`): η = 1/(1 + (d_pc/d_p)²). A particle
    at the cut size is caught half the time, one twice the cut size ≈ 80%, and one at half the cut
    ≈ 20% — the S-shaped grade-efficiency curve that says a cyclone is a size classifier, not a
    sharp filter. Returns the collection efficiency (0 to 1) as a plain float.
    """
    _check(particle_diameter, "[length]", "particle_diameter")
    _check(cut_diameter, "[length]", "cut_diameter")
    d_p = particle_diameter.to("m").magnitude
    d_pc = cut_diameter.to("m").magnitude
    if d_p <= 0:
        raise ValueError("particle_diameter must be positive")
    if d_pc <= 0:
        raise ValueError("cut_diameter must be positive")
    return 1.0 / (1.0 + (d_pc / d_p) ** 2)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
