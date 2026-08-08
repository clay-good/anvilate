"""T1 analytical elastic-wave-speed checks (closed-form).

Mechanical waves travel through a solid at speeds set by its stiffness and density. Three modes
matter: a longitudinal wave along a thin bar, a shear (transverse) wave, and a bulk longitudinal
(pressure) wave through an extended solid. These are the velocities an ultrasonic thickness gauge or
flaw detector relies on, and the P- and S-wave speeds a seismograph reads to locate an earthquake.
This is elastic-wave propagation in a solid, distinct from the thermodynamic speed of sound in a gas
(sqrt(gamma*R*T)) of :mod:`anvilate.analysis.compressible_flow`.

In a thin bar the longitudinal wave travels at v = sqrt(E/rho), from the Young's modulus E and the
density rho — about 5000 m/s in steel. A shear wave (in which the material moves across the
direction of travel) goes at v_s = sqrt(G/rho) from the shear modulus G, always slower than the
longitudinal wave, which is why an S-wave arrives after the P-wave. In an extended (bulk) solid the
P-wave is stiffened by the surrounding material to v_p = sqrt((K + 4G/3)/rho), from the bulk modulus
K and shear modulus G — the fastest of the three.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "bar_wave_speed",
    "bulk_longitudinal_wave_speed",
    "shear_wave_speed",
]


def bar_wave_speed(*, elastic_modulus: Quantity, density: Quantity) -> Quantity:
    """The thin-bar longitudinal wave speed, v = sqrt(E/rho).

    The speed of a longitudinal (extensional) wave along a slender bar, from its ``elastic_modulus``
    E (Young's modulus) and ``density`` rho: v = sqrt(E/rho). About 5000 m/s in steel, it is the
    velocity an ultrasonic gauge uses to turn an echo time into a thickness. Returns the speed in
    m/s.
    """
    _check(elastic_modulus, "[pressure]", "elastic_modulus")
    _check(density, "[mass]/[length]**3", "density")
    e = elastic_modulus.to("Pa").magnitude
    rho = density.to("kg/m**3").magnitude
    if e <= 0:
        raise ValueError("elastic_modulus must be positive")
    if rho <= 0:
        raise ValueError("density must be positive")
    return Quantity(magnitude=sqrt(e / rho), unit="m/s")


def shear_wave_speed(*, shear_modulus: Quantity, density: Quantity) -> Quantity:
    """The shear (transverse) wave speed, v_s = sqrt(G/rho).

    The speed of a transverse wave, in which the material displaces across the direction of travel,
    from the ``shear_modulus`` G and ``density`` rho: v_s = sqrt(G/rho). It is always slower than
    the longitudinal wave (G < E), so an earthquake's S-wave arrives after the P-wave — the delay a
    seismograph times to find the distance. Returns the speed in m/s.
    """
    _check(shear_modulus, "[pressure]", "shear_modulus")
    _check(density, "[mass]/[length]**3", "density")
    g = shear_modulus.to("Pa").magnitude
    rho = density.to("kg/m**3").magnitude
    if g <= 0:
        raise ValueError("shear_modulus must be positive")
    if rho <= 0:
        raise ValueError("density must be positive")
    return Quantity(magnitude=sqrt(g / rho), unit="m/s")


def bulk_longitudinal_wave_speed(
    *, bulk_modulus: Quantity, shear_modulus: Quantity, density: Quantity
) -> Quantity:
    """The bulk longitudinal (P-wave) speed, v_p = sqrt((K + 4G/3)/rho).

    The speed of a longitudinal wave through an extended solid, where the surrounding material
    stiffens it: v_p = sqrt((K + 4G/3)/rho), from the ``bulk_modulus`` K, ``shear_modulus`` G, and
    ``density`` rho. It is the fastest of the three modes and the P-wave a seismograph sees first.
    Returns the speed in m/s.
    """
    _check(bulk_modulus, "[pressure]", "bulk_modulus")
    _check(shear_modulus, "[pressure]", "shear_modulus")
    _check(density, "[mass]/[length]**3", "density")
    k = bulk_modulus.to("Pa").magnitude
    g = shear_modulus.to("Pa").magnitude
    rho = density.to("kg/m**3").magnitude
    if k <= 0:
        raise ValueError("bulk_modulus must be positive")
    if g <= 0:
        raise ValueError("shear_modulus must be positive")
    if rho <= 0:
        raise ValueError("density must be positive")
    return Quantity(magnitude=sqrt((k + 4.0 * g / 3.0) / rho), unit="m/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
