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

Sources: Graff, *Wave Motion in Elastic Solids* — the bar, shear, bulk-longitudinal and Rayleigh
wave speeds of an isotropic solid, each from its density and two elastic constants.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "bar_wave_speed",
    "bulk_longitudinal_wave_speed",
    "rayleigh_wave_speed",
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


def rayleigh_wave_speed(
    *,
    shear_modulus: Quantity,
    density: Quantity,
    poissons_ratio: float,
) -> Quantity:
    """The Rayleigh surface-wave speed, c_R ≈ c_s·(0.862 + 1.14·ν)/(1 + ν).

    The module covered the bar, shear, and bulk-longitudinal modes but not the *surface* wave —
    the mode used to inspect for surface and near-surface cracks, and the one that carries most
    of the destructive energy in an earthquake.

    A Rayleigh wave runs along a free surface with an elliptical particle motion that dies away
    within about a wavelength of depth. Its exact speed is the root of a cubic secular equation;
    Bergmann's rational approximation stands in for it, and its error is worth knowing: about
    1.4% low at ν = 0, 0.15% low at ν = 0.29, and under 0.1% only above ν ≈ 0.35. That is fine
    for a T1 screen and too coarse to time-gate a precision inspection with. It is always slower
    than the shear wave — 0.9245·c_s in steel at ν = 0.29 — and, uniquely among the modes, its
    speed depends only on the ratio, never rising above 0.955·c_s.

    Restricted to 0 ≤ ν < 0.5, which is the domain Bergmann fitted. The approximation is not
    merely inaccurate outside it — its numerator changes sign at ν = −0.756 and it returns a
    NEGATIVE wave speed below that, so auxetic materials need the exact secular root instead.

    That 7.5% gap is the practical point: time-gating a surface-wave inspection with the shear
    speed misplaces a flaw by 8% of the standoff. ``shear_modulus`` G and ``density`` ρ set the
    shear speed √(G/ρ); ``poissons_ratio`` ν is a plain float in [0, 0.5). Returns the speed in m/s.
    """
    _check(shear_modulus, "[pressure]", "shear_modulus")
    _check(density, "[mass]/[length]**3", "density")
    g = shear_modulus.to("Pa").magnitude
    rho = density.to("kg/m**3").magnitude
    if g <= 0:
        raise ValueError(f"shear_modulus must be positive; got {shear_modulus}")
    if rho <= 0:
        raise ValueError(f"density must be positive; got {density}")
    if not 0.0 <= poissons_ratio < 0.5:
        raise ValueError(
            f"poissons_ratio must lie in [0, 0.5) — the domain Bergmann's approximation was "
            f"fitted to. Below nu = -0.756 its numerator changes sign and it returns a negative "
            f"wave speed, so an auxetic material needs the exact secular root. "
            f"Got {poissons_ratio}"
        )
    shear_speed = sqrt(g / rho)
    ratio = (0.862 + 1.14 * poissons_ratio) / (1.0 + poissons_ratio)
    return Quantity(magnitude=shear_speed * ratio, unit="m/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
