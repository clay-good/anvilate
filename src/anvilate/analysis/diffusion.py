"""T1 analytical Fickian diffusion (mass-transport) checks (closed-form).

Matter spreads from where it is concentrated to where it is not, driven by random molecular motion —
diffusion. Fick's law sets the rate: the flux through a layer is proportional to the concentration
gradient across it. This governs how fast a gas permeates a barrier film, a drug releases from a
patch, a dopant penetrates a wafer, or a contaminant migrates through soil. It is the mass-transport
counterpart of heat conduction (:mod:`anvilate.analysis.thermal`), with the same square-root-of-time
penetration behavior.

Across a layer of thickness L with a concentration difference Delta_C, the steady flux is
J = D * Delta_C / L (Fick's first law), from the diffusivity D. Time enters through the mean-square
spreading: a diffusion front advances a characteristic distance x = sqrt(D * t) in a time t (the
Einstein relation), so the time to diffuse a distance is t = x^2 / D. These fix the two practical
questions — how fast matter crosses a barrier, and how far (or how long) a transient front reaches.

Every one of those relations takes the diffusivity D as given. For a dilute solute in a liquid the
Stokes-Einstein relation supplies it from first principles, D = k_B*T / (6*pi*mu*r), balancing the
thermal energy driving the random walk against the Stokes drag resisting it.
"""

from __future__ import annotations

from math import erf, pi, sqrt

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_DIFFUSIVITY_SOURCE = "the cited diffusivity for the species, host, and temperature"
_GEOMETRY_SOURCE = "the part drawing (wall thickness or depth of interest)"
_PROCESS_SOURCE = "the process record (exposure time and concentrations)"
_STOKES_EINSTEIN_SOURCE = "the particle size and the fluid's absolute temperature and viscosity"


class _DiffusionInputError(RefusalError, ValueError):
    """A diffusion input that cannot be used without correction."""


def _diffusion_refusal(message: str, *, subject: str, source: str) -> _DiffusionInputError:
    return _DiffusionInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _diffusion_input_source(name: str) -> str:
    if name == "diffusivity":
        return _DIFFUSIVITY_SOURCE
    if name in {"depth", "diffusion_length", "thickness"}:
        return _GEOMETRY_SOURCE
    if name in {"dynamic_viscosity", "particle_radius", "temperature"}:
        return _STOKES_EINSTEIN_SOURCE
    return _PROCESS_SOURCE


__all__ = [
    "diffusion_length",
    "diffusion_time",
    "error_function_concentration",
    "steady_diffusion_flux",
    "stokes_einstein_diffusivity",
]

_BOLTZMANN = 1.380649e-23  # J/K


def steady_diffusion_flux(
    *, diffusivity: Quantity, concentration_difference: Quantity, thickness: Quantity
) -> Quantity:
    """The steady diffusion flux, J = D * Delta_C / L (Fick's first law).

    The molar flux through a layer at steady state: the ``diffusivity`` D times the
    ``concentration_difference`` Delta_C across the layer, over its ``thickness`` L,
    J = D*Delta_C/L. It is the permeation rate through a barrier film or membrane per unit area,
    larger for a thinner
    layer or a steeper gradient. Returns the flux in mol/(m**2*s).
    """
    _check(diffusivity, "[length]**2/[time]", "diffusivity")
    _check(concentration_difference, "[substance]/[length]**3", "concentration_difference")
    _check(thickness, "[length]", "thickness")
    d = diffusivity.to("m**2/s").magnitude
    dc = concentration_difference.to("mol/m**3").magnitude
    length = thickness.to("m").magnitude
    if d < 0:
        raise _diffusion_refusal(
            "diffusivity must be non-negative", subject="diffusivity", source=_DIFFUSIVITY_SOURCE
        )
    if length <= 0:
        raise _diffusion_refusal(
            "thickness must be positive", subject="thickness", source=_GEOMETRY_SOURCE
        )
    return Quantity(magnitude=d * dc / length, unit="mol/(m**2*s)")


def diffusion_length(*, diffusivity: Quantity, time: Quantity) -> Quantity:
    """The diffusion penetration length, x = sqrt(D * t).

    The characteristic distance a diffusion front advances in a time ``time`` t at a ``diffusivity``
    D, x = sqrt(D * t) (the Einstein relation). Because it grows only with the square root of time,
    diffusion is quick over microns and glacially slow over centimetres — the reason thin films and
    fine particles equilibrate fast. Returns the diffusion length in m.
    """
    _check(diffusivity, "[length]**2/[time]", "diffusivity")
    _check(time, "[time]", "time")
    d = diffusivity.to("m**2/s").magnitude
    t = time.to("s").magnitude
    if d < 0:
        raise _diffusion_refusal(
            "diffusivity must be non-negative", subject="diffusivity", source=_DIFFUSIVITY_SOURCE
        )
    if t < 0:
        raise _diffusion_refusal(
            "time must be non-negative", subject="time", source=_PROCESS_SOURCE
        )
    return Quantity(magnitude=sqrt(d * t), unit="m")


