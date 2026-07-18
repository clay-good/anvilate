"""T1 analytical linear-elastic fracture mechanics (LEFM, closed-form).

Where the Inglis hole shows that a sharp flaw multiplies stress without limit, the
stress-intensity factor makes that danger quantitative. Around a crack tip the
elastic stress field has a fixed shape and a single amplitude — the mode-I
stress-intensity factor

    K_I = Y·σ·√(π·a),

for a remote stress σ, a crack of length a (half-length for a central crack), and a
dimensionless geometry factor Y that captures the crack's shape and location (Y = 1
for a central crack in a wide plate, ~1.12 for an edge crack — supplied like any
handbook coefficient). The crack runs when K_I reaches the material's fracture
toughness K_IC, which inverts to a critical crack length

    a_c = (1/π)·(K_IC / (Y·σ))²,

the flaw size a given stress can tolerate before fast fracture. Stresses and lengths
are dimension-checked :class:`~anvilate.units.Quantity` values; the fracture
toughness carries the LEFM unit MPa·√m.
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

__all__ = [
    "stress_intensity_factor",
    "critical_crack_length",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def stress_intensity_factor(
    *, remote_stress: Quantity, crack_length: Quantity, geometry_factor: float = 1.0
) -> Quantity:
    """The mode-I stress-intensity factor K_I = Y·σ·√(π·a).

    The amplitude of the crack-tip stress field, and the quantity to compare against
    the material's fracture toughness K_IC: the crack is stable while K_I < K_IC and
    runs when it reaches it. ``remote_stress`` σ is the applied (far-field) stress,
    ``crack_length`` a the crack length (the half-length for a central through-crack),
    and ``geometry_factor`` Y the dimensionless shape/location factor (1.0 for a
    central crack in a wide plate, ~1.12 for an edge crack). σ must be a stress, a a
    positive length, and Y positive. Returns K_I in MPa·√m.
    """
    _require(remote_stress, "[pressure]", "remote_stress")
    _require(crack_length, "[length]", "crack_length")
    if geometry_factor <= 0:
        raise ValueError(f"geometry_factor must be positive; got {geometry_factor}")
    sigma = remote_stress.to("MPa").magnitude
    a = crack_length.to("m").magnitude
    if a <= 0:
        raise ValueError(f"crack_length must be positive; got {crack_length}")
    return Quantity(magnitude=geometry_factor * sigma * sqrt(pi * a), unit="MPa*m**0.5")


def critical_crack_length(
    *, fracture_toughness: Quantity, remote_stress: Quantity, geometry_factor: float = 1.0
) -> Quantity:
    """The critical crack length a_c = (1/π)·(K_IC/(Y·σ))² for fast fracture.

    The inverse of :func:`stress_intensity_factor`: the largest crack a given stress
    can carry before K_I reaches the fracture toughness and the crack runs. Below
    a_c the flaw is stable; at it, fracture. ``fracture_toughness`` K_IC is the
    material's toughness (a MPa·√m quantity), ``remote_stress`` σ the applied stress,
    and ``geometry_factor`` Y the crack shape/location factor as in
    :func:`stress_intensity_factor`. A tougher material or a lower stress tolerates a
    larger flaw — the basis of a damage-tolerance inspection interval. Returns the
    critical crack length in millimetres.
    """
    _require(fracture_toughness, "[pressure] * [length]**0.5", "fracture_toughness")
    _require(remote_stress, "[pressure]", "remote_stress")
    if geometry_factor <= 0:
        raise ValueError(f"geometry_factor must be positive; got {geometry_factor}")
    kic = fracture_toughness.to("MPa*m**0.5").magnitude
    sigma = remote_stress.to("MPa").magnitude
    if sigma <= 0:
        raise ValueError(f"remote_stress must be positive; got {remote_stress}")
    a_c = (kic / (geometry_factor * sigma)) ** 2 / pi  # metres
    return Quantity(magnitude=a_c * 1000.0, unit="mm")
