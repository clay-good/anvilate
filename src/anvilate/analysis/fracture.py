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

Below that critical size a crack does not sit still under cyclic load: it grows a
little each cycle, at a rate the Paris-Erdogan law ties to the stress-intensity
range ΔK = Y·Δσ·√(π·a),

    da/dN = C·(ΔK)^m,

a straight line of slope m on a log-log plot between the threshold and fast
fracture. C and m are material constants from crack-growth testing (C quoted for
ΔK in MPa·√m and da in metres, so its units are m/cycle per (MPa·√m)^m). Because
ΔK itself rises with √a, the rate accelerates as the crack lengthens; integrating
da/dN from an initial flaw a_i to the final tolerable size a_f gives the
constant-amplitude propagation life

    N = [a_f^(1−m/2) − a_i^(1−m/2)] / [C·(Y·Δσ·√π)^m·(1 − m/2)]   (m ≠ 2),

the cycles a damage-tolerance inspection interval is built on.
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

__all__ = [
    "stress_intensity_factor",
    "critical_crack_length",
    "paris_law_crack_growth_rate",
    "paris_law_cycles_to_failure",
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


def paris_law_crack_growth_rate(
    *,
    stress_range: Quantity,
    crack_length: Quantity,
    paris_coefficient: float,
    paris_exponent: float,
    geometry_factor: float = 1.0,
) -> Quantity:
    """The Paris-Erdogan fatigue crack-growth rate da/dN = C·(ΔK)^m.

    How fast a crack advances *per cycle* under a cyclic load. ``stress_range`` Δσ is
    the far-field stress range (σ_max − σ_min of the cycle), ``crack_length`` a the
    current crack length, and ``geometry_factor`` Y the shape/location factor as in
    :func:`stress_intensity_factor`; together they set the stress-intensity range
    ΔK = Y·Δσ·√(π·a). ``paris_coefficient`` C and ``paris_exponent`` m are the
    material's crack-growth constants (m typically 2.5–4 for steels), with C quoted
    for ΔK in MPa·√m and da in metres. Because ΔK grows with √a, the rate accelerates
    as the crack lengthens. Δσ must be a stress, a a positive length, Y positive, and
    C and m positive. Returns da/dN in metres per cycle.
    """
    _require(stress_range, "[pressure]", "stress_range")
    _require(crack_length, "[length]", "crack_length")
    if geometry_factor <= 0:
        raise ValueError(f"geometry_factor must be positive; got {geometry_factor}")
    if paris_coefficient <= 0:
        raise ValueError(f"paris_coefficient must be positive; got {paris_coefficient}")
    if paris_exponent <= 0:
        raise ValueError(f"paris_exponent must be positive; got {paris_exponent}")
    delta_sigma = stress_range.to("MPa").magnitude
    a = crack_length.to("m").magnitude
    if delta_sigma <= 0:
        raise ValueError(f"stress_range must be positive; got {stress_range}")
    if a <= 0:
        raise ValueError(f"crack_length must be positive; got {crack_length}")
    delta_k = geometry_factor * delta_sigma * sqrt(pi * a)
    return Quantity(magnitude=paris_coefficient * delta_k**paris_exponent, unit="m")


def paris_law_cycles_to_failure(
    *,
    stress_range: Quantity,
    initial_crack_length: Quantity,
    final_crack_length: Quantity,
    paris_coefficient: float,
    paris_exponent: float,
    geometry_factor: float = 1.0,
) -> float:
    """The constant-amplitude crack-propagation life, the integral of the Paris law.

    Integrating da/dN = C·(Y·Δσ·√(π·a))^m from an initial flaw ``initial_crack_length``
    a_i to the final tolerable size ``final_crack_length`` a_f (typically the
    :func:`critical_crack_length`) gives the cycles to grow the crack across that span,

        N = [a_f^(1−m/2) − a_i^(1−m/2)] / [C·(Y·Δσ·√π)^m·(1 − m/2)],

    valid while Δσ, Y and m are constant (constant-amplitude loading with a
    slowly-varying geometry factor). ``stress_range`` Δσ, ``geometry_factor`` Y,
    ``paris_coefficient`` C and ``paris_exponent`` m are as in
    :func:`paris_law_crack_growth_rate`. Both crack lengths must be positive with
    a_f > a_i, and m must differ from 2 (the m = 2 case integrates to a logarithm and
    is not covered). Returns the dimensionless number of cycles.
    """
    _require(stress_range, "[pressure]", "stress_range")
    _require(initial_crack_length, "[length]", "initial_crack_length")
    _require(final_crack_length, "[length]", "final_crack_length")
    if geometry_factor <= 0:
        raise ValueError(f"geometry_factor must be positive; got {geometry_factor}")
    if paris_coefficient <= 0:
        raise ValueError(f"paris_coefficient must be positive; got {paris_coefficient}")
    if paris_exponent <= 0:
        raise ValueError(f"paris_exponent must be positive; got {paris_exponent}")
    if paris_exponent == 2:
        raise ValueError("paris_exponent must differ from 2 (the m = 2 case is not covered)")
    delta_sigma = stress_range.to("MPa").magnitude
    a_i = initial_crack_length.to("m").magnitude
    a_f = final_crack_length.to("m").magnitude
    if a_i <= 0 or a_f <= 0:
        raise ValueError("crack lengths must be positive")
    if a_f <= a_i:
        raise ValueError("final_crack_length must exceed initial_crack_length")
    exponent = 1.0 - paris_exponent / 2.0
    numerator = a_f**exponent - a_i**exponent
    denominator = (
        paris_coefficient * (geometry_factor * delta_sigma * sqrt(pi)) ** paris_exponent * exponent
    )
    return numerator / denominator
