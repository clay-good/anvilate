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
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

_ELEMENTARY_CHARGE = 1.602176634e-19  # C
_VACUUM_PERMITTIVITY = 8.8541878128e-12  # F/m
_ELECTRON_MASS = 9.1093837015e-31  # kg
_BOLTZMANN = 1.380649e-23  # J/K

__all__ = [
    "debye_length",
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
