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

Sources: Perry's Chemical Engineers' Handbook (gas-solid separations) — the Lapple cut
diameter of a cyclone, the grade efficiency curve it indexes, and the pressure drop in inlet
velocity heads.
"""

from __future__ import annotations

from math import pi, sqrt

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_CYCLONE_DRAWING_SOURCE = "the cyclone drawing and its design family's turn and head counts"
_GAS_SOURCE = "the cited gas density and viscosity at the operating temperature"
_DUTY_SOURCE = "the design gas flow and the resulting inlet velocity"
_DUST_SOURCE = "the dust's measured particle density and size distribution"


class _CycloneInputError(RefusalError, ValueError):
    """A cyclone-separator input that cannot be used without correction."""


def _cyclone_refusal(message: str, *, subject: str, source: str) -> _CycloneInputError:
    return _CycloneInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _cyclone_input_source(name: str) -> str:
    if name in {"effective_turns", "inlet_width", "velocity_head_count"}:
        return _CYCLONE_DRAWING_SOURCE
    if name in {"gas_density", "gas_viscosity"}:
        return _GAS_SOURCE
    if name in {"cut_diameter", "particle_density", "particle_diameter"}:
        return _DUST_SOURCE
    return _DUTY_SOURCE


__all__ = [
    "cyclone_collection_efficiency",
    "cyclone_cut_diameter",
    "cyclone_pressure_drop",
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
    require_finite(effective_turns, name="effective_turns")
    _check(gas_viscosity, "[pressure]*[time]", "gas_viscosity")
    _check(inlet_width, "[length]", "inlet_width")
    _check(inlet_velocity, "[length]/[time]", "inlet_velocity")
    _check(particle_density, "[mass]/[length]**3", "particle_density")
    _check(gas_density, "[mass]/[length]**3", "gas_density")
    if gas_density.magnitude <= 0:
        raise _cyclone_refusal(
            f"gas_density must be positive; got {gas_density}",
            subject="gas_density",
            source=_GAS_SOURCE,
        )
    mu = gas_viscosity.to("Pa*s").magnitude
    b = inlet_width.to("m").magnitude
    v_i = inlet_velocity.to("m/s").magnitude
    rho_p = particle_density.to("kg/m**3").magnitude
    rho = gas_density.to("kg/m**3").magnitude
    if effective_turns <= 0:
        raise _cyclone_refusal(
            "effective_turns must be positive",
            subject="effective_turns",
            source=_CYCLONE_DRAWING_SOURCE,
        )
    for subject, magnitude in (("gas_viscosity", mu), ("inlet_width", b), ("inlet_velocity", v_i)):
        if magnitude <= 0:
            raise _cyclone_refusal(
                "gas_viscosity, inlet_width, and inlet_velocity must be positive",
                subject=subject,
                source=_cyclone_input_source(subject),
            )
    if rho_p <= rho:
        raise _cyclone_refusal(
            "particle_density must exceed gas_density for the particle to separate",
            subject="particle_density and gas_density",
            source=_DUST_SOURCE,
        )
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
        raise _cyclone_refusal(
            "particle_diameter must be positive", subject="particle_diameter", source=_DUST_SOURCE
        )
    if d_pc <= 0:
        raise _cyclone_refusal(
            "cut_diameter must be positive", subject="cut_diameter", source=_DUST_SOURCE
        )
    return 1.0 / (1.0 + (d_pc / d_p) ** 2)


def cyclone_pressure_drop(
    *,
    inlet_velocity: Quantity,
    gas_density: Quantity,
    velocity_head_count: float = 8.0,
) -> Quantity:
    """The cyclone pressure drop, ΔP = N_H·½·ρ·v_in².

    The energy the swirling gas spends crossing a cyclone, and so the fan power it costs: a fixed
    number of inlet velocity heads, ΔP = ``velocity_head_count`` N_H · ½ · ``gas_density`` ρ ·
    ``inlet_velocity`` v_in². N_H is a dimensionless geometry constant (about 8 for a standard
    Stairmand cyclone) that rolls up the inlet, body, and vortex-finder losses. It rises with the
    *square* of inlet velocity — the same velocity that sharpens the :func:`cyclone_cut_diameter` —
    so finer cuts are paid for in pressure drop, the central design trade of a cyclone. Returns the
    pressure drop in pascals.
    """
    require_finite(velocity_head_count, name="velocity_head_count")
    _check(inlet_velocity, "[velocity]", "inlet_velocity")
    _check(gas_density, "[mass]/[volume]", "gas_density")
    v = inlet_velocity.to("m/s").magnitude
    rho = gas_density.to("kg/m**3").magnitude
    if v <= 0:
        raise _cyclone_refusal(
            "inlet_velocity must be positive", subject="inlet_velocity", source=_DUTY_SOURCE
        )
    if rho <= 0:
        raise _cyclone_refusal(
            "gas_density must be positive", subject="gas_density", source=_GAS_SOURCE
        )
    if velocity_head_count <= 0:
        raise _cyclone_refusal(
            "velocity_head_count must be positive",
            subject="velocity_head_count",
            source=_CYCLONE_DRAWING_SOURCE,
        )
    return Quantity(magnitude=velocity_head_count * 0.5 * rho * v**2, unit="Pa")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _cyclone_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_cyclone_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _cyclone_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_cyclone_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
