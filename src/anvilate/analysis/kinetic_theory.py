"""T1 analytical kinetic-theory-of-gases checks (closed-form).

A gas is a swarm of molecules in ceaseless random motion, and the kinetic theory ties that
microscopic picture to temperature and pressure. The molecules move fast — hundreds of metres per
second at room temperature — but travel only a tiny distance between collisions. These quantities
set the effusion and diffusion rates of a gas, the onset of free-molecular (rarefied) flow when the
mean free path rivals the apparatus size, and the thermal-velocity scale behind the speed of sound.
This is the molecular view that complements the bulk ideal-gas density of
:mod:`anvilate.analysis.gas_compression`.

The root-mean-square speed is v_rms = sqrt(3*R*T/M), from the absolute temperature T and the molar
mass M — lighter and hotter gases move faster, which is why hydrogen leaks and effuses quickest. The
mean (average) speed is slightly lower, v_mean = sqrt(8*R*T/(pi*M)). The mean free path, the average
distance a molecule travels between collisions, is lambda = k*T/(sqrt(2)*pi*d^2*P), from the
molecular diameter d and pressure P — about 68 nm for air at room conditions, growing without bound
as the gas is pumped down toward vacuum.
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

_GAS_CONSTANT = 8.314462618  # J/(mol*K)
_BOLTZMANN = 1.380649e-23  # J/K

__all__ = [
    "knudsen_number",
    "mean_free_path",
    "mean_molecular_speed",
    "rms_molecular_speed",
]


def rms_molecular_speed(*, temperature: Quantity, molar_mass: Quantity) -> Quantity:
    """The root-mean-square molecular speed, v_rms = sqrt(3*R*T/M).

    The speed whose square is the mean squared molecular speed, v_rms = sqrt(3*R*T/M), from the
    absolute ``temperature`` T and the ``molar_mass`` M. It is the velocity scale that sets a gas's
    pressure and its kinetic energy (½*m*v_rms^2 = (3/2)*k*T per molecule), and it is highest for
    light, hot gases. Returns the speed in m/s.
    """
    _check(temperature, "[temperature]", "temperature")
    _check(molar_mass, "[mass]/[substance]", "molar_mass")
    t = temperature.to("K").magnitude
    m = molar_mass.to("kg/mol").magnitude
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    if m <= 0:
        raise ValueError("molar_mass must be positive")
    return Quantity(magnitude=sqrt(3.0 * _GAS_CONSTANT * t / m), unit="m/s")


def mean_molecular_speed(*, temperature: Quantity, molar_mass: Quantity) -> Quantity:
    """The mean (average) molecular speed, v_mean = sqrt(8*R*T/(pi*M)).

    The arithmetic-average molecular speed of a Maxwell-Boltzmann gas, v_mean = sqrt(8*R*T/(pi*M)),
    from the absolute ``temperature`` T and ``molar_mass`` M. It is about 92% of the rms speed and
    governs collision and effusion rates. Returns the speed in m/s.
    """
    _check(temperature, "[temperature]", "temperature")
    _check(molar_mass, "[mass]/[substance]", "molar_mass")
    t = temperature.to("K").magnitude
    m = molar_mass.to("kg/mol").magnitude
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    if m <= 0:
        raise ValueError("molar_mass must be positive")
    return Quantity(magnitude=sqrt(8.0 * _GAS_CONSTANT * t / (pi * m)), unit="m/s")


def mean_free_path(
    *, temperature: Quantity, pressure: Quantity, molecular_diameter: Quantity
) -> Quantity:
    """The mean free path, lambda = k*T/(sqrt(2)*pi*d^2*P).

    The average distance a molecule travels between collisions: from the absolute ``temperature`` T,
    the ``pressure`` P, and the ``molecular_diameter`` d, lambda = k*T/(sqrt(2)*pi*d^2*P). It is
    ~68 nm for air at room conditions and grows inversely with pressure, so it rivals apparatus
    dimensions in vacuum systems (the free-molecular regime). Returns the mean free path in m.
    """
    _check(temperature, "[temperature]", "temperature")
    _check(pressure, "[pressure]", "pressure")
    _check(molecular_diameter, "[length]", "molecular_diameter")
    t = temperature.to("K").magnitude
    p = pressure.to("Pa").magnitude
    d = molecular_diameter.to("m").magnitude
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    if p <= 0:
        raise ValueError("pressure must be positive")
    if d <= 0:
        raise ValueError("molecular_diameter must be positive")
    return Quantity(magnitude=_BOLTZMANN * t / (sqrt(2.0) * pi * d * d * p), unit="m")


def knudsen_number(*, mean_free_path: Quantity, characteristic_length: Quantity) -> float:
    """The Knudsen number, Kn = lambda/L.

    The ratio of the molecular ``mean_free_path`` lambda to a flow's ``characteristic_length`` L
    (a channel width, particle diameter, or gap): Kn = lambda/L. It decides whether a gas behaves
    as a continuum or as discrete molecules. Kn < 0.01 is continuum flow (Navier-Stokes holds);
    0.01–0.1 is the slip regime (velocity slips at the wall); 0.1–10 is transitional; and Kn > 10
    is free-molecular flow, where molecules cross the gap without colliding — the regime of high
    vacuum, MEMS microchannels, and aerosol particles smaller than the mean free path. Pair with
    :func:`mean_free_path` to size the transition. Returns the dimensionless Knudsen number.
    """
    _check(mean_free_path, "[length]", "mean_free_path")
    _check(characteristic_length, "[length]", "characteristic_length")
    lam = mean_free_path.to("m").magnitude
    length = characteristic_length.to("m").magnitude
    if lam < 0:
        raise ValueError("mean_free_path must be non-negative")
    if length <= 0:
        raise ValueError("characteristic_length must be positive")
    return lam / length


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
