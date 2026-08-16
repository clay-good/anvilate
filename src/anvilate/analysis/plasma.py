"""T1 analytical plasma-physics checks (closed-form).

An ionized gas behaves collectively rather than as independent particles, and three quantities set
that behavior: the plasma frequency at which the electrons oscillate, the Debye length over which a
charge is screened, and the number of particles inside a Debye sphere. These govern plasma etching
of semiconductors, fusion confinement, gas-discharge lamps, and the ionosphere's reflection of radio
waves. The last ties back to radio: a signal below the plasma frequency is reflected, not
transmitted, which is how shortwave bounces off the ionosphere and why a re-entry plasma blacks out
communications.

The electron plasma frequency is f_p = (1/2pi)*sqrt(n*e^2/(eps0*m_e)), from the electron density n
(about 9 kHz times the square root of n in cm^-3). The Debye length lambda_D =
sqrt(eps0*k*T/(n*e^2)) is the distance over which the plasma screens out an electric field, set by
the density and the electron temperature T. A collection of charges is a true plasma only when many
particles sit within a Debye sphere, the plasma parameter N_D = (4/3)*pi*lambda_D^3*n being far
above one; otherwise it is just an ionized gas, not a collective medium.

Confining a plasma magnetically adds a fourth number, the plasma beta: beta = 2*mu0*n*k*T/B^2, the
plasma's own pressure measured against the magnetic pressure holding it. It is the headline figure
of merit of every tokamak and stellarator, because a magnetic bottle can only contain what it can
out-push — beta above a few percent is hard, and beta of order one is the limit.
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

_ELEMENTARY_CHARGE = 1.602176634e-19  # C
_VACUUM_PERMITTIVITY = 8.8541878128e-12  # F/m
_ELECTRON_MASS = 9.1093837015e-31  # kg
_BOLTZMANN = 1.380649e-23  # J/K
_VACUUM_PERMEABILITY = 1.25663706212e-6  # H/m

__all__ = [
    "debye_length",
    "plasma_beta",
    "plasma_frequency",
    "plasma_parameter",
]


def plasma_frequency(*, electron_density: Quantity) -> Quantity:
    """The electron plasma frequency, f_p = (1/2pi)*sqrt(n*e^2/(eps0*m_e)).

    The natural oscillation frequency of the electrons in a plasma of ``electron_density`` n. It is
    the radio cutoff: an electromagnetic wave below f_p is reflected rather than transmitted (why
    shortwave bounces off the ionosphere and re-entry vehicles suffer a comms blackout). Returns the
    ordinary plasma frequency in Hz.
    """
    _check(electron_density, "1/[length]**3", "electron_density")
    n = electron_density.to("1/m**3").magnitude
    if n < 0:
        raise ValueError("electron_density must be non-negative")
    omega_p = sqrt(n * _ELEMENTARY_CHARGE**2 / (_VACUUM_PERMITTIVITY * _ELECTRON_MASS))
    return Quantity(magnitude=omega_p / (2.0 * pi), unit="Hz")


def debye_length(*, electron_density: Quantity, electron_temperature: Quantity) -> Quantity:
    """The Debye screening length, lambda_D = sqrt(eps0*k*T/(n*e^2)).

    The distance over which a plasma of ``electron_density`` n and absolute ``electron_temperature``
    T screens out an electric field: beyond a few Debye lengths a charge is shielded and the plasma
    is quasi-neutral. Hotter, thinner plasmas screen over longer distances. Returns the Debye length
    in m.
    """
    _check(electron_density, "1/[length]**3", "electron_density")
    _check(electron_temperature, "[temperature]", "electron_temperature")
    n = electron_density.to("1/m**3").magnitude
    t = electron_temperature.to("K").magnitude
    if n <= 0:
        raise ValueError("electron_density must be positive")
    if t <= 0:
        raise ValueError("electron_temperature must be positive (absolute temperature)")
    lam = sqrt(_VACUUM_PERMITTIVITY * _BOLTZMANN * t / (n * _ELEMENTARY_CHARGE**2))
    return Quantity(magnitude=lam, unit="m")


def plasma_parameter(*, electron_density: Quantity, electron_temperature: Quantity) -> float:
    """The plasma parameter, N_D = (4/3)*pi*lambda_D^3*n.

    The number of particles inside a Debye sphere, from the ``electron_density`` n and absolute
    ``electron_temperature`` T. It is the test for collective behavior: N_D much above 1 means each
    particle interacts with many others at once and the medium is a true plasma; N_D near 1 means it
    is merely an ionized gas. Returns the plasma parameter as a plain float.
    """
    lam = (
        debye_length(electron_density=electron_density, electron_temperature=electron_temperature)
        .to("m")
        .magnitude
    )
    n = electron_density.to("1/m**3").magnitude
    return (4.0 / 3.0) * pi * lam**3 * n


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def plasma_beta(
    *, electron_density: Quantity, temperature: Quantity, magnetic_flux_density: Quantity
) -> float:
    """The plasma beta, β = 2·μ₀·n·k·T/B².

    The ratio of the plasma's kinetic pressure to the magnetic pressure confining it:
    β = n·k·T/(B²/2μ₀), from the ``electron_density`` n, the absolute ``temperature`` T, and the
    ``magnetic_flux_density`` B. The denominator is exactly the magnetic pressure of
    :func:`anvilate.analysis.magnetics.magnetic_pressure`; this is the number that says whether the
    field can hold the plasma at all.

    It is the figure of merit magnetic confinement is judged on, and it is a hard one: a high-field
    tokamak at 10 keV and 10²⁰ m⁻³ in 5 T runs β ≈ 1.6%, and pushing much past a few percent
    invites pressure-driven instabilities. Since fusion power goes as the pressure squared while
    the magnets cost the field squared, β is directly the economic efficiency of the confinement
    scheme. β ≥ 1 means the plasma is not confined by the field at all. This is the single-species
    (electron) beta; a two-species plasma at equal ion and electron temperature carries twice this.
    Temperature must be absolute. Returns the dimensionless beta as a plain float.
    """
    _check(electron_density, "1/[length]**3", "electron_density")
    _check(temperature, "[temperature]", "temperature")
    _check(magnetic_flux_density, "[magnetic_field]", "magnetic_flux_density")
    n = electron_density.to("1/m**3").magnitude
    t = temperature.to("K").magnitude
    b = magnetic_flux_density.to("T").magnitude
    if n <= 0:
        raise ValueError("electron_density must be positive")
    if t <= 0:
        raise ValueError("temperature must be a positive absolute temperature")
    if b <= 0:
        raise ValueError("magnetic_flux_density must be positive")
    return 2.0 * _VACUUM_PERMEABILITY * n * _BOLTZMANN * t / (b * b)