def diffusion_time(*, diffusion_length: Quantity, diffusivity: Quantity) -> Quantity:
    """The diffusion time over a distance, t = x^2 / D.

    The inverse of :func:`diffusion_length`: the time for a diffusion front to reach a distance
    ``diffusion_length`` x at a ``diffusivity`` D, t = x^2 / D. It quadruples for each doubling of
    the distance, so a process that diffuses across a thin section in seconds takes hours across a
    thick one. Returns the time in s.
    """
    _check(diffusion_length, "[length]", "diffusion_length")
    _check(diffusivity, "[length]**2/[time]", "diffusivity")
    x = diffusion_length.to("m").magnitude
    d = diffusivity.to("m**2/s").magnitude
    if x < 0:
        raise _diffusion_refusal(
            "diffusion_length must be non-negative",
            subject="diffusion_length",
            source=_GEOMETRY_SOURCE,
        )
    if d <= 0:
        raise _diffusion_refusal(
            "diffusivity must be positive", subject="diffusivity", source=_DIFFUSIVITY_SOURCE
        )
    return Quantity(magnitude=x * x / d, unit="s")


def error_function_concentration(
    *,
    surface_concentration: float,
    initial_concentration: float,
    depth: Quantity,
    diffusivity: Quantity,
    time: Quantity,
) -> float:
    """The concentration at depth and time in a semi-infinite solid, C = C_s − (C_s − C_0)·erf(z).

    The transient solution of Fick's second law when a surface is held at a fixed concentration and
    the solid is initially uniform — the carburizing / doping profile:
    C(x, t) = C_s − (C_s − C_0)·erf(x/(2·√(D·t))), from the ``surface_concentration`` C_s, the
    ``initial_concentration`` C_0, the ``depth`` x, the ``diffusivity`` D, and the ``time`` t. At
    the surface C = C_s; deep in, C → C_0; the profile advances as the diffusion length √(D·t)
    (:func:`diffusion_length`) grows, so reaching a target depth takes four times as long for twice
    the depth. Concentrations are plain numbers in any consistent unit (wt %, mole fraction,
    atoms/cm³) and the result is returned in that same unit.
    """
    require_finite(surface_concentration, name="surface_concentration")
    require_finite(initial_concentration, name="initial_concentration")
    _check(depth, "[length]", "depth")
    _check(diffusivity, "[length]**2/[time]", "diffusivity")
    _check(time, "[time]", "time")
    x = depth.to("m").magnitude
    d = diffusivity.to("m**2/s").magnitude
    t = time.to("s").magnitude
    if x < 0:
        raise _diffusion_refusal(
            "depth must be non-negative", subject="depth", source=_GEOMETRY_SOURCE
        )
    if d <= 0:
        raise _diffusion_refusal(
            "diffusivity must be positive", subject="diffusivity", source=_DIFFUSIVITY_SOURCE
        )
    if t <= 0:
        raise _diffusion_refusal("time must be positive", subject="time", source=_PROCESS_SOURCE)
    z = x / (2.0 * sqrt(d * t))
    return surface_concentration - (surface_concentration - initial_concentration) * erf(z)


def stokes_einstein_diffusivity(
    *, temperature: Quantity, dynamic_viscosity: Quantity, particle_radius: Quantity
) -> Quantity:
    """The Stokes-Einstein diffusivity of a dilute solute, D = k_B*T / (6*pi*mu*r).

    Every other relation in this module takes the diffusivity as given; this one computes it. A
    particle of ``particle_radius`` r suspended in a liquid of ``dynamic_viscosity`` mu at absolute
    ``temperature`` T is kicked by thermal motion and resisted by Stokes drag, and the balance of
    the two fixes how fast it spreads: D = k_B*T/(6*pi*mu*r), with k_B = 1.380649e-23 J/K. The
    6*pi*mu*r
    group is exactly the Stokes drag coefficient of
    :func:`anvilate.analysis.drag.stokes_drag_force`, which is why the relation holds only in the
    creeping-flow, dilute, spherical-particle regime it was derived for — a rough screening number
    for a protein, a nanoparticle, or a small molecule in solution, not a value for a concentrated
    suspension or a gas. Bigger particles and thicker solvents diffuse more slowly, in direct
    inverse proportion, and warming helps only weakly except through its effect on mu. Returns the
    diffusivity in m**2/s.
    """
    _check(temperature, "[temperature]", "temperature")
    _check(dynamic_viscosity, "[mass]/([length]*[time])", "dynamic_viscosity")
    _check(particle_radius, "[length]", "particle_radius")
    t = temperature.to("K").magnitude
    mu = dynamic_viscosity.to("Pa*s").magnitude
    r = particle_radius.to("m").magnitude
    if t <= 0:
        raise _diffusion_refusal(
            "temperature must be a positive absolute temperature",
            subject="temperature",
            source=_STOKES_EINSTEIN_SOURCE,
        )
    if mu <= 0:
        raise _diffusion_refusal(
            "dynamic_viscosity must be positive",
            subject="dynamic_viscosity",
            source=_STOKES_EINSTEIN_SOURCE,
        )
    if r <= 0:
        raise _diffusion_refusal(
            "particle_radius must be positive",
            subject="particle_radius",
            source=_STOKES_EINSTEIN_SOURCE,
        )
    return Quantity(magnitude=_BOLTZMANN * t / (6.0 * pi * mu * r), unit="m**2/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _diffusion_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_diffusion_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _diffusion_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_diffusion_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
